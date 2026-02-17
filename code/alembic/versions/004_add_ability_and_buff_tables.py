"""add ability_metrics and buff_uptimes tables

Revision ID: 004
Revises: 003
Create Date: 2026-02-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ability_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("metric_type", sa.String(20), nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("total", sa.BigInteger, server_default="0"),
        sa.Column("hit_count", sa.Integer, server_default="0"),
        sa.Column("crit_count", sa.Integer, server_default="0"),
        sa.Column("crit_pct", sa.Float, server_default="0.0"),
        sa.Column("pct_of_total", sa.Float, server_default="0.0"),
    )
    op.create_index(
        "ix_ability_metrics_fight_player",
        "ability_metrics",
        ["fight_id", "player_name"],
    )
    op.create_index(
        "ix_ability_metrics_spell_type",
        "ability_metrics",
        ["spell_id", "metric_type"],
    )

    op.create_table(
        "buff_uptimes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("metric_type", sa.String(20), nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("uptime_pct", sa.Float, server_default="0.0"),
        sa.Column("stack_count", sa.Float, server_default="0.0"),
    )
    op.create_index(
        "ix_buff_uptimes_fight_player",
        "buff_uptimes",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_buff_uptimes_fight_player", table_name="buff_uptimes")
    op.drop_table("buff_uptimes")
    op.drop_index("ix_ability_metrics_spell_type", table_name="ability_metrics")
    op.drop_index("ix_ability_metrics_fight_player", table_name="ability_metrics")
    op.drop_table("ability_metrics")
