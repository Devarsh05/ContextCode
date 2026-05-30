"""
Integration tests for POST /repos/index and GET /repos/{repo_id}/status.

Uses the async_client fixture (conftest.py) which overrides get_db with the
test database. The Celery task dispatch is mocked to prevent network calls.
"""

import json
import uuid
from unittest.mock import patch

import pytest

from app.models.indexing_job import IndexingJob
from app.models.repository import Repository


# ── POST /repos/index ─────────────────────────────────────────────────────────

async def test_index_repo_invalid_url_returns_400(async_client):
    response = await async_client.post(
        "/repos/index",
        json={"repo_url": "https://not-github.com/owner/repo"},
    )
    assert response.status_code == 400
    assert "Invalid GitHub URL" in response.json()["detail"]


async def test_index_repo_valid_url_creates_repo_and_job(async_client, db_session):
    with patch("app.api.repos.index_repository") as mock_task:
        mock_task.delay.return_value = None

        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/octocat/Hello-World"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "repo_id" in data
    assert "job_id" in data
    assert data["status"] == "queued"
    mock_task.delay.assert_called_once()

    from sqlalchemy import select
    result = await db_session.execute(
        select(Repository).where(Repository.url == "https://github.com/octocat/Hello-World")
    )
    repo = result.scalar_one_or_none()
    assert repo is not None
    assert repo.name == "Hello-World"


async def test_index_repo_existing_completed_returns_existing(async_client, db_session):
    repo = Repository(
        url="https://github.com/owner/done",
        name="done",
        status="completed",
    )
    db_session.add(repo)
    await db_session.flush()

    job = IndexingJob(repo_id=repo.id, status="completed", progress_pct=100)
    db_session.add(job)
    await db_session.commit()

    response = await async_client.post(
        "/repos/index",
        json={"repo_url": "https://github.com/owner/done"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == str(repo.id)
    assert data["job_id"] == str(job.id)
    assert data["status"] == "completed"


async def test_force_reindex_queues_new_job(async_client, db_session):
    repo = Repository(
        url="https://github.com/owner/force-test",
        name="force-test",
        status="completed",
    )
    db_session.add(repo)
    await db_session.flush()

    old_job = IndexingJob(repo_id=repo.id, status="completed", progress_pct=100)
    db_session.add(old_job)
    await db_session.commit()

    with patch("app.api.repos.index_repository") as mock_task, \
         patch("app.api.repos.get_vector_store") as mock_vs:
        mock_task.delay.return_value = None
        mock_vs.return_value.drop_collection.return_value = None

        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/owner/force-test", "force_reindex": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == str(repo.id)
    assert data["job_id"] != str(old_job.id)
    assert data["status"] == "queued"
    mock_task.delay.assert_called_once()
    mock_vs.return_value.drop_collection.assert_called_once_with(str(repo.id))


async def test_no_force_reindex_returns_completed_without_queuing(async_client, db_session):
    repo = Repository(
        url="https://github.com/owner/no-force-test",
        name="no-force-test",
        status="completed",
    )
    db_session.add(repo)
    await db_session.flush()

    job = IndexingJob(repo_id=repo.id, status="completed", progress_pct=100)
    db_session.add(job)
    await db_session.commit()

    with patch("app.api.repos.index_repository") as mock_task:
        mock_task.delay.return_value = None

        response = await async_client.post(
            "/repos/index",
            json={"repo_url": "https://github.com/owner/no-force-test", "force_reindex": False},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["repo_id"] == str(repo.id)
    assert data["job_id"] == str(job.id)
    assert data["status"] == "completed"
    mock_task.delay.assert_not_called()


# ── GET /repos/{repo_id}/status (SSE) ────────────────────────────────────────

async def test_status_sse_unknown_repo_returns_404(async_client):
    response = await async_client.get(f"/repos/{uuid.uuid4()}/status")
    assert response.status_code == 404


async def test_status_sse_streams_completed_event(async_client, db_session):
    repo = Repository(url="https://github.com/owner/sse-test", name="sse-test")
    db_session.add(repo)
    await db_session.flush()

    job = IndexingJob(repo_id=repo.id, status="completed", progress_pct=100)
    db_session.add(job)
    await db_session.commit()

    async with async_client.stream("GET", f"/repos/{repo.id}/status") as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        events = []
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
                break

    assert len(events) == 1
    assert events[0]["status"] == "completed"
    assert events[0]["progress_pct"] == 100
    assert events[0]["current_stage"] is None
    assert events[0]["error_message"] is None
