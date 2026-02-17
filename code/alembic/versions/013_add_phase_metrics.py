"""add phase_metrics table

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
    op.create_table(
        "phase_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("phase_name", sa.String(100), nullable=False),
        sa.Column("phase_start_ms", sa.BigInteger, nullable=False),
        sa.Column("phase_end_ms", sa.BigInteger, nullable=False),
        sa.Column(
            "is_downtime", sa.Boolean,
            nullable=False, server_default="false",
        ),
        sa.Column("phase_dps", sa.Float, nullable=True),
        sa.Column("phase_casts", sa.Integer, nullable=True),
        sa.Column("phase_gcd_uptime_pct", sa.Float, nullable=True),
    )
    op.create_index(
        "ix_phase_metrics_fight_player",
        "phase_metrics",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_phase_metrics_fight_player",
        table_name="phase_metrics",
    )
    op.drop_table("phase_metrics")
