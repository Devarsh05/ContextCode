"""add is_demo to repositories

Revision ID: c7a1f4e9b2d6
Revises: d3b7e2f10a95
Create Date: 2026-06-22 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7a1f4e9b2d6"
down_revision: Union[str, Sequence[str], None] = "d3b7e2f10a95"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default backfills existing rows so the NOT NULL add succeeds.
    op.add_column(
        "repositories",
        sa.Column(
            "is_demo", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )


def downgrade() -> None:
    op.drop_column("repositories", "is_demo")
