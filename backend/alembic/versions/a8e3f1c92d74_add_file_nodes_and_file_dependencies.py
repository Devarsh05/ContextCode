"""add file_nodes and file_dependencies tables

Revision ID: a8e3f1c92d74
Revises: b5c3e8a91d2f
Create Date: 2026-05-30 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8e3f1c92d74"
down_revision: Union[str, Sequence[str], None] = "b5c3e8a91d2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_nodes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("repo_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("import_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("imported_by_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id", "file_path", name="uq_file_nodes_repo_id_file_path"),
    )
    op.create_table(
        "file_dependencies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("repo_id", sa.UUID(), nullable=False),
        sa.Column("source_file", sa.String(), nullable=False),
        sa.Column("target_file", sa.String(), nullable=False),
        sa.Column("import_raw", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_file_dependencies_repo_id_source_file",
        "file_dependencies",
        ["repo_id", "source_file"],
    )


def downgrade() -> None:
    op.drop_index("ix_file_dependencies_repo_id_source_file", table_name="file_dependencies")
    op.drop_table("file_dependencies")
    op.drop_table("file_nodes")
