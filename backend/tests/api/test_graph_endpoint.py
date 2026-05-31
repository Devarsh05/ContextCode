"""Tests for GET /repos/{repo_id}/graph endpoint."""

import uuid

from app.models.graph import FileDependency, FileNode
from app.models.repository import Repository


async def _make_completed_repo(db_session, name="graph-repo"):
    repo = Repository(
        url=f"https://github.com/org/{name}",
        name=name,
        status="completed",
    )
    db_session.add(repo)
    await db_session.commit()
    return repo


async def _seed_graph(db_session, repo):
    """main.py imports utils.py + os(unresolved); utils.py imported by main."""
    db_session.add_all([
        FileNode(repo_id=repo.id, file_path="app/main.py", language="python",
                 import_count=2, imported_by_count=0),
        FileNode(repo_id=repo.id, file_path="app/utils.py", language="python",
                 import_count=0, imported_by_count=1),
        FileNode(repo_id=repo.id, file_path="app/core.py", language="python",
                 import_count=0, imported_by_count=3),
    ])
    db_session.add_all([
        FileDependency(repo_id=repo.id, source_file="app/main.py",
                       target_file="app/utils.py", import_raw="from .utils import helper"),
        FileDependency(repo_id=repo.id, source_file="app/main.py",
                       target_file=None, import_raw="import os"),
    ])
    await db_session.commit()


# ── 404 / 400 ────────────────────────────────────────────────────────────────

async def test_graph_unknown_repo_returns_404(async_client):
    response = await async_client.get(f"/repos/{uuid.uuid4()}/graph")
    assert response.status_code == 404


async def test_graph_not_completed_repo_returns_400(async_client, db_session):
    repo = Repository(
        url="https://github.com/org/running-repo",
        name="running-repo",
        status="running",
    )
    db_session.add(repo)
    await db_session.commit()

    response = await async_client.get(f"/repos/{repo.id}/graph")
    assert response.status_code == 400
    assert "not fully indexed" in response.json()["detail"]


# ── 200 happy path ─────────────────────────────────────────────────────────────

async def test_graph_returns_200_with_counts(async_client, db_session):
    repo = await _make_completed_repo(db_session)
    await _seed_graph(db_session, repo)

    response = await async_client.get(f"/repos/{repo.id}/graph")
    assert response.status_code == 200
    data = response.json()

    assert data["repo_id"] == str(repo.id)
    assert data["node_count"] == 3
    assert data["edge_count"] == 2
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2

    # Edge shape + one unresolved (target_file None) present.
    edge = data["edges"][0]
    assert set(edge.keys()) == {"source_file", "target_file", "import_raw"}
    assert any(e["target_file"] is None for e in data["edges"])


async def test_graph_edges_sorted_by_source_file(async_client, db_session):
    repo = await _make_completed_repo(db_session, name="edge-sort")
    db_session.add_all([
        FileDependency(repo_id=repo.id, source_file="z/last.py",
                       target_file=None, import_raw="import z"),
        FileDependency(repo_id=repo.id, source_file="a/first.py",
                       target_file=None, import_raw="import a"),
    ])
    await db_session.commit()

    response = await async_client.get(f"/repos/{repo.id}/graph")
    sources = [e["source_file"] for e in response.json()["edges"]]
    assert sources == sorted(sources)


# ── resolved_only ──────────────────────────────────────────────────────────────

async def test_resolved_only_filters_unresolved_edges(async_client, db_session):
    repo = await _make_completed_repo(db_session, name="resolved-repo")
    await _seed_graph(db_session, repo)

    response = await async_client.get(f"/repos/{repo.id}/graph?resolved_only=true")
    assert response.status_code == 200
    data = response.json()

    # Only the resolved edge (app/main.py → app/utils.py) survives.
    assert data["edge_count"] == 1
    assert all(e["target_file"] is not None for e in data["edges"])


# ── node ordering ──────────────────────────────────────────────────────────────

async def test_nodes_sorted_by_imported_by_count_desc(async_client, db_session):
    repo = await _make_completed_repo(db_session, name="sort-repo")
    await _seed_graph(db_session, repo)

    response = await async_client.get(f"/repos/{repo.id}/graph")
    counts = [n["imported_by_count"] for n in response.json()["nodes"]]
    assert counts == sorted(counts, reverse=True)
    # core.py (imported_by=3) is the most central → first.
    assert response.json()["nodes"][0]["file_path"] == "app/core.py"


# ── empty graph ────────────────────────────────────────────────────────────────

async def test_empty_graph_returns_200_with_empty_lists(async_client, db_session):
    repo = await _make_completed_repo(db_session, name="empty-repo")

    response = await async_client.get(f"/repos/{repo.id}/graph")
    assert response.status_code == 200
    data = response.json()
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert data["nodes"] == []
    assert data["edges"] == []
