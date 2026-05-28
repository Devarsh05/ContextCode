import logging
import tempfile
import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.database import SyncSessionLocal
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.services.ingestion import IngestionService
from app.workers.celery_app import app

logger = logging.getLogger(__name__)


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


# ── Task ──────────────────────────────────────────────────────────────────────


@app.task(bind=True, name="app.workers.tasks.index_repository")
def index_repository(self, repo_url: str, job_id: str, repo_id: str) -> dict:
    """
    Ingest a GitHub repository:
      1. Clone (shallow, depth=1)
      2. Enforce size limits (10k files / 500 MB)
      3. Walk indexable files, count them
      4. Persist file_count to Repository; mark job completed

    Phase 3 will add AST parsing and embedding between steps 3 and 4.
    On any error the job and repository rows are marked 'failed'.
    The temp directory is always cleaned up via TemporaryDirectory context.
    """
    logger.info(
        "Starting indexing: repo_url=%s job_id=%s repo_id=%s",
        repo_url, job_id, repo_id,
    )

    with SyncSessionLocal() as session:
        try:
            _set_job(session, job_id, status="running", progress_pct=5, current_stage="cloning")

            with tempfile.TemporaryDirectory() as tmp_dir:
                IngestionService.clone_repository(repo_url, tmp_dir)
                logger.info("Cloned %s to %s", repo_url, tmp_dir)

                _set_job(session, job_id, progress_pct=20, current_stage="walking")

                IngestionService.enforce_size_limits(tmp_dir)

                file_count = sum(1 for _ in IngestionService.walk_repository(tmp_dir))
                logger.info("Walked %d indexable files", file_count)

            # tmp_dir deleted here — after walk is complete
            _set_repo(session, repo_id, file_count=file_count, status="completed")
            _set_job(
                session, job_id,
                status="completed", progress_pct=100, current_stage=None,
            )

            logger.info("Indexing complete: job_id=%s file_count=%d", job_id, file_count)
            return {"job_id": job_id, "repo_id": repo_id, "file_count": file_count}

        except Exception as exc:
            logger.exception("Indexing failed: job_id=%s error=%s", job_id, exc)
            _set_job(
                session, job_id,
                status="failed", error_message=str(exc), current_stage=None,
            )
            _set_repo(session, repo_id, status="failed")
            raise
