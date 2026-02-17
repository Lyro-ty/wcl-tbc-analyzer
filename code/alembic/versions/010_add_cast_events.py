"""add cast_events table

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
    op.create_table(
        "cast_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger, nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("target_name", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_cast_events_fight_player_ts",
        "cast_events",
        ["fight_id", "player_name", "timestamp_ms"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cast_events_fight_player_ts", table_name="cast_events"
    )
    op.drop_table("cast_events")
