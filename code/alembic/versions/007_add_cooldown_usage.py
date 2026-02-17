"""add cooldown_usage table

Revision ID: 007
Revises: 006
Create Date: 2026-02-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cooldown_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("cooldown_sec", sa.Integer, nullable=False),
        sa.Column("times_used", sa.Integer, server_default="0"),
        sa.Column("max_possible_uses", sa.Integer, server_default="0"),
        sa.Column("first_use_ms", sa.BigInteger, nullable=True),
        sa.Column("last_use_ms", sa.BigInteger, nullable=True),
        sa.Column("efficiency_pct", sa.Float, server_default="0.0"),
    )
    op.create_index(
        "ix_cooldown_usage_fight_player",
        "cooldown_usage",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_cooldown_usage_fight_player", table_name="cooldown_usage")
    op.drop_table("cooldown_usage")
