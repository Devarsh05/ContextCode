"""Schema guard for the ``repositories.is_demo`` column.

Builds a throwaway database from the Alembic migrations (via the ``migrated_db``
fixture in conftest.py) and asserts the live schema matches the ORM: the column
exists, is NOT NULL, and its server_default backfills ``False`` for rows
inserted without it. Requires Postgres; skips otherwise.
"""
from __future__ import annotations

import uuid

import pytest

pytest.importorskip("psycopg2")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def test_is_demo_column_exists_and_is_not_null(migrated_db):
    engine = create_engine(migrated_db)
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'repositories' "
                    "AND column_name = 'is_demo'"
                )
            ).first()
        assert row is not None, "is_demo column missing from migrated schema"
        assert row[0] == "NO"
    finally:
        engine.dispose()


def test_is_demo_defaults_false_when_omitted(migrated_db):
    """A repo inserted without is_demo must persist with is_demo=False —
    proves the migration's server_default is applied by the live schema."""
    from app.models.repository import Repository

    engine = create_engine(migrated_db)
    Session = sessionmaker(engine, expire_on_commit=False)
    try:
        # Insert raw SQL omitting is_demo entirely so only the DB default fills
        # it (the ORM would otherwise supply its Python-side default).
        repo_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO repositories (id, url, name, status) "
                    "VALUES (:id, :url, :name, 'pending')"
                ),
                {
                    "id": repo_id,
                    "url": f"https://github.com/test/{uuid.uuid4().hex}",
                    "name": "is-demo-guard",
                },
            )

        with Session() as session:
            stored = session.get(Repository, repo_id)
            assert stored is not None
            assert stored.is_demo is False
    finally:
        engine.dispose()
