"""add resource_snapshots and cast_events tables

Revision ID: 012
Revises: 011
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "resource_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("min_value", sa.Integer, server_default="0"),
        sa.Column("max_value", sa.Integer, server_default="0"),
        sa.Column("avg_value", sa.Float, server_default="0.0"),
        sa.Column("time_at_zero_ms", sa.BigInteger, server_default="0"),
        sa.Column("time_at_zero_pct", sa.Float, server_default="0.0"),
        sa.Column("samples_json", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_resource_snapshots_fight_player",
        "resource_snapshots",
        ["fight_id", "player_name"],
    )

    op.create_table(
        "cast_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger, nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("target_name", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_cast_events_fight_player",
        "cast_events",
        ["fight_id", "player_name"],
    )
    op.create_index(
        "ix_cast_events_fight_spell",
        "cast_events",
        ["fight_id", "spell_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cast_events_fight_spell", table_name="cast_events")
    op.drop_index("ix_cast_events_fight_player", table_name="cast_events")
    op.drop_table("cast_events")
    op.drop_index(
        "ix_resource_snapshots_fight_player",
        table_name="resource_snapshots",
    )
    op.drop_table("resource_snapshots")
