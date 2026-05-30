"""alter file_dependencies.target_file to nullable

Revision ID: d3b7e2f10a95
Revises: a8e3f1c92d74
Create Date: 2026-05-30 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3b7e2f10a95"
down_revision: Union[str, Sequence[str], None] = "a8e3f1c92d74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("file_dependencies", "target_file", existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    op.alter_column("file_dependencies", "target_file", existing_type=sa.String(), nullable=False)
