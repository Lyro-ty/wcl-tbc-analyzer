"""add resource_snapshots table

Revision ID: 011
Revises: 010
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(20), nullable=False),
        sa.Column("min_value", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_value", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_value", sa.Float, nullable=False, server_default="0.0"),
        sa.Column(
            "time_at_zero_ms", sa.BigInteger,
            nullable=False, server_default="0",
        ),
        sa.Column(
            "time_at_zero_pct", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column("samples_json", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_resource_snapshots_fight_player",
        "resource_snapshots",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_resource_snapshots_fight_player",
        table_name="resource_snapshots",
    )
    op.drop_table("resource_snapshots")
