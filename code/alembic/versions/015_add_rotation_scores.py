"""add rotation_scores table

Revision ID: 015
Revises: 014
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rotation_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "fight_id", sa.Integer,
            sa.ForeignKey("fights.id"), nullable=False,
        ),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("spec", sa.String(50), nullable=False),
        sa.Column(
            "score_pct", sa.Float,
            nullable=False, server_default="0.0",
        ),
        sa.Column(
            "rules_checked", sa.Integer,
            nullable=False, server_default="0",
        ),
        sa.Column(
            "rules_passed", sa.Integer,
            nullable=False, server_default="0",
        ),
        sa.Column("violations_json", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_rotation_scores_fight_player",
        "rotation_scores",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rotation_scores_fight_player",
        table_name="rotation_scores",
    )
    op.drop_table("rotation_scores")
