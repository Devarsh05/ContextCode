import logging
import posixpath
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.models.database import SyncSessionLocal
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.services.ingestion import IngestionService
from app.workers.celery_app import app

logger = logging.getLogger(__name__)

_EMBED_BATCH = 200   # chunks per embedding progress tick
_DB_BATCH = 500      # rows per session.add_all + flush


# ── Path helpers ──────────────────────────────────────────────────────────────


def _to_repo_relative(abs_path: str, clone_root: str) -> str:
    """Return abs_path relative to clone_root as a forward-slash string.

    Separators are normalized to '/' first and the relative path is computed
    with posixpath, so the result is identical whether the worker runs on
    Windows (native backslash temp clone paths like
    C:\\Users\\...\\Temp\\tmpXXX\\pkg\\mod.py) or Linux (Railway). This is the
    cross-platform-deterministic form of os.path.relpath — it does not depend
    on the host's path semantics, so paths are clean by construction on both.
    """
    norm_path = abs_path.replace("\\", "/")
    norm_root = clone_root.replace("\\", "/").rstrip("/")
    return posixpath.relpath(norm_path, norm_root)


# ── Sync DB helpers ───────────────────────────────────────────────────────────


def _set_job(session: Session, job_id: str, **fields) -> None:
    session.execute(
        update(IndexingJob)
        .where(IndexingJob.id == uuid.UUID(job_id))
        .values(**fields)
    )
    session.commit()


def _set_repo(session: Session, repo_id: str, **fields) -> None:
    session.execute(
        update(Repository)
        .where(Repository.id == uuid.UUID(repo_id))
        .values(**fields)
    )
    session.commit()


# ── Pipeline (Stages 2–7) ─────────────────────────────────────────────────────


def run_indexing_pipeline(
    repo_id: str,
    job_id: str,
    local_path: str,
    session: Session,
    force_reindex: bool = False,
    embedder=None,
    vector_store=None,
) -> int:
    """
    Stages 2–7 of the indexing pipeline, starting from a locally cloned repo.

    Returns the number of indexable files found.
    Raises on embedding or Chroma failure after marking the job as failed.
    Per-file parse errors are logged and skipped without failing the job.
    """
    from app.models.code_chunk import CodeChunk
    from app.parsers.registry import get_language_for_file, get_parser_for_language
    from app.services.embeddings import get_embedder
    from app.services.vector_store import get_vector_store

    if embedder is None:
        embedder = get_embedder()
    if vector_store is None:
        vector_store = get_vector_store()

    repo_uuid = uuid.UUID(repo_id)
    repo_id_str = str(repo_uuid)   # used as Chroma collection key

    # ── Force reindex: clear existing data before rebuilding ─────────────────
    if force_reindex:
        session.execute(delete(CodeChunk).where(CodeChunk.repo_id == repo_uuid))
        session.commit()
        vector_store.drop_collection(repo_id_str)

    # ── Stage 2: Walk + enforce size limits (progress: 30%) ──────────────────
    _set_job(session, job_id, progress_pct=30, current_stage="walking")
    IngestionService.enforce_size_limits(local_path)
    file_paths = list(IngestionService.walk_repository(local_path))
    file_count = len(file_paths)
    _set_repo(session, repo_id, file_count=file_count)

    # ── Stage 3: Parse files into CodeChunk ORM objects (progress: 30–55%) ──
    _set_job(session, job_id, progress_pct=32, current_stage="parsing")
    chunk_rows: list[CodeChunk] = []

    for i, file_path in enumerate(file_paths):
        try:
            language = get_language_for_file(file_path)
            if language is None:
                continue
            parser = get_parser_for_language(language)
            if parser is None:
                continue
            content = Path(file_path).read_text(encoding="utf-8", errors="replace")
            # Store the path relative to the clone root so chunk file_path is
            # clean and portable (drives citations + the LLM context). Reading
            # still uses the absolute path above.
            rel_path = _to_repo_relative(file_path, local_path)
            for pc in parser.parse(rel_path, content):
                chunk_rows.append(
                    CodeChunk(
                        repo_id=repo_uuid,
                        file_path=pc.file_path,
                        chunk_type=pc.chunk_type,
                        function_name=pc.function_name,
                        start_line=pc.start_line,
                        end_line=pc.end_line,
                        content=pc.content,
                        language=pc.language,
                    )
                )
        except Exception:
            logger.warning("Parse error on %s — skipping file", file_path, exc_info=True)

        if file_count > 0:
            pct = 30 + int(25 * (i + 1) / file_count)
            _set_job(session, job_id, progress_pct=pct, current_stage="parsing")

    # ── Stage 4: Persist CodeChunk rows (batched, progress: 60%) ─────────────
    _set_job(session, job_id, progress_pct=60, current_stage="persisting")
    for i in range(0, len(chunk_rows), _DB_BATCH):
        session.add_all(chunk_rows[i : i + _DB_BATCH])
        session.flush()
    session.commit()

    # ── Stages 5–6: Embed + store in Chroma (progress: 60–80%) ───────────────
    # Skipped when there are no chunks; the dependency graph is still built.
    if chunk_rows:
        try:
            all_embeddings: list[list[float]] = []
            total = len(chunk_rows)

            for i in range(0, total, _EMBED_BATCH):
                batch = chunk_rows[i : i + _EMBED_BATCH]
                all_embeddings.extend(embedder.embed_texts([c.content for c in batch]))
                pct = 60 + int(20 * min(i + _EMBED_BATCH, total) / total)
                _set_job(session, job_id, progress_pct=pct, current_stage="embedding")

            # ── Stage 6: Write to Chroma (progress: 80%) ─────────────────────
            _set_job(session, job_id, progress_pct=80, current_stage="storing")
            vector_store.add_chunks(repo_id_str, chunk_rows, all_embeddings)

        except Exception as exc:
            logger.exception("Pipeline failed: repo_id=%s error=%s", repo_id, exc)
            _set_job(
                session, job_id,
                status="failed", error_message=str(exc), current_stage=None,
            )
            _set_repo(session, repo_id, status="failed")
            raise

    # ── Stage 7: Build dependency graph (non-fatal, progress: 85–95%) ────────
    # Graph build failure must NOT fail the indexing job — log a warning and
    # carry on to completion. Reuses the Stage 2 file list (no re-walk); paths
    # are made repo-relative (forward slashes) for the builder.
    from app.graph.builder import GraphBuilder

    _set_job(session, job_id, progress_pct=85, current_stage="building_graph")
    try:
        rel_paths = [_to_repo_relative(p, local_path) for p in file_paths]
        result = GraphBuilder(session, local_path, rel_paths).build(repo_id)
        logger.info(
            "Dependency graph built: repo_id=%s nodes=%d edges=%d unresolved=%d",
            repo_id, result.node_count, result.edge_count, result.unresolved_count,
        )
    except Exception:
        session.rollback()
        logger.warning(
            "Dependency graph build failed for repo_id=%s — indexing continues",
            repo_id, exc_info=True,
        )
    _set_job(session, job_id, progress_pct=95, current_stage="building_graph")

    # ── Stage 8: Mark complete (progress: 100%) ──────────────────────────────
    _set_job(session, job_id, progress_pct=100, status="completed", current_stage=None)
    _set_repo(session, repo_id, status="completed")

    logger.info(
        "Pipeline complete: repo_id=%s chunks=%d files=%d",
        repo_id, len(chunk_rows), file_count,
    )
    return file_count


