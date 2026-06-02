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

Requires a reachable Postgres (``DATABASE_URL``); skips otherwise.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _server_url():
    raw = os.environ.get("DATABASE_URL")
    if not raw:
        pytest.skip("DATABASE_URL not set; migration schema test needs Postgres")
    url = make_url(raw)
    if not url.get_backend_name().startswith("postgresql"):
        pytest.skip("migration schema test requires a Postgres DATABASE_URL")
    return url


def _connect(url, dbname):
    return psycopg2.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        dbname=dbname,
    )


@pytest.fixture
def migrated_db(monkeypatch):
    """Create a fresh database, run ``alembic upgrade head`` against it, and
    hand back a sync (psycopg2) URL. Dropped on teardown."""
    base = _server_url()
    tmp_name = f"cc_migtest_{uuid.uuid4().hex[:12]}"

    try:
        admin = _connect(base, base.database)
    except psycopg2.OperationalError as exc:  # pragma: no cover - env dependent
        pytest.skip(f"Postgres unavailable: {exc}")
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(f'CREATE DATABASE "{tmp_name}"')
    finally:
        admin.close()

    # env.py reads DATABASE_URL (async driver) and runs the migrations online.
    async_url = base.set(drivername="postgresql+asyncpg", database=tmp_name)
    monkeypatch.setenv(
        "DATABASE_URL", async_url.render_as_string(hide_password=False)
    )

    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))

    try:
        command.upgrade(cfg, "head")
        yield base.set(drivername="postgresql+psycopg2", database=tmp_name)
    finally:
        admin = _connect(base, base.database)
        admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (tmp_name,),
                )
                cur.execute(f'DROP DATABASE IF EXISTS "{tmp_name}"')
        finally:
            admin.close()


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
