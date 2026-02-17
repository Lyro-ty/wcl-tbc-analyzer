"""add overheal_total column to ability_metrics

Revision ID: 008
Revises: 007
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ability_metrics",
        sa.Column("overheal_total", sa.BigInteger, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ability_metrics", "overheal_total")
