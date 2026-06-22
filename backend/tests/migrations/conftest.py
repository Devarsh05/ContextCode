"""Shared fixtures for migration-schema tests.

These tests build a throwaway database **from the Alembic migrations** (not
``Base.metadata.create_all``) and assert the live schema matches expectations,
guarding against ORM/migration drift. They require a reachable Postgres
(``DATABASE_URL``) and skip otherwise.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from sqlalchemy.engine import make_url  # noqa: E402

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

    # env.py reads DATABASE_URL and normalizes it to a sync driver to run the
    # migrations online; pass the async form to prove that normalization holds.
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
