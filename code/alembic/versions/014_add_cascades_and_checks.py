"""add cascade deletes and check constraints

Revision ID: 014
Revises: 013
Create Date: 2026-02-17

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, column, referred_table.referred_column)
_FK_CASCADES = [
    ("fights", "report_code", "reports.code"),
    ("fights", "encounter_id", "encounters.id"),
    ("fight_performances", "fight_id", "fights.id"),
    ("ability_metrics", "fight_id", "fights.id"),
    ("buff_uptimes", "fight_id", "fights.id"),
    ("death_details", "fight_id", "fights.id"),
    ("cast_events", "fight_id", "fights.id"),
    ("cast_metrics", "fight_id", "fights.id"),
    ("cooldown_usage", "fight_id", "fights.id"),
    ("cancelled_casts", "fight_id", "fights.id"),
    ("resource_snapshots", "fight_id", "fights.id"),
    ("fight_consumables", "fight_id", "fights.id"),
    ("gear_snapshots", "fight_id", "fights.id"),
    ("top_rankings", "encounter_id", "encounters.id"),
    ("speed_rankings", "encounter_id", "encounters.id"),
    ("progression_snapshots", "character_id", "my_characters.id"),
    ("progression_snapshots", "encounter_id", "encounters.id"),
]

# (table, constraint_name, sqltext)
_CHECK_CONSTRAINTS = [
    (
        "fight_performances",
        "ck_fp_parse_pct",
        "parse_percentile IS NULL OR "
        "(parse_percentile >= 0 AND parse_percentile <= 100)",
    ),
    (
        "fight_performances",
        "ck_fp_ilvl_parse_pct",
        "ilvl_parse_percentile IS NULL OR "
        "(ilvl_parse_percentile >= 0 AND ilvl_parse_percentile <= 100)",
    ),
    ("fight_performances", "ck_fp_dps_pos", "dps >= 0"),
    (
        "cast_metrics",
        "ck_cm_gcd_pct",
        "gcd_uptime_pct >= 0 AND gcd_uptime_pct <= 100",
    ),
    (
        "buff_uptimes",
        "ck_bu_uptime_pct",
        "uptime_pct >= 0 AND uptime_pct <= 100",
    ),
    (
        "cooldown_usage",
        "ck_cu_eff_pct",
        "efficiency_pct >= 0 AND efficiency_pct <= 100",
    ),
    (
        "cancelled_casts",
        "ck_cc_cancel_pct",
        "cancel_pct >= 0 AND cancel_pct <= 100",
    ),
    (
        "resource_snapshots",
        "ck_rs_zero_pct",
        "time_at_zero_pct >= 0 AND time_at_zero_pct <= 100",
    ),
]


def upgrade() -> None:
    # Replace all FK constraints with CASCADE DELETE versions
    for table, column, referent in _FK_CASCADES:
        constraint_name = f"{table}_{column}_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table,
            referent.split(".")[0],  # referred table
            [column],
            [referent.split(".")[1]],  # referred column
            ondelete="CASCADE",
        )

    # Add CHECK constraints on bounded numeric columns
    for table, name, sqltext in _CHECK_CONSTRAINTS:
        op.create_check_constraint(name, table, sa.text(sqltext))


def downgrade() -> None:
    # Remove CHECK constraints
    for table, name, _sqltext in reversed(_CHECK_CONSTRAINTS):
        op.drop_constraint(name, table, type_="check")

    # Restore original FK constraints without CASCADE
    for table, column, referent in reversed(_FK_CASCADES):
        constraint_name = f"{table}_{column}_fkey"
        op.drop_constraint(constraint_name, table, type_="foreignkey")
        op.create_foreign_key(
            constraint_name,
            table,
            referent.split(".")[0],
            [column],
            [referent.split(".")[1]],
        )
