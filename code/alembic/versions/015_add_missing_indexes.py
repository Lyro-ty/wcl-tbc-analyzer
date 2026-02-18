"""add missing indexes

Revision ID: 015
Revises: 014
Create Date: 2026-02-18

"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_speed_rankings_encounter_id",
        "speed_rankings",
        ["encounter_id"],
    )
    op.create_index(
        "ix_fight_performances_my_char",
        "fight_performances",
        ["is_my_character"],
        postgresql_where=text("is_my_character = true"),
    )
    op.create_index(
        "ix_reports_start_time",
        "reports",
        ["start_time"],
    )


def downgrade() -> None:
    op.drop_index("ix_reports_start_time", table_name="reports")
    op.drop_index("ix_fight_performances_my_char", table_name="fight_performances")
    op.drop_index("ix_speed_rankings_encounter_id", table_name="speed_rankings")
