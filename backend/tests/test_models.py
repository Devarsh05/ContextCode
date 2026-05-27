import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.indexing_job import IndexingJob
from app.models.repository import Repository


async def test_db_session_fixture_works(db_session):
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


async def test_create_repository(db_session):
    repo = Repository(url="https://github.com/org/repo", name="repo")
    db_session.add(repo)
    await db_session.flush()
    await db_session.refresh(repo)

    assert isinstance(repo.id, uuid.UUID)
    assert repo.status == "pending"
    assert repo.file_count is None
    assert repo.created_at is not None
    assert repo.updated_at is not None


async def test_repository_url_unique(db_session):
    url = "https://github.com/org/duplicate"
    db_session.add(Repository(url=url, name="repo1"))
    await db_session.flush()

    db_session.add(Repository(url=url, name="repo2"))
    try:
        await db_session.flush()
        pytest.fail("Expected IntegrityError was not raised")
    except IntegrityError:
        pass


async def test_create_indexing_job(db_session):
    repo = Repository(url="https://github.com/org/job-repo", name="job-repo")
    db_session.add(repo)
    await db_session.flush()

    job = IndexingJob(repo_id=repo.id)
    db_session.add(job)
    await db_session.flush()
    await db_session.refresh(job)

    assert isinstance(job.id, uuid.UUID)
    assert job.status == "queued"
    assert job.progress_pct == 0
    assert job.current_stage is None
    assert job.error_message is None
    assert job.created_at is not None
    assert job.updated_at is not None


async def test_indexing_job_relationship(db_session):
    repo = Repository(url="https://github.com/org/rel-repo", name="rel-repo")
    db_session.add(repo)
    await db_session.flush()

    job = IndexingJob(repo_id=repo.id)
    db_session.add(job)
    await db_session.commit()

    stmt = (
        select(Repository)
        .where(Repository.id == repo.id)
        .options(selectinload(Repository.indexing_jobs))
    )
    result = await db_session.execute(stmt)
    loaded_repo = result.scalar_one()

    assert len(loaded_repo.indexing_jobs) == 1
    assert loaded_repo.indexing_jobs[0].id == job.id
