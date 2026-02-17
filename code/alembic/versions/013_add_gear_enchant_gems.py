"""add enchant and gem columns to gear_snapshots

Revision ID: 013
Revises: 012
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gear_snapshots",
        sa.Column("permanent_enchant", sa.Integer, nullable=True),
    )
    op.add_column(
        "gear_snapshots",
        sa.Column("temporary_enchant", sa.Integer, nullable=True),
    )
    op.add_column(
        "gear_snapshots",
        sa.Column("gems_json", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("gear_snapshots", "gems_json")
    op.drop_column("gear_snapshots", "temporary_enchant")
    op.drop_column("gear_snapshots", "permanent_enchant")
