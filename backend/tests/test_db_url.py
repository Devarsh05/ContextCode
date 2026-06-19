"""Unit tests for the DATABASE_URL scheme normalizers.

These derive an async (asyncpg) URL for the app engine and a sync (psycopg2) URL
for the Celery worker / Alembic from the single raw DATABASE_URL value, idempotently
and regardless of which scheme the host injects. No DB connection is made.
"""

import pytest

from app.models.database import to_async_url, to_sync_url


class TestToAsyncUrl:
    def test_sync_postgresql_scheme_becomes_asyncpg(self):
        # Railway injects the sync form.
        assert (
            to_async_url("postgresql://u:p@h:5432/db")
            == "postgresql+asyncpg://u:p@h:5432/db"
        )

    def test_legacy_postgres_scheme_becomes_asyncpg(self):
        assert (
            to_async_url("postgres://u:p@h:5432/db")
            == "postgresql+asyncpg://u:p@h:5432/db"
        )

    def test_already_asyncpg_is_unchanged(self):
        url = "postgresql+asyncpg://u:p@h:5432/db"
        assert to_async_url(url) == url

    def test_psycopg2_scheme_becomes_asyncpg(self):
        assert (
            to_async_url("postgresql+psycopg2://u:p@h:5432/db")
            == "postgresql+asyncpg://u:p@h:5432/db"
        )


class TestToSyncUrl:
    def test_sync_postgresql_scheme_becomes_psycopg2(self):
        assert (
            to_sync_url("postgresql://u:p@h:5432/db")
            == "postgresql+psycopg2://u:p@h:5432/db"
        )

    def test_legacy_postgres_scheme_becomes_psycopg2(self):
        assert (
            to_sync_url("postgres://u:p@h:5432/db")
            == "postgresql+psycopg2://u:p@h:5432/db"
        )

    def test_asyncpg_scheme_becomes_psycopg2(self):
        assert (
            to_sync_url("postgresql+asyncpg://u:p@h:5432/db")
            == "postgresql+psycopg2://u:p@h:5432/db"
        )

    def test_already_psycopg2_is_unchanged(self):
        url = "postgresql+psycopg2://u:p@h:5432/db"
        assert to_sync_url(url) == url


class TestPreservesPartsAndNonPostgres:
    def test_credentials_host_port_db_and_query_preserved(self):
        raw = "postgresql://user:s3cr3t@db.internal:6543/contextcode?sslmode=require"
        assert (
            to_async_url(raw)
            == "postgresql+asyncpg://user:s3cr3t@db.internal:6543/contextcode?sslmode=require"
        )
        assert (
            to_sync_url(raw)
            == "postgresql+psycopg2://user:s3cr3t@db.internal:6543/contextcode?sslmode=require"
        )

    @pytest.mark.parametrize("func", [to_async_url, to_sync_url])
    def test_non_postgres_left_untouched(self, func):
        url = "sqlite+aiosqlite:///:memory:"
        assert func(url) == url
