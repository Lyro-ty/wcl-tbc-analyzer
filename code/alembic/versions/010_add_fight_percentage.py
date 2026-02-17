"""add fight_percentage column to fights table

Revision ID: 010
Revises: 009
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fights", sa.Column("fight_percentage", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("fights", "fight_percentage")
