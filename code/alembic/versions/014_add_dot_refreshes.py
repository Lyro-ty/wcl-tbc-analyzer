"""add dot_refreshes table

Revision ID: 014
Revises: 013
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dot_refreshes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("total_refreshes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("early_refreshes", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "early_refresh_pct", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column(
            "avg_remaining_ms", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column(
            "clipped_ticks_est", sa.Integer,
            nullable=False, server_default="0",
        ),
    )
    op.create_index(
        "ix_dot_refreshes_fight_player",
        "dot_refreshes",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_dot_refreshes_fight_player",
        table_name="dot_refreshes",
    )
    op.drop_table("dot_refreshes")
