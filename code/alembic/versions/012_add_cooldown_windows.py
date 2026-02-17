"""add cooldown_windows table

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
        "cooldown_windows",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("spell_id", sa.Integer, nullable=False),
        sa.Column("window_start_ms", sa.BigInteger, nullable=False),
        sa.Column("window_end_ms", sa.BigInteger, nullable=False),
        sa.Column(
            "window_damage", sa.BigInteger,
            nullable=False, server_default="0",
        ),
        sa.Column(
            "window_dps", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column(
            "baseline_dps", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column(
            "dps_gain_pct", sa.Float,
            nullable=False, server_default="0.0",
        ),
    )
    op.create_index(
        "ix_cooldown_windows_fight_player",
        "cooldown_windows",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cooldown_windows_fight_player",
        table_name="cooldown_windows",
    )
    op.drop_table("cooldown_windows")
