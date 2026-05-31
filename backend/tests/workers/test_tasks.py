"""Tests for the dependency-graph phase wired into run_indexing_pipeline.

Covers that graph building runs after embedding, that a graph-build failure
does not fail the indexing job, that progress hits the 85/95 checkpoints, and
that real graph rows are persisted end-to-end.

Uses a synchronous SQLite session — no Postgres, Redis, or Celery required.
"""

import app.workers.tasks as tasks_mod
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.graph.builder import GraphBuildResult
from app.models.code_chunk import CodeChunk  # registers table
from app.models.database import Base
from app.models.graph import FileDependency, FileNode
from app.models.indexing_job import IndexingJob
from app.models.repository import Repository
from app.services.vector_store import VectorStore
from app.workers.tasks import run_indexing_pipeline


# ── Fake embedder (avoids loading sentence-transformers) ─────────────────────

class FakeEmbedder:
    def embed_texts(self, texts):
        return [[float(i % 3 == j) for j in range(3)] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return self.embed_texts([text])[0]


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sync_db(tmp_path):
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
    sync_db.commit()
    return repo


@pytest.fixture
def job_row(sync_db, repo_row):
    job = IndexingJob(repo_id=repo_row.id)
    sync_db.add(job)
    sync_db.commit()
    return job


@pytest.fixture
def fixture_repo(tmp_path):
    """Python package where main.py imports from a sibling module."""
    pkg = tmp_path / "app"
    pkg.mkdir()
    (pkg / "main.py").write_text(
        "import os\n"
        "from .utils import helper\n\n"
        "def run():\n    return helper()\n"
    )
    (pkg / "utils.py").write_text("def helper():\n    return 1\n")
    return tmp_path


def _run(repo, job, path, sync_db, test_store, fake_embedder, **kwargs):
    run_indexing_pipeline(
        repo_id=str(repo.id),
        job_id=str(job.id),
        local_path=str(path),
        session=sync_db,
        embedder=fake_embedder,
        vector_store=test_store,
        **kwargs,
    )


# ── Tests ───────────────────────────────────────────────────────────────────

class TestGraphPhaseWiring:
    def test_graph_build_runs_after_embedding(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo,
        monkeypatch,
    ):
        order = []

        real_embed = fake_embedder.embed_texts

        def spy_embed(texts):
            order.append("embed")
            return real_embed(texts)

        monkeypatch.setattr(fake_embedder, "embed_texts", spy_embed)

        class SpyBuilder:
            def __init__(self, session, repo_root, all_file_paths):
                pass

            def build(self, repo_id):
                order.append("graph")
                return GraphBuildResult(0, 0, 0)

        monkeypatch.setattr("app.graph.builder.GraphBuilder", SpyBuilder)

        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        assert "embed" in order and "graph" in order
        assert order.index("embed") < order.index("graph")

    def test_graph_build_failure_does_not_fail_job(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo,
        monkeypatch,
    ):
        class BoomBuilder:
            def __init__(self, *args, **kwargs):
                pass

            def build(self, repo_id):
                raise RuntimeError("graph boom")

        monkeypatch.setattr("app.graph.builder.GraphBuilder", BoomBuilder)

        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        sync_db.refresh(job_row)
        assert job_row.status == "completed"
        assert job_row.progress_pct == 100
        assert job_row.error_message is None

    def test_progress_hits_85_and_95_during_graph_phase(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo,
        monkeypatch,
    ):
        captured = []
        real_set_job = tasks_mod._set_job

        def spy_set_job(session, job_id, **fields):
            if "progress_pct" in fields:
                captured.append(fields["progress_pct"])
            return real_set_job(session, job_id, **fields)

        monkeypatch.setattr(tasks_mod, "_set_job", spy_set_job)

        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        assert 85 in captured
        assert 95 in captured
        assert 100 in captured
        # Ordering: embedding done (80) → graph start (85) → graph done (95).
        assert captured.index(80) < captured.index(85) < captured.index(95)

    def test_graph_rows_persisted_end_to_end(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, fixture_repo,
    ):
        _run(repo_row, job_row, fixture_repo, sync_db, test_store, fake_embedder)

        nodes = (
            sync_db.execute(select(FileNode).where(FileNode.repo_id == repo_row.id))
            .scalars().all()
        )
        deps = (
            sync_db.execute(
                select(FileDependency).where(FileDependency.repo_id == repo_row.id)
            ).scalars().all()
        )
        node_paths = {n.file_path for n in nodes}
        assert "app/main.py" in node_paths
        assert "app/utils.py" in node_paths
        # The relative import resolves; `import os` does not.
        resolved = {(d.source_file, d.target_file) for d in deps if d.target_file}
        assert ("app/main.py", "app/utils.py") in resolved
        assert any(d.target_file is None for d in deps)  # os unresolved

    def test_zero_chunk_repo_still_completes_with_graph_phase(
        self, sync_db, test_store, fake_embedder, repo_row, job_row, tmp_path,
    ):
        # No supported source files → no chunks, embedding skipped, graph empty.
        (tmp_path / "README.md").write_text("# Hello\n")

        _run(repo_row, job_row, tmp_path, sync_db, test_store, fake_embedder)

        sync_db.refresh(job_row)
        assert job_row.status == "completed"
        assert job_row.progress_pct == 100
