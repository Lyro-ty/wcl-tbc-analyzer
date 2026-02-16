"""add speed_rankings table

Revision ID: 002
Revises: 001
Create Date: 2026-02-16

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "speed_rankings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("report_code", sa.String(50), nullable=False),
        sa.Column("fight_id", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("guild_name", sa.String(200), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_speed_rankings_encounter_rank",
        "speed_rankings",
        ["encounter_id", "rank_position"],
    )


def downgrade() -> None:
    op.drop_index("ix_speed_rankings_encounter_rank", table_name="speed_rankings")
    op.drop_table("speed_rankings")
