"""Tests for the idempotent demo-repo seeding routine.

Uses the async ``db_session`` fixture (SQLite in-memory, schema from
``Base.metadata.create_all``) — see conftest.py.
"""
import logging

from sqlalchemy import select

from app.models.repository import Repository
from app.services.demo_seed import DEMO_REPO_URLS, seed_demo_repos


async def _add_repo(db_session, url, name, is_demo=False):
    repo = Repository(url=url, name=name, is_demo=is_demo)
    db_session.add(repo)
    await db_session.flush()
    return repo


async def test_seed_flags_only_matching_existing_rows(db_session):
    for url in DEMO_REPO_URLS:
        name = url.rsplit("/", 1)[-1]
        await _add_repo(db_session, url, name)
    # An unrelated repo that must stay untouched.
    other = await _add_repo(
        db_session, "https://github.com/owner/unrelated", "unrelated"
    )
    await db_session.commit()

    result = await seed_demo_repos(db_session)

    assert result == {"flagged": 3, "already": 0, "missing": 0}

    rows = (await db_session.execute(select(Repository))).scalars().all()
    demos = {r.url for r in rows if r.is_demo}
    assert demos == set(DEMO_REPO_URLS)
    await db_session.refresh(other)
    assert other.is_demo is False


async def test_seed_is_idempotent(db_session):
    for url in DEMO_REPO_URLS:
        await _add_repo(db_session, url, url.rsplit("/", 1)[-1])
    await db_session.commit()

    first = await seed_demo_repos(db_session)
    assert first == {"flagged": 3, "already": 0, "missing": 0}

    # Second run is a no-op: everything is already a demo, nothing re-flagged.
    second = await seed_demo_repos(db_session)
    assert second == {"flagged": 0, "already": 3, "missing": 0}

    demo_count = len(
        (
            await db_session.execute(
                select(Repository).where(Repository.is_demo.is_(True))
            )
        )
        .scalars()
        .all()
    )
    assert demo_count == 3


async def test_seed_skips_missing_repo_with_warning(db_session, caplog):
    # No rows present at all — every demo URL is missing.
    with caplog.at_level(logging.WARNING):
        result = await seed_demo_repos(db_session)

    assert result == {"flagged": 0, "already": 0, "missing": 3}

    # No rows fabricated.
    rows = (await db_session.execute(select(Repository))).scalars().all()
    assert rows == []

    # A clear warning was logged for each missing demo repo.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 3
    assert all("not present locally" in r.getMessage() for r in warnings)
