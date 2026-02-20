"""add benchmark FK and composite indexes

Revision ID: 018
Revises: 23aaa98ec819
Create Date: 2026-02-20

"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "018"
down_revision: str | None = "23aaa98ec819"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Delete orphaned benchmark_reports not referencing a valid report
    op.execute(
        text(
            "DELETE FROM benchmark_reports "
            "WHERE report_code NOT IN (SELECT code FROM reports)"
        )
    )

    # Add FK: benchmark_reports.report_code → reports.code
    op.create_foreign_key(
        "fk_benchmark_reports_report_code",
        "benchmark_reports",
        "reports",
        ["report_code"],
        ["code"],
        ondelete="CASCADE",
    )

    # Add composite index on fights for report+encounter+kill lookups
    op.create_index(
        "ix_fights_report_encounter_kill",
        "fights",
        ["report_code", "encounter_id", "kill"],
    )

    # Add composite index on fight_performances for fight+player lookups
    op.create_index(
        "ix_fight_performances_fight_player",
        "fight_performances",
        ["fight_id", "player_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_fight_performances_fight_player", "fight_performances")
    op.drop_index("ix_fights_report_encounter_kill", "fights")
    op.drop_constraint(
        "fk_benchmark_reports_report_code", "benchmark_reports", type_="foreignkey"
    )
