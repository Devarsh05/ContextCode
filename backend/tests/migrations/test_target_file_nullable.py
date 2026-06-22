"""Regression guard against schema drift between the ORM models and migrations.

The dependency graph stores NULL in ``file_dependencies.target_file`` for
unresolved / third-party imports. The ORM model declares the column nullable,
but the *live* schema is defined by the Alembic migrations — and the two
diverged once: the creating migration made the column NOT NULL, a later
migration relaxed it, but a database that was never upgraded kept the
constraint and only blew up in Celery (``NotNullViolation``).

The rest of the suite builds its schema from ``Base.metadata.create_all``
(SQLite), so it inherits the model's nullability and can never catch this class
of drift. This module instead builds a throwaway database **from the
migrations** and proves a ``target_file=None`` row persists — so a future
migration that reintroduces NOT NULL fails here, not in production.

Requires a reachable Postgres (``DATABASE_URL``); skips otherwise. The
``migrated_db`` fixture lives in this package's conftest.py.
"""
from __future__ import annotations

import uuid

import pytest

pytest.importorskip("psycopg2")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402


def test_target_file_is_nullable_in_migrated_schema(migrated_db):
    engine = create_engine(migrated_db)
    try:
        with engine.connect() as conn:
            is_nullable = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'file_dependencies' "
                    "AND column_name = 'target_file'"
                )
            ).scalar_one()
        assert is_nullable == "YES"
    finally:
        engine.dispose()


def test_null_target_file_persists_against_migrated_schema(migrated_db):
    """An unresolved import (target_file=None) must persist without raising —
    the exact write that produced NotNullViolation in production."""
    from app.models.graph import FileDependency
    from app.models.repository import Repository

    engine = create_engine(migrated_db)
    Session = sessionmaker(engine, expire_on_commit=False)
    try:
        with Session() as session:
            repo = Repository(
                url=f"https://github.com/test/{uuid.uuid4().hex}",
                name="migration-guard",
            )
            session.add(repo)
            session.commit()

            dep = FileDependency(
                repo_id=repo.id,
                source_file="app/main.py",
                target_file=None,  # unresolved / third-party import
                import_raw="import os",
            )
            session.add(dep)
            session.commit()  # must NOT raise NotNullViolation

            stored = session.get(FileDependency, dep.id)
            assert stored is not None
            assert stored.target_file is None
    finally:
        engine.dispose()
