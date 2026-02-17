"""add performance indexes

Revision ID: 003
Revises: 002
Create Date: 2026-02-16

"""
from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # fight_performances — most queried table, every tool call touches it
    op.create_index(
        "ix_fight_performances_fight_id",
        "fight_performances",
        ["fight_id"],
    )
    op.create_index(
        "ix_fight_performances_player_name",
        "fight_performances",
        ["player_name"],
    )
    op.create_index(
        "ix_fight_performances_class_spec",
        "fight_performances",
        ["player_class", "player_spec"],
    )

    # fights — filtered by report_code and encounter_id in nearly every query
    op.create_index(
        "ix_fights_report_code",
        "fights",
        ["report_code"],
    )
    op.create_index(
        "ix_fights_encounter_id",
        "fights",
        ["encounter_id"],
    )

    # top_rankings — filtered by (encounter_id, class, spec) in compare/rankings queries
    op.create_index(
        "ix_top_rankings_encounter_class_spec",
        "top_rankings",
        ["encounter_id", "class", "spec"],
    )


def downgrade() -> None:
    op.drop_index("ix_top_rankings_encounter_class_spec", table_name="top_rankings")
    op.drop_index("ix_fights_encounter_id", table_name="fights")
    op.drop_index("ix_fights_report_code", table_name="fights")
    op.drop_index("ix_fight_performances_class_spec", table_name="fight_performances")
    op.drop_index("ix_fight_performances_player_name", table_name="fight_performances")
    op.drop_index("ix_fight_performances_fight_id", table_name="fight_performances")
