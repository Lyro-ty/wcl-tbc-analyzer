"""add death_details table

Revision ID: 005
Revises: 004
Create Date: 2026-02-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "death_details",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("death_index", sa.Integer, nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger, nullable=False),
        sa.Column("killing_blow_ability", sa.String(200), nullable=False),
        sa.Column("killing_blow_source", sa.String(200), nullable=False),
        sa.Column("damage_taken_total", sa.BigInteger, server_default="0"),
        sa.Column("events_json", sa.Text, nullable=False),
    )
    op.create_index(
        "ix_death_details_fight_player",
        "death_details",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_death_details_fight_player", table_name="death_details")
    op.drop_table("death_details")
