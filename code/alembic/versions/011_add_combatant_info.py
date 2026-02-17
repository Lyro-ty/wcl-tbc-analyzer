"""add fight_consumables and gear_snapshots tables

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
        "fight_consumables",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("active", sa.Boolean, server_default="true"),
    )
    op.create_index(
        "ix_fight_consumables_fight_player",
        "fight_consumables",
        ["fight_id", "player_name"],
    )

    op.create_table(
        "gear_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer, sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("slot", sa.Integer, nullable=False),
        sa.Column("item_id", sa.Integer, nullable=False),
        sa.Column("item_level", sa.Integer, server_default="0"),
    )
    op.create_index(
        "ix_gear_snapshots_fight_player",
        "gear_snapshots",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_gear_snapshots_fight_player", table_name="gear_snapshots")
    op.drop_table("gear_snapshots")
    op.drop_index("ix_fight_consumables_fight_player", table_name="fight_consumables")
    op.drop_table("fight_consumables")
