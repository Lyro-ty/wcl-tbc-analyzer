"""add cancelled_casts table

Revision ID: 009
Revises: 008
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cancelled_casts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("total_begins", sa.Integer, server_default="0"),
        sa.Column("total_completions", sa.Integer, server_default="0"),
        sa.Column("cancel_count", sa.Integer, server_default="0"),
        sa.Column("cancel_pct", sa.Float, server_default="0.0"),
        sa.Column("top_cancelled_json", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_cancelled_casts_fight_player",
        "cancelled_casts",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_cancelled_casts_fight_player", table_name="cancelled_casts")
    op.drop_table("cancelled_casts")
