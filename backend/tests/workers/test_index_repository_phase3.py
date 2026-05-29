import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.code_chunk import CodeChunk  # registers table with Base.metadata
from app.models.database import Base
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.services.vector_store import VectorStore
from app.workers.tasks import run_indexing_pipeline


# ── Fake embedder (avoids loading sentence-transformers) ─────────────────────

class FakeEmbedder:
    """Returns deterministic 3-D unit vectors for fast, reproducible tests."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(i % 3 == j) for j in range(3)] for i, _ in enumerate(texts)]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]

    @property
    def dimension(self) -> int:
        return 3

    @property
    def model_name(self) -> str:
        return "fake"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sync_db(tmp_path):
    """Sync SQLite session with all tables — no Postgres required."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Factory = sessionmaker(engine, expire_on_commit=False)
    with Factory() as session:
        yield session
    engine.dispose()


@pytest.fixture
def test_store(tmp_path):
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    return VectorStore(persist_path=str(chroma_dir))


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def repo_row(sync_db):
    repo = Repository(url="https://github.com/test/repo", name="repo")
    sync_db.add(repo)
    sync_db.flush()
    sync_db.commit()
    return repo


@pytest.fixture
def job_row(sync_db, repo_row):
    job = IndexingJob(repo_id=repo_row.id)
    sync_db.add(job)
    sync_db.flush()
    sync_db.commit()
    return job


@pytest.fixture
def fixture_repo(tmp_path):
    """Two-file Python repo with one function + one class each."""
    (tmp_path / "auth.py").write_text(
        "def login(username, password):\n    pass\n\n"
        "class UserManager:\n    def create(self):\n        pass\n"
    )
    (tmp_path / "utils.py").write_text(
        "import os\n\n"
        "def helper():\n    pass\n"
    )
    return tmp_path


def _run(repo, job, path, sync_db, test_store, fake_embedder, **kwargs):
    """Convenience wrapper so tests don't repeat long call signatures."""
    run_indexing_pipeline(
        repo_id=str(repo.id),
        job_id=str(job.id),
        local_path=str(path),
        session=sync_db,
        embedder=fake_embedder,
        vector_store=test_store,
        **kwargs,
    )


# ── Persistence ───────────────────────────────────────────────────────────────

class TestCodeChunkPersistence:
    def test_chunks_written_to_db(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()
        # auth.py: function + class (+ optional module); utils.py: module + function
        assert count >= 3

    def test_chunk_metadata_fields_match_parsed_content(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        chunks = (
            sync_db.query(CodeChunk)
            .filter(CodeChunk.repo_id == repo_row.id)
            .all()
        )
        for chunk in chunks:
            assert chunk.chunk_type in ("function", "class", "module")
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
            assert chunk.language == "python"
            assert chunk.content.strip()

    def test_vector_store_count_matches_db_count(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        db_count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()
        chroma_count = test_store.chunk_count(str(repo_row.id))
        assert db_count == chroma_count > 0


# ── Progress ──────────────────────────────────────────────────────────────────

class TestProgress:
    def test_job_ends_completed_at_100_pct(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        sync_db.refresh(job_row)
        assert job_row.status == "completed"
        assert job_row.progress_pct == 100
        assert job_row.current_stage is None

    def test_repo_status_set_completed(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        sync_db.refresh(repo_row)
        assert repo_row.status == "completed"
        assert repo_row.file_count is not None and repo_row.file_count >= 2


# ── Force Reindex ─────────────────────────────────────────────────────────────

class TestForceReindex:
    def test_force_reindex_drops_db_chunks_and_rebuilds(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo
    ):
        # First pass
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)
        first_count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()

        # Second pass with force_reindex
        job2 = IndexingJob(repo_id=repo_row.id)
        sync_db.add(job2)
        sync_db.commit()
        _run(
            repo_row, job2, fixture_repo, sync_db, test_store, fake_embedder,
            force_reindex=True,
        )

        second_count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()
        chroma_count = test_store.chunk_count(str(repo_row.id))

        # No accumulation: same files → same chunk count; Chroma in sync
        assert second_count == first_count
        assert chroma_count == second_count


# ── Error Handling ────────────────────────────────────────────────────────────

class TestErrorHandling:
    def test_malformed_file_skipped_job_still_completes(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, tmp_path
    ):
        (tmp_path / "good.py").write_text("def hello(): pass\n")
        (tmp_path / "bad.py").write_text("def (((broken:\n" * 10)

        _run(repo_row, job_row, tmp_path, sync_db, test_store, fake_embedder)

        sync_db.refresh(job_row)
        assert job_row.status == "completed"
        count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()
        assert count > 0  # good.py's chunk was indexed despite bad.py

    def test_embedding_failure_marks_job_failed(
        self, sync_db, test_store, repo_row, job_row, fixture_repo
    ):
        bad_embedder = MagicMock()
        bad_embedder.embed_texts.side_effect = RuntimeError("embedding service down")

        with pytest.raises(RuntimeError, match="embedding service down"):
            run_indexing_pipeline(
                repo_id=str(repo_row.id),
                job_id=str(job_row.id),
                local_path=str(fixture_repo),
                session=sync_db,
                embedder=bad_embedder,
                vector_store=test_store,
            )

        sync_db.refresh(job_row)
        assert job_row.status == "failed"
        assert "embedding service down" in (job_row.error_message or "")

    def test_unsupported_files_only_completes_with_zero_chunks(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, tmp_path
    ):
        (tmp_path / "README.md").write_text("# Hello\n")
        (tmp_path / "config.yaml").write_text("key: value\n")

        _run(repo_row, job_row, tmp_path, sync_db, test_store, fake_embedder)

        sync_db.refresh(job_row)
        assert job_row.status == "completed"
        count = sync_db.query(CodeChunk).filter(
            CodeChunk.repo_id == repo_row.id
        ).count()
        assert count == 0
