"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-15

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "encounters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("zone_id", sa.Integer(), nullable=False),
        sa.Column("zone_name", sa.String(200), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "my_characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("server_slug", sa.String(100), nullable=False),
        sa.Column("server_region", sa.String(10), nullable=False),
        sa.Column("character_class", sa.String(50), nullable=False),
        sa.Column("spec", sa.String(50), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "server_slug", "server_region"),
    )

    op.create_table(
        "reports",
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("guild_name", sa.String(200), nullable=True),
        sa.Column("guild_id", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.BigInteger(), nullable=False),
        sa.Column("end_time", sa.BigInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "fights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("report_code", sa.String(50), nullable=False),
        sa.Column("fight_id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.BigInteger(), nullable=False),
        sa.Column("end_time", sa.BigInteger(), nullable=False),
        sa.Column(
            "duration_ms", sa.BigInteger(),
            sa.Computed("end_time - start_time"), nullable=False,
        ),
        sa.Column("kill", sa.Boolean(), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["report_code"], ["reports.code"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_code", "fight_id"),
    )

    op.create_table(
        "fight_performances",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fight_id", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("player_class", sa.String(50), nullable=False),
        sa.Column("player_spec", sa.String(50), nullable=False),
        sa.Column("player_server", sa.String(100), nullable=False),
        sa.Column("total_damage", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("dps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_healing", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("hps", sa.Float(), nullable=False, server_default="0"),
        sa.Column("parse_percentile", sa.Float(), nullable=True),
        sa.Column("ilvl_parse_percentile", sa.Float(), nullable=True),
        sa.Column("deaths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("interrupts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("dispels", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("item_level", sa.Float(), nullable=True),
        sa.Column("is_my_character", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["fight_id"], ["fights.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "top_rankings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("class", sa.String(50), nullable=False),
        sa.Column("spec", sa.String(50), nullable=False),
        sa.Column("metric", sa.String(20), nullable=False),
        sa.Column("rank_position", sa.Integer(), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("player_server", sa.String(100), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("report_code", sa.String(50), nullable=False),
        sa.Column("fight_id", sa.Integer(), nullable=False),
        sa.Column("guild_name", sa.String(200), nullable=True),
        sa.Column("item_level", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "progression_snapshots",
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("encounter_id", sa.Integer(), nullable=False),
        sa.Column("best_parse", sa.Float(), nullable=True),
        sa.Column("median_parse", sa.Float(), nullable=True),
        sa.Column("best_dps", sa.Float(), nullable=True),
        sa.Column("median_dps", sa.Float(), nullable=True),
        sa.Column("kill_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_deaths", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["my_characters.id"]),
        sa.ForeignKeyConstraint(["encounter_id"], ["encounters.id"]),
        sa.PrimaryKeyConstraint("time", "character_id", "encounter_id"),
    )


def downgrade() -> None:
    op.drop_table("progression_snapshots")
    op.drop_table("top_rankings")
    op.drop_table("fight_performances")
    op.drop_table("fights")
    op.drop_table("reports")
    op.drop_table("my_characters")
    op.drop_table("encounters")