# ── Task ──────────────────────────────────────────────────────────────────────


@app.task(bind=True, name="app.workers.tasks.index_repository")
def index_repository(
    self, repo_url: str, job_id: str, repo_id: str, force_reindex: bool = False
) -> dict:
    """
    Ingest a GitHub repository end-to-end:
      1. Clone (shallow, depth=1)
      2–7. Delegate to run_indexing_pipeline (walk → parse → persist → embed → store → complete)

    On any error the job and repository rows are marked 'failed'.
    The temp directory is always cleaned up via TemporaryDirectory context.
    """
    logger.info(
        "Starting indexing: repo_url=%s job_id=%s repo_id=%s force_reindex=%s",
        repo_url, job_id, repo_id, force_reindex,
    )

    with SyncSessionLocal() as session:
        try:
            _set_job(session, job_id, status="running", progress_pct=10, current_stage="cloning")

            with tempfile.TemporaryDirectory() as tmp_dir:
                IngestionService.clone_repository(repo_url, tmp_dir)
                logger.info("Cloned %s to %s", repo_url, tmp_dir)

                file_count = run_indexing_pipeline(
                    repo_id=repo_id,
                    job_id=job_id,
                    local_path=tmp_dir,
                    session=session,
                    force_reindex=force_reindex,
                )

            logger.info("Indexing complete: job_id=%s file_count=%d", job_id, file_count)
            return {"job_id": job_id, "repo_id": repo_id, "file_count": file_count}

        except Exception as exc:
            logger.exception("Indexing failed: job_id=%s error=%s", job_id, exc)
            # run_indexing_pipeline may have already marked failed — _set_job is idempotent
            _set_job(
                session, job_id,
                status="failed", error_message=str(exc), current_stage=None,
            )
            _set_repo(session, repo_id, status="failed")
            raise
