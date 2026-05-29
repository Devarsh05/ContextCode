"""create code_chunks table

Revision ID: b5c3e8a91d2f
Revises: f0dc9d8ad487
Create Date: 2026-05-29 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5c3e8a91d2f"
down_revision: Union[str, Sequence[str], None] = "f0dc9d8ad487"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "code_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("repo_id", sa.UUID(), nullable=False),
        sa.Column("file_path", sa.String(), nullable=False),
        sa.Column("chunk_type", sa.String(), nullable=False),
        sa.Column("function_name", sa.String(), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_code_chunks_repo_id", "code_chunks", ["repo_id"])


def downgrade() -> None:
    op.drop_index("ix_code_chunks_repo_id", table_name="code_chunks")
    op.drop_table("code_chunks")
