"""add cast_metrics table

Revision ID: 006
Revises: 005
Create Date: 2026-02-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cast_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("total_casts", sa.Integer, server_default="0"),
        sa.Column("casts_per_minute", sa.Float, server_default="0.0"),
        sa.Column("gcd_uptime_pct", sa.Float, server_default="0.0"),
        sa.Column("active_time_ms", sa.BigInteger, server_default="0"),
        sa.Column("downtime_ms", sa.BigInteger, server_default="0"),
        sa.Column("longest_gap_ms", sa.BigInteger, server_default="0"),
        sa.Column("longest_gap_at_ms", sa.BigInteger, server_default="0"),
        sa.Column("avg_gap_ms", sa.Float, server_default="0.0"),
        sa.Column("gap_count", sa.Integer, server_default="0"),
    )
    op.create_index(
        "ix_cast_metrics_fight_player",
        "cast_metrics",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_cast_metrics_fight_player", table_name="cast_metrics")
    op.drop_table("cast_metrics")
