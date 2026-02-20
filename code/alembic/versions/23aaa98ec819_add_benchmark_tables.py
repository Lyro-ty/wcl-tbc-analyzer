"""add benchmark tables

Revision ID: 23aaa98ec819
Revises: 016
Create Date: 2026-02-20

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "23aaa98ec819"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "watched_guilds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("guild_name", sa.String, nullable=False),
        sa.Column("wcl_guild_id", sa.Integer, nullable=False),
        sa.Column("server_slug", sa.String, nullable=False),
        sa.Column("server_region", sa.String(2), nullable=False),
        sa.Column(
            "added_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "is_active", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.UniqueConstraint(
            "guild_name", "server_slug", "server_region", name="uq_watched_guild"
        ),
    )

    op.create_table(
        "benchmark_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_code", sa.String, nullable=False, unique=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column(
            "encounter_id",
            sa.Integer,
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("guild_name", sa.String, nullable=True),
        sa.Column(
            "ingested_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_benchmark_reports_source", "benchmark_reports", ["source"])

    op.create_table(
        "encounter_benchmarks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "encounter_id",
            sa.Integer,
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("computed_at", sa.DateTime, nullable=False),
        sa.Column("benchmarks", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("encounter_benchmarks")
    op.drop_index("ix_benchmark_reports_source", table_name="benchmark_reports")
    op.drop_table("benchmark_reports")
    op.drop_table("watched_guilds")
