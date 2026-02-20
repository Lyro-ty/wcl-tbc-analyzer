"""backfill healer hps from dps column

Revision ID: 016
Revises: 015
Create Date: 2026-02-19

"""
from collections.abc import Sequence

from sqlalchemy import text

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        text(
            "UPDATE fight_performances "
            "SET hps = dps, dps = 0.0 "
            "WHERE player_spec IN ('Holy', 'Discipline', 'Restoration') "
            "AND dps > 0.0 AND hps = 0.0"
        )
    )


def downgrade() -> None:
    op.execute(
        text(
            "UPDATE fight_performances "
            "SET dps = hps, hps = 0.0 "
            "WHERE player_spec IN ('Holy', 'Discipline', 'Restoration') "
            "AND hps > 0.0 AND dps = 0.0"
        )
    )
