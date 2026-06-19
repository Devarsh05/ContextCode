import os
import sys
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Add backend/ to sys.path so `from app.models...` works when alembic
# is invoked from backend/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

config = context.config

# Import every model so autogenerate can detect all tables. Migrations run on the
# SYNC driver (psycopg2) regardless of how DATABASE_URL arrives — Railway's
# postgresql:// and the local postgresql+asyncpg:// both normalize to +psycopg2.
from app.models.database import Base, to_sync_url  # noqa: E402
from app.models.graph import FileDependency, FileNode  # noqa: E402, F401
from app.models.indexing_job import IndexingJob  # noqa: E402, F401
from app.models.repository import Repository  # noqa: E402, F401

config.set_main_option("sqlalchemy.url", to_sync_url(os.environ["DATABASE_URL"]))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
