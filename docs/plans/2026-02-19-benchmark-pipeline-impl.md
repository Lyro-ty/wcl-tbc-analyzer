# Benchmark Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated pipeline that ingests top player/guild reports from fresh.warcraftlogs.com, computes structured performance benchmarks per encounter, and exposes them to the AI agent for comparison-based analysis and proactive coaching.

**Architecture:** Reuses the existing ingestion pipeline (`ingest_report()` with `ingest_tables=True, ingest_events=True`) to pull full data for top-ranked kills. A new `benchmarks.py` pipeline module computes aggregates over existing tables (`fight_performances`, `cast_metrics`, `buff_uptimes`, `ability_metrics`, `cooldown_usage`, `fight_consumables`) and stores them in a JSON column on `encounter_benchmarks`. Two new agent tools query these benchmarks. A weekly auto-refresh timer extends the existing `AutoIngestService`.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, Alembic, FastAPI, LangGraph, argparse, pydantic-settings v2

**Design doc:** `docs/plans/2026-02-19-benchmark-pipeline-design.md`

---

## Task 1: Switch WCL URLs to Fresh

Switch default WCL API endpoints from `warcraftlogs.com` to `fresh.warcraftlogs.com`.

**Files:**
- Modify: `code/shukketsu/config.py:10-11`

**Step 1: Update defaults**

In `config.py`, change the two URL defaults in `WCLConfig`:

```python
class WCLConfig(BaseModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    api_url: str = "https://fresh.warcraftlogs.com/api/v2/client"
    oauth_url: str = "https://fresh.warcraftlogs.com/oauth/token"
```

**Step 2: Commit**

```bash
git add code/shukketsu/config.py
git commit -m "feat: switch WCL API defaults to fresh.warcraftlogs.com"
```

---

## Task 2: Alembic Migration — 3 New Tables

Create a migration adding `watched_guilds`, `benchmark_reports`, and `encounter_benchmarks`.

**Files:**
- Create: `code/alembic/versions/<hash>_add_benchmark_tables.py`

**Step 1: Generate migration**

```bash
cd /home/lyro/nvidia-workbench/wcl-tbc-analyzer
alembic revision -m "add benchmark tables"
```

**Step 2: Write migration**

```python
"""add benchmark tables

Revision ID: <auto>
"""

from alembic import op

import sqlalchemy as sa

# revision identifiers
revision = "<auto>"
down_revision = "2b19c872c9d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "watched_guilds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("guild_name", sa.String, nullable=False),
        sa.Column("wcl_guild_id", sa.Integer, nullable=False),
        sa.Column("server_slug", sa.String, nullable=False),
        sa.Column("server_region", sa.String(2), nullable=False),
        sa.Column("added_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("guild_name", "server_slug", "server_region",
                            name="uq_watched_guild"),
    )

    op.create_table(
        "benchmark_reports",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_code", sa.String, nullable=False, unique=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("encounter_id", sa.Integer,
                  sa.ForeignKey("encounters.id", ondelete="CASCADE"), nullable=True),
        sa.Column("guild_name", sa.String, nullable=True),
        sa.Column("ingested_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_benchmark_reports_source", "benchmark_reports", ["source"])

    op.create_table(
        "encounter_benchmarks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("encounter_id", sa.Integer,
                  sa.ForeignKey("encounters.id", ondelete="CASCADE"),
                  nullable=False, unique=True),
        sa.Column("sample_size", sa.Integer, nullable=False),
        sa.Column("computed_at", sa.DateTime, nullable=False),
        sa.Column("benchmarks", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("encounter_benchmarks")
    op.drop_table("benchmark_reports")
    op.drop_table("watched_guilds")
```

**Step 3: Run migration**

```bash
alembic upgrade head
```

**Step 4: Commit**

```bash
git add code/alembic/versions/
git commit -m "feat: add benchmark tables migration (watched_guilds, benchmark_reports, encounter_benchmarks)"
```

---

## Task 3: ORM Models

Add three new SQLAlchemy models to `db/models.py`.

**Files:**
- Modify: `code/shukketsu/db/models.py`

**Step 1: Write failing test**

Create `code/tests/db/test_benchmark_models.py`:

```python
"""Tests for benchmark ORM models."""

from datetime import datetime, timezone

from shukketsu.db.models import (
    BenchmarkReport,
    EncounterBenchmark,
    WatchedGuild,
)


class TestWatchedGuild:
    def test_create(self):
        g = WatchedGuild(
            guild_name="APES",
            wcl_guild_id=12345,
            server_slug="whitemane",
            server_region="US",
        )
        assert g.guild_name == "APES"
        assert g.wcl_guild_id == 12345
        assert g.is_active is True

    def test_defaults(self):
        g = WatchedGuild(
            guild_name="Test", wcl_guild_id=1,
            server_slug="s", server_region="US",
        )
        assert g.is_active is True


class TestBenchmarkReport:
    def test_create(self):
        r = BenchmarkReport(
            report_code="abc123",
            source="speed_ranking",
            encounter_id=50649,
            guild_name="APES",
        )
        assert r.report_code == "abc123"
        assert r.source == "speed_ranking"

    def test_watched_guild_source(self):
        r = BenchmarkReport(
            report_code="xyz789",
            source="watched_guild",
            guild_name="Progress",
        )
        assert r.source == "watched_guild"
        assert r.encounter_id is None


class TestEncounterBenchmark:
    def test_create(self):
        b = EncounterBenchmark(
            encounter_id=50649,
            sample_size=10,
            computed_at=datetime.now(timezone.utc),
            benchmarks={"kill": {"avg_duration_ms": 245000}},
        )
        assert b.encounter_id == 50649
        assert b.benchmarks["kill"]["avg_duration_ms"] == 245000
```

**Step 2: Run test to verify it fails**

```bash
pytest code/tests/db/test_benchmark_models.py -v
```

Expected: FAIL — `ImportError: cannot import name 'WatchedGuild'`

**Step 3: Add models to `db/models.py`**

Add after the `SpeedRanking` class (before `ProgressionSnapshot`):

```python
class WatchedGuild(Base):
    __tablename__ = "watched_guilds"
    __table_args__ = (
        UniqueConstraint(
            "guild_name", "server_slug", "server_region",
            name="uq_watched_guild",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_name: Mapped[str] = mapped_column(String, nullable=False)
    wcl_guild_id: Mapped[int] = mapped_column(Integer, nullable=False)
    server_slug: Mapped[str] = mapped_column(String, nullable=False)
    server_region: Mapped[str] = mapped_column(String(2), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class BenchmarkReport(Base):
    __tablename__ = "benchmark_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_code: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    encounter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("encounters.id", ondelete="CASCADE"), nullable=True
    )
    guild_name: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )


class EncounterBenchmark(Base):
    __tablename__ = "encounter_benchmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    encounter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("encounters.id", ondelete="CASCADE"),
        nullable=False, unique=True,
    )
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    benchmarks: Mapped[dict] = mapped_column(JSON, nullable=False)
```

Ensure these imports are present at the top of `db/models.py`: `JSON`, `func`, `UniqueConstraint` (check existing imports and add only what's missing).

**Step 4: Run tests**

```bash
pytest code/tests/db/test_benchmark_models.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/db/models.py code/tests/db/test_benchmark_models.py
git commit -m "feat: add WatchedGuild, BenchmarkReport, EncounterBenchmark ORM models"
```

---

## Task 4: Config — Benchmark Settings

Add `BenchmarkConfig` to settings for auto-refresh and pipeline defaults.

**Files:**
- Modify: `code/shukketsu/config.py`
- Test: `code/tests/test_config.py` (if exists, otherwise create)

**Step 1: Write failing test**

Create `code/tests/test_benchmark_config.py`:

```python
"""Tests for benchmark config."""

from shukketsu.config import BenchmarkConfig


class TestBenchmarkConfig:
    def test_defaults(self):
        cfg = BenchmarkConfig()
        assert cfg.enabled is True
        assert cfg.refresh_interval_days == 7
        assert cfg.max_reports_per_encounter == 10
        assert cfg.zone_ids == []

    def test_custom_values(self):
        cfg = BenchmarkConfig(
            enabled=False,
            refresh_interval_days=3,
            max_reports_per_encounter=5,
            zone_ids=[1047],
        )
        assert cfg.enabled is False
        assert cfg.refresh_interval_days == 3
        assert cfg.max_reports_per_encounter == 5
        assert cfg.zone_ids == [1047]
```

**Step 2: Run test to verify it fails**

```bash
pytest code/tests/test_benchmark_config.py -v
```

Expected: FAIL — `ImportError: cannot import name 'BenchmarkConfig'`

**Step 3: Add config**

In `config.py`, add after `AutoIngestConfig`:

```python
class BenchmarkConfig(BaseModel):
    enabled: bool = True
    refresh_interval_days: int = 7
    max_reports_per_encounter: int = 10
    zone_ids: list[int] = []  # Empty = all zones
```

And add to `Settings`:

```python
class Settings(BaseSettings):
    # ... existing fields ...
    benchmark: BenchmarkConfig = BenchmarkConfig()
```

**Step 4: Run tests**

```bash
pytest code/tests/test_benchmark_config.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/config.py code/tests/test_benchmark_config.py
git commit -m "feat: add BenchmarkConfig to settings"
```

---

## Task 5: Benchmark SQL Queries

Create `db/queries/benchmark.py` with discovery and aggregation queries.

**Files:**
- Create: `code/shukketsu/db/queries/benchmark.py`
- Modify: `code/shukketsu/db/queries/__init__.py` (add import)

**Step 1: Create query module**

Create `code/shukketsu/db/queries/benchmark.py`:

```python
"""Benchmark SQL queries — discovery and aggregation.

Used by: pipeline/benchmarks.py, agent/tools/benchmark_tools.py,
         api/routes/data/benchmarks.py
"""

from sqlalchemy import text

__all__ = [
    "SPEED_RANKING_REPORT_CODES",
    "EXISTING_BENCHMARK_CODES",
    "BENCHMARK_KILL_STATS",
    "BENCHMARK_SPEC_DPS",
    "BENCHMARK_SPEC_GCD",
    "BENCHMARK_SPEC_ABILITIES",
    "BENCHMARK_SPEC_BUFFS",
    "BENCHMARK_SPEC_COOLDOWNS",
    "BENCHMARK_CONSUMABLE_RATES",
    "BENCHMARK_COMPOSITION",
    "GET_ENCOUNTER_BENCHMARK",
    "BENCHMARK_DEATHS",
]


# -- Discovery queries --

SPEED_RANKING_REPORT_CODES = text("""
    SELECT DISTINCT sr.report_code, sr.encounter_id, sr.guild_name
    FROM speed_rankings sr
    WHERE (:encounter_id IS NULL OR sr.encounter_id = :encounter_id)
    ORDER BY sr.report_code
""")

EXISTING_BENCHMARK_CODES = text("""
    SELECT report_code FROM benchmark_reports
""")


# -- Aggregation queries (scoped to benchmark reports) --

BENCHMARK_KILL_STATS = text("""
    SELECT e.id AS encounter_id, e.name AS encounter_name,
           COUNT(*) AS sample_size,
           ROUND(AVG(f.duration_ms)::numeric, 0) AS avg_duration_ms,
           PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY f.duration_ms) AS median_duration_ms,
           MIN(f.duration_ms) AS fastest_duration_ms
    FROM fights f
    JOIN benchmark_reports br ON br.report_code = f.report_code
    JOIN encounters e ON e.id = f.encounter_id
    WHERE f.kill = true
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY e.id, e.name
    ORDER BY e.id
""")

BENCHMARK_DEATHS = text("""
    SELECT f.encounter_id,
           ROUND(AVG(fp.deaths)::numeric, 2) AS avg_deaths_per_player,
           ROUND(
               COUNT(*) FILTER (WHERE fp.deaths = 0)::numeric
               / NULLIF(COUNT(*), 0), 2
           ) AS pct_zero_death_players
    FROM fight_performances fp
    JOIN fights f ON f.report_code = fp.report_code AND f.fight_id = fp.fight_id
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id
""")

BENCHMARK_SPEC_DPS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           COUNT(*) AS sample_size,
           ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.dps)::numeric, 1)
               AS median_dps,
           ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY fp.dps)::numeric, 1)
               AS p75_dps,
           ROUND(AVG(fp.hps)::numeric, 1) AS avg_hps,
           ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY fp.hps)::numeric, 1)
               AS median_hps
    FROM fight_performances fp
    JOIN fights f ON f.report_code = fp.report_code AND f.fight_id = fp.fight_id
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec
    HAVING COUNT(*) >= 2
    ORDER BY f.encounter_id, avg_dps DESC
""")

BENCHMARK_SPEC_GCD = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           ROUND(AVG(cm.gcd_uptime_pct)::numeric, 1) AS avg_gcd_uptime,
           ROUND(AVG(cm.casts_per_minute)::numeric, 1) AS avg_cpm
    FROM cast_metrics cm
    JOIN fights f ON f.report_code = cm.report_code AND f.fight_id = cm.fight_id
    JOIN fight_performances fp
        ON fp.report_code = cm.report_code
        AND fp.fight_id = cm.fight_id
        AND LOWER(fp.player_name) = LOWER(cm.player_name)
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec
    HAVING COUNT(*) >= 2
""")

BENCHMARK_SPEC_ABILITIES = text("""
    WITH totals AS (
        SELECT am.report_code, am.fight_id, am.player_name,
               SUM(am.total_amount) AS fight_total
        FROM ability_metrics am
        JOIN fights f ON f.report_code = am.report_code AND f.fight_id = am.fight_id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND am.metric_type = 'damage'
          AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
        GROUP BY am.report_code, am.fight_id, am.player_name
    )
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           am.ability_name,
           ROUND(AVG(
               am.total_amount::numeric / NULLIF(t.fight_total, 0)
           ), 3) AS avg_damage_pct,
           ROUND(AVG(am.total_amount)::numeric, 0) AS avg_damage
    FROM ability_metrics am
    JOIN totals t ON t.report_code = am.report_code
        AND t.fight_id = am.fight_id AND t.player_name = am.player_name
    JOIN fights f ON f.report_code = am.report_code AND f.fight_id = am.fight_id
    JOIN fight_performances fp
        ON fp.report_code = am.report_code
        AND fp.fight_id = am.fight_id
        AND LOWER(fp.player_name) = LOWER(am.player_name)
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND am.metric_type = 'damage'
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, am.ability_name
    HAVING AVG(am.total_amount::numeric / NULLIF(t.fight_total, 0)) >= 0.03
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_damage_pct DESC
""")

BENCHMARK_SPEC_BUFFS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           bu.buff_name,
           ROUND(AVG(bu.uptime_pct)::numeric, 1) AS avg_uptime
    FROM buff_uptimes bu
    JOIN fights f ON f.report_code = bu.report_code AND f.fight_id = bu.fight_id
    JOIN fight_performances fp
        ON fp.report_code = bu.report_code
        AND fp.fight_id = bu.fight_id
        AND LOWER(fp.player_name) = LOWER(bu.player_name)
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND bu.uptime_pct >= 10
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, bu.buff_name
    HAVING AVG(bu.uptime_pct) >= 20
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_uptime DESC
""")

BENCHMARK_SPEC_COOLDOWNS = text("""
    SELECT f.encounter_id,
           fp.player_class, fp.player_spec,
           cu.ability_name,
           ROUND(AVG(cu.times_used)::numeric, 1) AS avg_times_used,
           ROUND(AVG(cu.efficiency_pct)::numeric, 1) AS avg_efficiency
    FROM cooldown_usage cu
    JOIN fights f ON f.report_code = cu.report_code AND f.fight_id = cu.fight_id
    JOIN fight_performances fp
        ON fp.report_code = cu.report_code
        AND fp.fight_id = cu.fight_id
        AND LOWER(fp.player_name) = LOWER(cu.player_name)
    JOIN benchmark_reports br ON br.report_code = f.report_code
    WHERE f.kill = true
      AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    GROUP BY f.encounter_id, fp.player_class, fp.player_spec, cu.ability_name
    ORDER BY f.encounter_id, fp.player_class, fp.player_spec, avg_efficiency DESC
""")

BENCHMARK_CONSUMABLE_RATES = text("""
    WITH player_fights AS (
        SELECT DISTINCT fp.report_code, fp.fight_id, fp.player_name
        FROM fight_performances fp
        JOIN fights f ON f.report_code = fp.report_code AND f.fight_id = fp.fight_id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
    ),
    consumable_presence AS (
        SELECT pf.report_code, pf.fight_id, pf.player_name,
               fc.category,
               CASE WHEN fc.id IS NOT NULL THEN 1 ELSE 0 END AS has_consumable
        FROM player_fights pf
        LEFT JOIN fight_consumables fc
            ON fc.report_code = pf.report_code
            AND fc.fight_id = pf.fight_id
            AND LOWER(fc.player_name) = LOWER(pf.player_name)
    )
    SELECT category,
           ROUND(
               SUM(has_consumable)::numeric / NULLIF(COUNT(DISTINCT
                   (report_code, fight_id, player_name)), 0),
               2
           ) AS usage_rate
    FROM consumable_presence
    WHERE category IS NOT NULL
    GROUP BY category
    ORDER BY usage_rate DESC
""")

BENCHMARK_COMPOSITION = text("""
    WITH fight_roles AS (
        SELECT f.encounter_id, fp.report_code, fp.fight_id,
               fp.player_class, fp.player_spec,
               COUNT(*) AS player_count
        FROM fight_performances fp
        JOIN fights f ON f.report_code = fp.report_code AND f.fight_id = fp.fight_id
        JOIN benchmark_reports br ON br.report_code = f.report_code
        WHERE f.kill = true
          AND (:encounter_id IS NULL OR f.encounter_id = :encounter_id)
        GROUP BY f.encounter_id, fp.report_code, fp.fight_id,
                 fp.player_class, fp.player_spec
    )
    SELECT encounter_id, player_class, player_spec,
           ROUND(AVG(player_count)::numeric, 1) AS avg_count,
           COUNT(*) AS appearances
    FROM fight_roles
    GROUP BY encounter_id, player_class, player_spec
    ORDER BY encounter_id, appearances DESC
""")


# -- Read queries --

GET_ENCOUNTER_BENCHMARK = text("""
    SELECT eb.encounter_id, e.name AS encounter_name,
           eb.sample_size, eb.computed_at, eb.benchmarks
    FROM encounter_benchmarks eb
    JOIN encounters e ON e.id = eb.encounter_id
    WHERE e.name ILIKE :encounter_name
    LIMIT 1
""")
```

**Step 2: Update `db/queries/__init__.py`**

Add the import for the new module. Check existing `__init__.py` first — it may just be empty or re-export modules.

**Step 3: Commit**

```bash
git add code/shukketsu/db/queries/benchmark.py code/shukketsu/db/queries/__init__.py
git commit -m "feat: add benchmark SQL queries for discovery and aggregation"
```

---

## Task 6: Benchmark Pipeline Module

The core pipeline: discover top reports, ingest them, compute benchmarks.

**Files:**
- Create: `code/shukketsu/pipeline/benchmarks.py`
- Test: `code/tests/pipeline/test_benchmarks.py`

**Step 1: Write failing tests**

Create `code/tests/pipeline/test_benchmarks.py`:

```python
"""Tests for benchmark pipeline."""

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.benchmarks import (
    BenchmarkResult,
    compute_encounter_benchmarks,
    discover_benchmark_reports,
    ingest_benchmark_reports,
)


def _make_row(**kwargs):
    row = SimpleNamespace(**kwargs)
    row._mapping = kwargs
    return row


class TestDiscoverBenchmarkReports:
    async def test_discovers_from_speed_rankings(self):
        session = AsyncMock()
        # Speed ranking report codes
        speed_result = AsyncMock()
        speed_result.fetchall.return_value = [
            _make_row(report_code="abc", encounter_id=50649, guild_name="APES"),
            _make_row(report_code="def", encounter_id=50649, guild_name="Progress"),
        ]
        # Existing benchmark codes (none)
        existing_result = AsyncMock()
        existing_result.scalars.return_value.all.return_value = []
        # No watched guilds
        guild_result = AsyncMock()
        guild_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[speed_result, existing_result, guild_result]
        )

        reports = await discover_benchmark_reports(session, max_per_encounter=10)
        assert len(reports) == 2
        assert reports[0]["report_code"] == "abc"
        assert reports[0]["source"] == "speed_ranking"

    async def test_deduplicates_existing(self):
        session = AsyncMock()
        speed_result = AsyncMock()
        speed_result.fetchall.return_value = [
            _make_row(report_code="abc", encounter_id=50649, guild_name="APES"),
        ]
        existing_result = AsyncMock()
        existing_result.scalars.return_value.all.return_value = ["abc"]
        guild_result = AsyncMock()
        guild_result.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(
            side_effect=[speed_result, existing_result, guild_result]
        )

        reports = await discover_benchmark_reports(session, max_per_encounter=10)
        assert len(reports) == 0


class TestIngestBenchmarkReports:
    async def test_ingests_new_reports(self):
        session = AsyncMock()
        session.add = MagicMock()  # sync method
        wcl = AsyncMock()

        reports = [
            {"report_code": "abc", "source": "speed_ranking",
             "encounter_id": 50649, "guild_name": "APES"},
        ]

        with patch(
            "shukketsu.pipeline.benchmarks.ingest_report",
            new_callable=AsyncMock,
        ) as mock_ingest:
            mock_ingest.return_value = SimpleNamespace(
                fights=3, performances=30, table_rows=60,
                event_rows=90, snapshots=0, enrichment_errors=[],
            )
            result = await ingest_benchmark_reports(wcl, session, reports)

        assert result["ingested"] == 1
        mock_ingest.assert_called_once()
        session.add.assert_called_once()

    async def test_skips_on_error(self):
        session = AsyncMock()
        session.add = MagicMock()
        wcl = AsyncMock()

        reports = [
            {"report_code": "abc", "source": "speed_ranking",
             "encounter_id": 50649, "guild_name": "APES"},
        ]

        with patch(
            "shukketsu.pipeline.benchmarks.ingest_report",
            new_callable=AsyncMock,
            side_effect=Exception("WCL error"),
        ):
            result = await ingest_benchmark_reports(wcl, session, reports)

        assert result["ingested"] == 0
        assert result["errors"] == 1


class TestComputeEncounterBenchmarks:
    async def test_computes_benchmarks(self):
        session = AsyncMock()
        session.merge = MagicMock()  # sync method

        # Kill stats
        kill_result = AsyncMock()
        kill_result.fetchall.return_value = [
            _make_row(
                encounter_id=50649, encounter_name="Gruul",
                sample_size=10, avg_duration_ms=245000,
                median_duration_ms=240000, fastest_duration_ms=198000,
            ),
        ]
        # Deaths
        death_result = AsyncMock()
        death_result.fetchall.return_value = [
            _make_row(
                encounter_id=50649,
                avg_deaths_per_player=0.3, pct_zero_death_players=0.8,
            ),
        ]
        # Per-spec DPS
        spec_result = AsyncMock()
        spec_result.fetchall.return_value = [
            _make_row(
                encounter_id=50649, player_class="Warlock",
                player_spec="Destruction", sample_size=5,
                avg_dps=1420.0, median_dps=1380.0, p75_dps=1520.0,
                avg_hps=0.0, median_hps=0.0,
            ),
        ]
        # GCD
        gcd_result = AsyncMock()
        gcd_result.fetchall.return_value = [
            _make_row(
                encounter_id=50649, player_class="Warlock",
                player_spec="Destruction",
                avg_gcd_uptime=91.0, avg_cpm=28.5,
            ),
        ]
        # Abilities (empty for simplicity)
        empty_result = AsyncMock()
        empty_result.fetchall.return_value = []
        # Buffs (empty)
        # Cooldowns (empty)
        # Consumables (empty)
        # Composition (empty)

        session.execute = AsyncMock(side_effect=[
            kill_result, death_result, spec_result, gcd_result,
            empty_result, empty_result, empty_result, empty_result, empty_result,
        ])

        result = await compute_encounter_benchmarks(session)

        assert result["computed"] == 1
        session.merge.assert_called_once()
        # Check the merged object
        benchmark = session.merge.call_args[0][0]
        assert benchmark.encounter_id == 50649
        assert benchmark.sample_size == 10
        assert benchmark.benchmarks["kill"]["avg_duration_ms"] == 245000
        assert "Warlock_Destruction" in benchmark.benchmarks["by_spec"]
        spec_data = benchmark.benchmarks["by_spec"]["Warlock_Destruction"]
        assert spec_data["avg_dps"] == 1420.0
        assert spec_data["avg_gcd_uptime"] == 91.0


class TestBenchmarkResult:
    def test_dataclass(self):
        r = BenchmarkResult(discovered=10, ingested=8, computed=5, errors=[])
        assert r.discovered == 10
```

**Step 2: Run test to verify it fails**

```bash
pytest code/tests/pipeline/test_benchmarks.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'shukketsu.pipeline.benchmarks'`

**Step 3: Write implementation**

Create `code/shukketsu/pipeline/benchmarks.py`:

```python
"""Benchmark pipeline — discover top reports, ingest, compute aggregates.

Flow: discover_benchmark_reports → ingest_benchmark_reports → compute_encounter_benchmarks
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from shukketsu.db.models import (
    BenchmarkReport,
    EncounterBenchmark,
    WatchedGuild,
)
from shukketsu.db.queries import benchmark as bq
from shukketsu.pipeline.ingest import ingest_report

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    discovered: int = 0
    ingested: int = 0
    computed: int = 0
    errors: list[str] = field(default_factory=list)


async def discover_benchmark_reports(
    session,
    encounter_id: int | None = None,
    max_per_encounter: int = 10,
) -> list[dict]:
    """Find top report codes from speed rankings + watched guilds."""
    # 1. Speed ranking report codes
    result = await session.execute(
        bq.SPEED_RANKING_REPORT_CODES,
        {"encounter_id": encounter_id},
    )
    speed_rows = result.fetchall()

    # Deduplicate and limit per encounter
    seen_per_encounter: dict[int, int] = {}
    candidates = []
    for row in speed_rows:
        enc_id = row.encounter_id
        count = seen_per_encounter.get(enc_id, 0)
        if count >= max_per_encounter:
            continue
        candidates.append({
            "report_code": row.report_code,
            "source": "speed_ranking",
            "encounter_id": enc_id,
            "guild_name": row.guild_name,
        })
        seen_per_encounter[enc_id] = count + 1

    # 2. Watched guild reports (future — requires WCL API call)
    # For now, watched guilds are used by the separate guild report fetcher
    guild_result = await session.execute(
        select(WatchedGuild).where(WatchedGuild.is_active.is_(True))
    )
    _watched = guild_result.scalars().all()
    # TODO: Fetch guild reports via WCL GUILD_REPORTS query per watched guild
    # and add to candidates with source="watched_guild"

    # 3. Filter out already-ingested reports
    existing_result = await session.execute(bq.EXISTING_BENCHMARK_CODES)
    existing_codes = {r[0] for r in existing_result.fetchall()}

    new_reports = [c for c in candidates if c["report_code"] not in existing_codes]
    logger.info(
        "Discovered %d candidate reports (%d new, %d already ingested)",
        len(candidates), len(new_reports), len(existing_codes),
    )
    return new_reports


async def ingest_benchmark_reports(
    wcl,
    session,
    reports: list[dict],
) -> dict:
    """Ingest discovered reports using the existing pipeline."""
    ingested = 0
    errors = 0

    for report_info in reports:
        code = report_info["report_code"]
        try:
            result = await ingest_report(
                wcl, session, code,
                ingest_tables=True, ingest_events=True,
            )
            session.add(BenchmarkReport(
                report_code=code,
                source=report_info["source"],
                encounter_id=report_info.get("encounter_id"),
                guild_name=report_info.get("guild_name"),
            ))
            await session.commit()
            ingested += 1
            logger.info(
                "Ingested benchmark report %s: %d fights, %d performances",
                code, result.fights, result.performances,
            )
        except Exception:
            logger.exception("Failed to ingest benchmark report %s", code)
            await session.rollback()
            errors += 1

    return {"ingested": ingested, "errors": errors}


async def compute_encounter_benchmarks(
    session,
    encounter_id: int | None = None,
) -> dict:
    """Compute aggregate benchmarks from ingested benchmark data."""
    params = {"encounter_id": encounter_id}

    # Fetch all aggregation data
    kill_rows = (await session.execute(bq.BENCHMARK_KILL_STATS, params)).fetchall()
    death_rows = (await session.execute(bq.BENCHMARK_DEATHS, params)).fetchall()
    spec_rows = (await session.execute(bq.BENCHMARK_SPEC_DPS, params)).fetchall()
    gcd_rows = (await session.execute(bq.BENCHMARK_SPEC_GCD, params)).fetchall()
    ability_rows = (await session.execute(bq.BENCHMARK_SPEC_ABILITIES, params)).fetchall()
    buff_rows = (await session.execute(bq.BENCHMARK_SPEC_BUFFS, params)).fetchall()
    cd_rows = (await session.execute(bq.BENCHMARK_SPEC_COOLDOWNS, params)).fetchall()
    consumable_rows = (await session.execute(
        bq.BENCHMARK_CONSUMABLE_RATES, params
    )).fetchall()
    comp_rows = (await session.execute(bq.BENCHMARK_COMPOSITION, params)).fetchall()

    # Index supplementary data by (encounter_id, class, spec)
    death_by_enc = {r.encounter_id: r for r in death_rows}

    def _spec_key(row):
        return (row.encounter_id, row.player_class, row.player_spec)

    gcd_by_spec = {_spec_key(r): r for r in gcd_rows}

    abilities_by_spec: dict[tuple, list] = {}
    for r in ability_rows:
        abilities_by_spec.setdefault(_spec_key(r), []).append(r)

    buffs_by_spec: dict[tuple, list] = {}
    for r in buff_rows:
        buffs_by_spec.setdefault(_spec_key(r), []).append(r)

    cds_by_spec: dict[tuple, list] = {}
    for r in cd_rows:
        cds_by_spec.setdefault(_spec_key(r), []).append(r)

    comp_by_enc: dict[int, list] = {}
    for r in comp_rows:
        comp_by_enc.setdefault(r.encounter_id, []).append(r)

    computed = 0
    for kill_row in kill_rows:
        enc_id = kill_row.encounter_id

        # Build per-spec data
        by_spec = {}
        for sr in spec_rows:
            if sr.encounter_id != enc_id:
                continue
            key = (enc_id, sr.player_class, sr.player_spec)
            spec_key_str = f"{sr.player_class}_{sr.player_spec}"

            gcd = gcd_by_spec.get(key)
            abilities = abilities_by_spec.get(key, [])
            buffs = buffs_by_spec.get(key, [])
            cds = cds_by_spec.get(key, [])

            by_spec[spec_key_str] = {
                "sample_size": sr.sample_size,
                "avg_dps": float(sr.avg_dps),
                "median_dps": float(sr.median_dps),
                "p75_dps": float(sr.p75_dps),
                "avg_hps": float(sr.avg_hps),
                "median_hps": float(sr.median_hps),
                "avg_gcd_uptime": float(gcd.avg_gcd_uptime) if gcd else None,
                "avg_cpm": float(gcd.avg_cpm) if gcd else None,
                "top_abilities": [
                    {"name": a.ability_name, "avg_damage_pct": float(a.avg_damage_pct)}
                    for a in abilities[:10]
                ],
                "avg_buff_uptimes": {
                    b.buff_name: float(b.avg_uptime) for b in buffs[:15]
                },
                "avg_cooldown_efficiency": {
                    c.ability_name: {
                        "avg_times_used": float(c.avg_times_used),
                        "avg_efficiency": float(c.avg_efficiency),
                    }
                    for c in cds
                },
            }

        # Deaths
        death = death_by_enc.get(enc_id)

        # Consumable rates
        consumable_dict = {
            r.category: float(r.usage_rate) for r in consumable_rows
        }

        # Composition
        comp_list = [
            {
                "class": c.player_class,
                "spec": c.player_spec,
                "avg_count": float(c.avg_count),
                "appearances": c.appearances,
            }
            for c in comp_by_enc.get(enc_id, [])[:20]
        ]

        benchmarks = {
            "kill": {
                "avg_duration_ms": int(kill_row.avg_duration_ms),
                "median_duration_ms": int(kill_row.median_duration_ms),
                "fastest_duration_ms": int(kill_row.fastest_duration_ms),
            },
            "deaths": {
                "avg_deaths_per_player": float(death.avg_deaths_per_player)
                if death else None,
                "pct_zero_death_players": float(death.pct_zero_death_players)
                if death else None,
            },
            "by_spec": by_spec,
            "consumables": consumable_dict,
            "composition": comp_list,
        }

        session.merge(EncounterBenchmark(
            encounter_id=enc_id,
            sample_size=kill_row.sample_size,
            computed_at=datetime.now(timezone.utc),
            benchmarks=benchmarks,
        ))
        await session.commit()
        computed += 1
        logger.info(
            "Computed benchmarks for %s (%d kills, %d specs)",
            kill_row.encounter_name, kill_row.sample_size, len(by_spec),
        )

    return {"computed": computed}


async def run_benchmark_pipeline(
    wcl,
    session,
    encounter_id: int | None = None,
    max_reports_per_encounter: int = 10,
    compute_only: bool = False,
    force: bool = False,
) -> BenchmarkResult:
    """Full pipeline: discover -> ingest -> compute."""
    result = BenchmarkResult()

    if not compute_only:
        # Discover
        reports = await discover_benchmark_reports(
            session,
            encounter_id=encounter_id,
            max_per_encounter=max_reports_per_encounter,
        )
        result.discovered = len(reports)

        # Ingest
        if reports:
            ingest_result = await ingest_benchmark_reports(wcl, session, reports)
            result.ingested = ingest_result["ingested"]
            if ingest_result["errors"]:
                result.errors.append(
                    f"{ingest_result['errors']} reports failed to ingest"
                )

    # Compute
    compute_result = await compute_encounter_benchmarks(session, encounter_id)
    result.computed = compute_result["computed"]

    logger.info(
        "Benchmark pipeline complete: discovered=%d, ingested=%d, computed=%d",
        result.discovered, result.ingested, result.computed,
    )
    return result
```

**Step 4: Run tests**

```bash
pytest code/tests/pipeline/test_benchmarks.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add code/shukketsu/pipeline/benchmarks.py code/tests/pipeline/test_benchmarks.py
git commit -m "feat: add benchmark pipeline — discover, ingest, compute"
```

---

## Task 7: Agent Tools — Benchmark Tools

Two new tools for the agent to query benchmarks.

**Files:**
- Create: `code/shukketsu/agent/tools/benchmark_tools.py`
- Modify: `code/shukketsu/agent/tools/__init__.py`
- Test: `code/tests/agent/test_benchmark_tools.py`

**Step 1: Write failing tests**

Create `code/tests/agent/test_benchmark_tools.py`:

```python
"""Tests for benchmark agent tools."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.agent.tools.benchmark_tools import (
    get_encounter_benchmarks,
    get_spec_benchmark,
)


def _make_row(**kwargs):
    row = SimpleNamespace(**kwargs)
    row._mapping = kwargs
    return row


SAMPLE_BENCHMARKS = {
    "kill": {"avg_duration_ms": 245000, "median_duration_ms": 240000,
             "fastest_duration_ms": 198000},
    "deaths": {"avg_deaths_per_player": 0.3, "pct_zero_death_players": 0.8},
    "by_spec": {
        "Warlock_Destruction": {
            "sample_size": 5, "avg_dps": 1420.0, "median_dps": 1380.0,
            "p75_dps": 1520.0, "avg_hps": 0.0, "median_hps": 0.0,
            "avg_gcd_uptime": 91.0, "avg_cpm": 28.5,
            "top_abilities": [
                {"name": "Shadow Bolt", "avg_damage_pct": 0.62},
            ],
            "avg_buff_uptimes": {"Curse of the Elements": 95.0},
            "avg_cooldown_efficiency": {
                "Infernal": {"avg_times_used": 1.2, "avg_efficiency": 85.0},
            },
        },
    },
    "consumables": {"flask": 0.95, "food": 0.98},
    "composition": [
        {"class": "Warlock", "spec": "Destruction", "avg_count": 2.5,
         "appearances": 10},
    ],
}


class TestGetEncounterBenchmarks:
    async def test_returns_formatted_benchmarks(self):
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = _make_row(
            encounter_id=50649, encounter_name="Gruul the Dragonkiller",
            sample_size=10, computed_at="2026-02-19",
            benchmarks=SAMPLE_BENCHMARKS,
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Gruul"}
            )

        assert "Gruul" in result
        assert "245000" in result or "245.0" in result or "4:05" in result

    async def test_no_data(self):
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_encounter_benchmarks.ainvoke(
                {"encounter_name": "Unknown"}
            )

        assert "No benchmark" in result or "not found" in result.lower()


class TestGetSpecBenchmark:
    async def test_returns_spec_data(self):
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = _make_row(
            encounter_id=50649, encounter_name="Gruul the Dragonkiller",
            sample_size=10, computed_at="2026-02-19",
            benchmarks=SAMPLE_BENCHMARKS,
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke({
                "encounter_name": "Gruul",
                "class_name": "Warlock",
                "spec_name": "Destruction",
            })

        assert "1420" in result
        assert "91" in result  # GCD uptime

    async def test_spec_not_found(self):
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.fetchone.return_value = _make_row(
            encounter_id=50649, encounter_name="Gruul",
            sample_size=10, computed_at="2026-02-19",
            benchmarks=SAMPLE_BENCHMARKS,
        )
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "shukketsu.agent.tool_utils._get_session",
            return_value=mock_session,
        ):
            result = await get_spec_benchmark.ainvoke({
                "encounter_name": "Gruul",
                "class_name": "Mage",
                "spec_name": "Fire",
            })

        assert "No benchmark" in result or "not found" in result.lower()
```

**Step 2: Run test to verify it fails**

```bash
pytest code/tests/agent/test_benchmark_tools.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `code/shukketsu/agent/tools/benchmark_tools.py`:

```python
"""Agent tools for querying encounter benchmarks."""

import logging

from shukketsu.agent.tool_utils import db_tool
from shukketsu.db.queries import benchmark as bq

logger = logging.getLogger(__name__)


def _format_duration(ms: int) -> str:
    """Format milliseconds as M:SS."""
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


def _format_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


@db_tool
async def get_encounter_benchmarks(session, encounter_name: str) -> str:
    """Get performance benchmarks for an encounter computed from top guild kills.
    Returns kill stats, death rates, composition, consumable rates.
    Use this to establish what top players/guilds achieve before analyzing a player."""
    result = await session.execute(
        bq.GET_ENCOUNTER_BENCHMARK,
        {"encounter_name": f"%{encounter_name}%"},
    )
    row = result.fetchone()
    if not row:
        return f"No benchmark data found for '{encounter_name}'. Run pull-benchmarks first."

    b = row.benchmarks
    kill = b.get("kill", {})
    deaths = b.get("deaths", {})
    consumables = b.get("consumables", {})
    composition = b.get("composition", [])

    lines = [
        f"=== Benchmarks for {row.encounter_name} ===",
        f"Sample: {row.sample_size} top kills",
        "",
        "-- Kill Stats --",
        f"  Avg duration: {_format_duration(kill.get('avg_duration_ms', 0))}",
        f"  Median duration: {_format_duration(kill.get('median_duration_ms', 0))}",
        f"  Fastest: {_format_duration(kill.get('fastest_duration_ms', 0))}",
        "",
        "-- Deaths --",
        f"  Avg deaths/player: {deaths.get('avg_deaths_per_player', 'N/A')}",
        f"  Zero-death rate: {_format_pct(deaths.get('pct_zero_death_players'))}",
        "",
    ]

    if consumables:
        lines.append("-- Consumable Usage --")
        for cat, rate in consumables.items():
            lines.append(f"  {cat}: {_format_pct(rate * 100 if rate <= 1 else rate)}")
        lines.append("")

    if composition:
        lines.append("-- Common Specs (top 10) --")
        for c in composition[:10]:
            lines.append(
                f"  {c['class']} {c['spec']}: avg {c['avg_count']} per raid"
                f" ({c['appearances']} appearances)"
            )
        lines.append("")

    # Summarize spec DPS
    by_spec = b.get("by_spec", {})
    if by_spec:
        lines.append("-- Spec DPS Targets --")
        sorted_specs = sorted(
            by_spec.items(), key=lambda x: x[1].get("avg_dps", 0), reverse=True
        )
        for spec_key, data in sorted_specs:
            lines.append(
                f"  {spec_key.replace('_', ' ')}: "
                f"avg {data.get('avg_dps', 0):.0f} DPS, "
                f"GCD {_format_pct(data.get('avg_gcd_uptime'))}, "
                f"CPM {data.get('avg_cpm', 'N/A')}"
            )

    return "\n".join(lines)


@db_tool
async def get_spec_benchmark(
    session,
    encounter_name: str,
    class_name: str,
    spec_name: str,
) -> str:
    """Get spec-specific performance targets for an encounter from top players.
    Returns DPS target, GCD uptime target, top abilities, buff uptimes,
    and cooldown efficiency benchmarks."""
    result = await session.execute(
        bq.GET_ENCOUNTER_BENCHMARK,
        {"encounter_name": f"%{encounter_name}%"},
    )
    row = result.fetchone()
    if not row:
        return f"No benchmark data found for '{encounter_name}'. Run pull-benchmarks first."

    spec_key = f"{class_name}_{spec_name}"
    by_spec = row.benchmarks.get("by_spec", {})
    data = by_spec.get(spec_key)
    if not data:
        available = ", ".join(sorted(by_spec.keys()))
        return (
            f"No benchmark data for {class_name} {spec_name} on {row.encounter_name}. "
            f"Available specs: {available}"
        )

    lines = [
        f"=== {class_name} {spec_name} Benchmarks — {row.encounter_name} ===",
        f"Sample: {data.get('sample_size', 'N/A')} players",
        "",
        "-- Performance Targets --",
        f"  Avg DPS: {data.get('avg_dps', 0):.0f}",
        f"  Median DPS: {data.get('median_dps', 0):.0f}",
        f"  75th percentile DPS: {data.get('p75_dps', 0):.0f}",
    ]

    if data.get("avg_hps"):
        lines.append(f"  Avg HPS: {data['avg_hps']:.0f}")

    lines.extend([
        "",
        "-- Activity --",
        f"  GCD Uptime: {_format_pct(data.get('avg_gcd_uptime'))}",
        f"  Casts/min: {data.get('avg_cpm', 'N/A')}",
    ])

    abilities = data.get("top_abilities", [])
    if abilities:
        lines.extend(["", "-- Top Abilities (% of damage) --"])
        for a in abilities:
            lines.append(f"  {a['name']}: {a['avg_damage_pct'] * 100:.1f}%")

    buffs = data.get("avg_buff_uptimes", {})
    if buffs:
        lines.extend(["", "-- Key Buff Uptimes --"])
        for name, uptime in buffs.items():
            lines.append(f"  {name}: {_format_pct(uptime)}")

    cds = data.get("avg_cooldown_efficiency", {})
    if cds:
        lines.extend(["", "-- Cooldown Efficiency --"])
        for name, cd_data in cds.items():
            lines.append(
                f"  {name}: avg {cd_data['avg_times_used']:.1f} uses, "
                f"{_format_pct(cd_data['avg_efficiency'])} efficiency"
            )

    return "\n".join(lines)
```

**Step 4: Wire into ALL_TOOLS**

In `code/shukketsu/agent/tools/__init__.py`, add the import and list entries:

```python
from shukketsu.agent.tools.benchmark_tools import (
    get_encounter_benchmarks,
    get_spec_benchmark,
)
```

Add to `ALL_TOOLS` list:
```python
    # Benchmark tools (2)
    get_encounter_benchmarks,
    get_spec_benchmark,
```

Add to `__all__`:
```python
    "get_encounter_benchmarks",
    "get_spec_benchmark",
```

**Step 5: Run tests**

```bash
pytest code/tests/agent/test_benchmark_tools.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add code/shukketsu/agent/tools/benchmark_tools.py \
        code/shukketsu/agent/tools/__init__.py \
        code/tests/agent/test_benchmark_tools.py
git commit -m "feat: add get_encounter_benchmarks and get_spec_benchmark agent tools"
```

---

## Task 8: Agent Prompt Updates

Add benchmark tools to the system prompt and a benchmark comparison section to the analysis prompt.

**Files:**
- Modify: `code/shukketsu/agent/prompts.py`

**Step 1: Update SYSTEM_PROMPT**

In the tool list section of `SYSTEM_PROMPT`, add after the existing event-data tools section:

```
### Benchmark tools
- get_encounter_benchmarks(encounter_name): Performance benchmarks from top guild kills — kill stats, death rates, spec DPS targets, consumable rates, composition
- get_spec_benchmark(encounter_name, class_name, spec_name): Spec-specific performance targets — DPS target, GCD uptime, top abilities, buff uptimes, cooldown efficiency
```

**Step 2: Update ANALYSIS_PROMPT**

Add as the first section (before "1. Summary"):

```
## 0. Benchmark Comparison
Before analyzing, retrieve encounter benchmarks via get_encounter_benchmarks and spec targets
via get_spec_benchmark. Compare the player's metrics against these targets:
- Flag areas >10% below benchmark as PRIORITY improvements
- Frame recommendations using concrete numbers: "Top Destruction Warlocks average 91% GCD
  uptime on Gruul — yours was 82%, suggesting ~9% DPS upside from reducing downtime"
- If benchmarks are unavailable, skip this section silently
```

**Step 3: Update ROUTER_PROMPT**

Add `benchmark` to the `general` category examples so benchmark queries route correctly.

**Step 4: Commit**

```bash
git add code/shukketsu/agent/prompts.py
git commit -m "feat: add benchmark tools to agent prompts with benchmark comparison section"
```

---

## Task 9: CLI Scripts

Two new scripts: `pull-benchmarks` and `manage-watched-guilds`.

**Files:**
- Create: `code/shukketsu/scripts/pull_benchmarks.py`
- Create: `code/shukketsu/scripts/manage_watched_guilds.py`
- Modify: `pyproject.toml` (add entry points)
- Test: `code/tests/scripts/test_pull_benchmarks.py`
- Test: `code/tests/scripts/test_manage_watched_guilds.py`

**Step 1: Write failing tests for pull-benchmarks**

Create `code/tests/scripts/test_pull_benchmarks.py`:

```python
"""Tests for pull-benchmarks CLI script."""

from shukketsu.scripts.pull_benchmarks import parse_args


class TestParseArgs:
    def test_defaults(self):
        args = parse_args([])
        assert args.encounter is None
        assert args.zone_id is None
        assert args.max_reports == 10
        assert args.compute_only is False
        assert args.force is False

    def test_compute_only(self):
        args = parse_args(["--compute-only"])
        assert args.compute_only is True

    def test_encounter_filter(self):
        args = parse_args(["--encounter", "Gruul"])
        assert args.encounter == "Gruul"

    def test_max_reports(self):
        args = parse_args(["--max-reports", "5"])
        assert args.max_reports == 5

    def test_zone_id(self):
        args = parse_args(["--zone-id", "1048"])
        assert args.zone_id == 1048

    def test_force(self):
        args = parse_args(["--force"])
        assert args.force is True
```

**Step 2: Write failing tests for manage-watched-guilds**

Create `code/tests/scripts/test_manage_watched_guilds.py`:

```python
"""Tests for manage-watched-guilds CLI script."""

from shukketsu.scripts.manage_watched_guilds import parse_args


class TestParseArgs:
    def test_add(self):
        args = parse_args(["--add", "APES", "--guild-id", "12345",
                           "--server", "whitemane", "--region", "US"])
        assert args.add == "APES"
        assert args.guild_id == 12345
        assert args.server == "whitemane"
        assert args.region == "US"

    def test_list(self):
        args = parse_args(["--list"])
        assert args.list is True

    def test_remove(self):
        args = parse_args(["--remove", "APES"])
        assert args.remove == "APES"

    def test_defaults(self):
        args = parse_args([])
        assert args.add is None
        assert args.list is False
        assert args.remove is None
```

**Step 3: Run tests to verify they fail**

```bash
pytest code/tests/scripts/test_pull_benchmarks.py code/tests/scripts/test_manage_watched_guilds.py -v
```

Expected: FAIL — `ModuleNotFoundError`

**Step 4: Implement pull-benchmarks**

Create `code/shukketsu/scripts/pull_benchmarks.py`:

```python
"""Pull and compute benchmarks from top guild kills."""

import argparse
import asyncio
import logging

from sqlalchemy import select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import Encounter
from shukketsu.pipeline.benchmarks import run_benchmark_pipeline
from shukketsu.wcl.auth import WCLAuth
from shukketsu.wcl.client import WCLClient
from shukketsu.wcl.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pull top guild reports and compute benchmarks"
    )
    parser.add_argument("--encounter", help="Filter by encounter name")
    parser.add_argument("--zone-id", type=int, help="Filter by zone ID")
    parser.add_argument(
        "--max-reports", type=int, default=10,
        help="Max reports per encounter (default: 10)",
    )
    parser.add_argument(
        "--compute-only", action="store_true",
        help="Skip ingestion, recompute from existing data",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-ingest already-tracked reports",
    )
    return parser.parse_args(argv)


async def run(
    encounter: str | None = None,
    zone_id: int | None = None,
    max_reports: int = 10,
    compute_only: bool = False,
    force: bool = False,
) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    # Resolve encounter filter to ID
    encounter_id = None
    if encounter or zone_id:
        async with session_factory() as session:
            query = select(Encounter)
            if encounter:
                query = query.where(Encounter.name.ilike(f"%{encounter}%"))
            if zone_id:
                query = query.where(Encounter.zone_id == zone_id)
            result = await session.execute(query)
            encounters = list(result.scalars().all())

        if not encounters:
            logger.error("No encounters found matching filters")
            await engine.dispose()
            return

        # If filtering by name, use first match
        if encounter and len(encounters) == 1:
            encounter_id = encounters[0].id
        logger.info(
            "Filtered to %d encounters: %s",
            len(encounters),
            ", ".join(e.name for e in encounters),
        )

    if compute_only:
        async with session_factory() as session:
            result = await run_benchmark_pipeline(
                wcl=None, session=session,
                encounter_id=encounter_id,
                compute_only=True,
            )
        await engine.dispose()
        logger.info("Compute-only: %d benchmarks computed", result.computed)
        return

    auth = WCLAuth(
        settings.wcl.client_id,
        settings.wcl.client_secret.get_secret_value(),
        settings.wcl.oauth_url,
    )
    async with (
        WCLClient(auth, RateLimiter(), api_url=settings.wcl.api_url) as wcl,
        session_factory() as session,
    ):
        result = await run_benchmark_pipeline(
            wcl, session,
            encounter_id=encounter_id,
            max_reports_per_encounter=max_reports,
            force=force,
        )

    await engine.dispose()
    logger.info(
        "Done: discovered=%d, ingested=%d, computed=%d, errors=%d",
        result.discovered, result.ingested, result.computed, len(result.errors),
    )
    for err in result.errors:
        logger.error("  %s", err)


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(
        run(
            encounter=args.encounter,
            zone_id=args.zone_id,
            max_reports=args.max_reports,
            compute_only=args.compute_only,
            force=args.force,
        )
    )


if __name__ == "__main__":
    main()
```

**Step 5: Implement manage-watched-guilds**

Create `code/shukketsu/scripts/manage_watched_guilds.py`:

```python
"""Manage watched guilds for benchmark tracking."""

import argparse
import asyncio
import logging

from sqlalchemy import delete, select

from shukketsu.config import get_settings
from shukketsu.db.engine import create_db_engine, create_session_factory
from shukketsu.db.models import WatchedGuild

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage watched guilds")
    parser.add_argument("--add", help="Guild name to add")
    parser.add_argument("--guild-id", type=int, help="WCL guild ID (required for --add)")
    parser.add_argument("--server", help="Server slug (required for --add)")
    parser.add_argument("--region", default="US", help="Region (default: US)")
    parser.add_argument("--list", action="store_true", help="List watched guilds")
    parser.add_argument("--remove", help="Guild name to remove")
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)

    async with session_factory() as session:
        if args.add:
            if not args.guild_id or not args.server:
                logger.error("--guild-id and --server are required with --add")
                await engine.dispose()
                return
            guild = WatchedGuild(
                guild_name=args.add,
                wcl_guild_id=args.guild_id,
                server_slug=args.server,
                server_region=args.region,
            )
            session.add(guild)
            await session.commit()
            logger.info("Added watched guild: %s (ID %d)", args.add, args.guild_id)

        elif args.remove:
            result = await session.execute(
                delete(WatchedGuild).where(
                    WatchedGuild.guild_name.ilike(args.remove)
                )
            )
            await session.commit()
            if result.rowcount:
                logger.info("Removed watched guild: %s", args.remove)
            else:
                logger.warning("Guild not found: %s", args.remove)

        elif args.list:
            result = await session.execute(
                select(WatchedGuild).order_by(WatchedGuild.guild_name)
            )
            guilds = result.scalars().all()
            if not guilds:
                logger.info("No watched guilds configured")
            else:
                for g in guilds:
                    status = "active" if g.is_active else "inactive"
                    logger.info(
                        "  %s (ID %d) — %s-%s [%s]",
                        g.guild_name, g.wcl_guild_id,
                        g.server_slug, g.server_region, status,
                    )

        else:
            logger.info("Use --add, --remove, or --list. See --help.")

    await engine.dispose()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
```

**Step 6: Register entry points in pyproject.toml**

Add after `pull-table-data` line:

```toml
pull-benchmarks = "shukketsu.scripts.pull_benchmarks:main"
manage-watched-guilds = "shukketsu.scripts.manage_watched_guilds:main"
```

**Step 7: Run tests**

```bash
pytest code/tests/scripts/test_pull_benchmarks.py code/tests/scripts/test_manage_watched_guilds.py -v
```

Expected: PASS

**Step 8: Reinstall package**

```bash
pip install --break-system-packages -e ".[dev]"
```

**Step 9: Commit**

```bash
git add code/shukketsu/scripts/pull_benchmarks.py \
        code/shukketsu/scripts/manage_watched_guilds.py \
        code/tests/scripts/test_pull_benchmarks.py \
        code/tests/scripts/test_manage_watched_guilds.py \
        pyproject.toml
git commit -m "feat: add pull-benchmarks and manage-watched-guilds CLI scripts"
```

---

## Task 10: API Endpoints

Benchmark data + watched guild CRUD endpoints.

**Files:**
- Create: `code/shukketsu/api/routes/data/benchmarks.py`
- Modify: `code/shukketsu/api/routes/data/__init__.py`
- Test: `code/tests/api/test_data_benchmarks.py`

**Step 1: Write failing tests**

Create `code/tests/api/test_data_benchmarks.py`:

```python
"""Tests for benchmark API endpoints."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.api.conftest import make_row

SAMPLE_BENCHMARKS = {
    "kill": {"avg_duration_ms": 245000},
    "deaths": {"avg_deaths_per_player": 0.3},
    "by_spec": {"Warlock_Destruction": {"avg_dps": 1420.0}},
    "consumables": {},
    "composition": [],
}


# GET /api/data/benchmarks

async def test_list_benchmarks(client, mock_session):
    mock_result = AsyncMock()
    mock_result.fetchall.return_value = [
        make_row(
            encounter_id=50649, encounter_name="Gruul",
            sample_size=10, computed_at="2026-02-19",
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["encounter_name"] == "Gruul"


async def test_list_benchmarks_empty(client, mock_session):
    mock_result = AsyncMock()
    mock_result.fetchall.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks")
    assert resp.status_code == 200
    assert resp.json() == []


# GET /api/data/benchmarks/{encounter}

async def test_get_benchmark(client, mock_session):
    mock_result = AsyncMock()
    mock_result.fetchone.return_value = make_row(
        encounter_id=50649, encounter_name="Gruul",
        sample_size=10, computed_at="2026-02-19",
        benchmarks=SAMPLE_BENCHMARKS,
    )
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/Gruul")
    assert resp.status_code == 200
    data = resp.json()
    assert data["encounter_name"] == "Gruul"
    assert data["benchmarks"]["kill"]["avg_duration_ms"] == 245000


async def test_get_benchmark_not_found(client, mock_session):
    mock_result = AsyncMock()
    mock_result.fetchone.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/benchmarks/Unknown")
    assert resp.status_code == 404


# GET /api/data/watched-guilds

async def test_list_watched_guilds(client, mock_session):
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [
        SimpleNamespace(
            id=1, guild_name="APES", wcl_guild_id=12345,
            server_slug="whitemane", server_region="US", is_active=True,
        ),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    resp = await client.get("/api/data/watched-guilds")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["guild_name"] == "APES"
```

**Step 2: Run tests to verify they fail**

```bash
pytest code/tests/api/test_data_benchmarks.py -v
```

Expected: FAIL

**Step 3: Implement endpoints**

Create `code/shukketsu/api/routes/data/benchmarks.py`:

```python
"""Benchmark data + watched guild CRUD endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shukketsu.api.deps import cooldown, get_db
from shukketsu.db.models import WatchedGuild
from shukketsu.db.queries import benchmark as bq

logger = logging.getLogger(__name__)
router = APIRouter()


# -- Response models --

class BenchmarkSummary(BaseModel):
    encounter_id: int
    encounter_name: str
    sample_size: int
    computed_at: str


class BenchmarkDetail(BaseModel):
    encounter_id: int
    encounter_name: str
    sample_size: int
    computed_at: str
    benchmarks: dict


class WatchedGuildResponse(BaseModel):
    id: int
    guild_name: str
    wcl_guild_id: int
    server_slug: str
    server_region: str
    is_active: bool


class AddWatchedGuildRequest(BaseModel):
    guild_name: str
    wcl_guild_id: int
    server_slug: str
    server_region: str = "US"


class BenchmarkRefreshResponse(BaseModel):
    discovered: int
    ingested: int
    computed: int
    errors: list[str]


# -- Benchmark endpoints --

BENCHMARKS_LIST = text("""
    SELECT eb.encounter_id, e.name AS encounter_name,
           eb.sample_size, eb.computed_at
    FROM encounter_benchmarks eb
    JOIN encounters e ON e.id = eb.encounter_id
    ORDER BY e.name
""")


@router.get("/benchmarks", response_model=list[BenchmarkSummary])
async def list_benchmarks(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(BENCHMARKS_LIST)
        rows = result.fetchall()
        return [
            BenchmarkSummary(
                encounter_id=r.encounter_id,
                encounter_name=r.encounter_name,
                sample_size=r.sample_size,
                computed_at=str(r.computed_at),
            )
            for r in rows
        ]
    except Exception:
        logger.exception("Failed to list benchmarks")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get("/benchmarks/{encounter}", response_model=BenchmarkDetail)
async def get_benchmark(encounter: str, session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(
            bq.GET_ENCOUNTER_BENCHMARK,
            {"encounter_name": f"%{encounter}%"},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Benchmark not found")
        return BenchmarkDetail(
            encounter_id=row.encounter_id,
            encounter_name=row.encounter_name,
            sample_size=row.sample_size,
            computed_at=str(row.computed_at),
            benchmarks=row.benchmarks,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get benchmark")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.get(
    "/benchmarks/{encounter}/{class_name}/{spec_name}",
    response_model=dict,
)
async def get_spec_benchmark(
    encounter: str, class_name: str, spec_name: str,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            bq.GET_ENCOUNTER_BENCHMARK,
            {"encounter_name": f"%{encounter}%"},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Benchmark not found")

        spec_key = f"{class_name}_{spec_name}"
        spec_data = row.benchmarks.get("by_spec", {}).get(spec_key)
        if not spec_data:
            raise HTTPException(status_code=404, detail="Spec benchmark not found")

        return {"encounter_name": row.encounter_name, "spec": spec_key, **spec_data}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get spec benchmark")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post(
    "/benchmarks/refresh",
    response_model=BenchmarkRefreshResponse,
    dependencies=[cooldown("benchmark_refresh", 3600)],
)
async def refresh_benchmarks(
    zone_id: int | None = None,
    force: bool = False,
    session: AsyncSession = Depends(get_db),
):
    from shukketsu.config import get_settings
    from shukketsu.pipeline.benchmarks import run_benchmark_pipeline
    from shukketsu.wcl.auth import WCLAuth
    from shukketsu.wcl.client import WCLClient
    from shukketsu.wcl.rate_limiter import RateLimiter

    settings = get_settings()
    if not settings.wcl.client_id:
        raise HTTPException(status_code=503, detail="WCL credentials not configured")

    try:
        auth = WCLAuth(
            settings.wcl.client_id,
            settings.wcl.client_secret.get_secret_value(),
            settings.wcl.oauth_url,
        )
        async with WCLClient(auth, RateLimiter(), api_url=settings.wcl.api_url) as wcl:
            result = await run_benchmark_pipeline(
                wcl, session, force=force,
                max_reports_per_encounter=settings.benchmark.max_reports_per_encounter,
            )

        return BenchmarkRefreshResponse(
            discovered=result.discovered,
            ingested=result.ingested,
            computed=result.computed,
            errors=result.errors,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to refresh benchmarks")
        raise HTTPException(status_code=500, detail="Internal server error") from None


# -- Watched guild endpoints --

@router.get("/watched-guilds", response_model=list[WatchedGuildResponse])
async def list_watched_guilds(session: AsyncSession = Depends(get_db)):
    try:
        result = await session.execute(
            select(WatchedGuild).order_by(WatchedGuild.guild_name)
        )
        guilds = result.scalars().all()
        return [
            WatchedGuildResponse(
                id=g.id, guild_name=g.guild_name,
                wcl_guild_id=g.wcl_guild_id,
                server_slug=g.server_slug,
                server_region=g.server_region,
                is_active=g.is_active,
            )
            for g in guilds
        ]
    except Exception:
        logger.exception("Failed to list watched guilds")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.post("/watched-guilds", response_model=WatchedGuildResponse, status_code=201)
async def add_watched_guild(
    body: AddWatchedGuildRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        guild = WatchedGuild(
            guild_name=body.guild_name,
            wcl_guild_id=body.wcl_guild_id,
            server_slug=body.server_slug,
            server_region=body.server_region,
        )
        session.add(guild)
        await session.commit()
        await session.refresh(guild)
        return WatchedGuildResponse(
            id=guild.id, guild_name=guild.guild_name,
            wcl_guild_id=guild.wcl_guild_id,
            server_slug=guild.server_slug,
            server_region=guild.server_region,
            is_active=guild.is_active,
        )
    except Exception:
        logger.exception("Failed to add watched guild")
        raise HTTPException(status_code=500, detail="Internal server error") from None


@router.delete("/watched-guilds/{guild_id}", status_code=204)
async def remove_watched_guild(
    guild_id: int,
    session: AsyncSession = Depends(get_db),
):
    try:
        result = await session.execute(
            select(WatchedGuild).where(WatchedGuild.id == guild_id)
        )
        guild = result.scalar_one_or_none()
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")
        await session.delete(guild)
        await session.commit()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to remove watched guild")
        raise HTTPException(status_code=500, detail="Internal server error") from None
```

**Step 4: Register in data router**

In `code/shukketsu/api/routes/data/__init__.py`, add:

```python
from shukketsu.api.routes.data.benchmarks import router as benchmarks_router
```

And:

```python
router.include_router(benchmarks_router)
```

**Step 5: Run tests**

```bash
pytest code/tests/api/test_data_benchmarks.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add code/shukketsu/api/routes/data/benchmarks.py \
        code/shukketsu/api/routes/data/__init__.py \
        code/tests/api/test_data_benchmarks.py
git commit -m "feat: add benchmark and watched guild API endpoints"
```

---

## Task 11: Auto-Refresh Integration

Extend `AutoIngestService` with a weekly benchmark refresh timer.

**Files:**
- Modify: `code/shukketsu/pipeline/auto_ingest.py`
- Test: `code/tests/pipeline/test_auto_ingest.py` (add benchmark timer tests)

**Step 1: Write failing test**

Add to `code/tests/pipeline/test_auto_ingest.py` (or create if not exists):

```python
"""Tests for benchmark auto-refresh in AutoIngestService."""

from unittest.mock import AsyncMock, MagicMock, patch

from shukketsu.pipeline.auto_ingest import AutoIngestService


class TestBenchmarkAutoRefresh:
    def test_benchmark_config_defaults(self):
        settings = MagicMock()
        settings.benchmark.enabled = True
        settings.benchmark.refresh_interval_days = 7
        settings.auto_ingest.enabled = False

        service = AutoIngestService(
            settings=settings,
            session_factory=AsyncMock(),
            wcl_factory=AsyncMock(),
        )
        assert service._benchmark_enabled is True
        assert service._benchmark_interval_days == 7
```

**Step 2: Add benchmark timer to AutoIngestService**

In `auto_ingest.py`, add to `__init__`:

```python
self._benchmark_enabled = settings.benchmark.enabled
self._benchmark_interval_days = settings.benchmark.refresh_interval_days
self._benchmark_task = None
self._last_benchmark_run = None
```

Add a `_benchmark_loop()` method (similar to `_poll_loop()` but with day-based interval):

```python
async def _benchmark_loop(self) -> None:
    """Weekly benchmark refresh loop."""
    interval = self._benchmark_interval_days * 86400  # days to seconds
    while True:
        await asyncio.sleep(interval)
        try:
            async with self._session_factory() as session:
                async with self._wcl_factory() as wcl:
                    from shukketsu.pipeline.benchmarks import run_benchmark_pipeline
                    result = await run_benchmark_pipeline(
                        wcl, session,
                        max_reports_per_encounter=self._settings.benchmark.max_reports_per_encounter,
                    )
                    logger.info(
                        "Benchmark auto-refresh: discovered=%d, ingested=%d, computed=%d",
                        result.discovered, result.ingested, result.computed,
                    )
            self._last_benchmark_run = datetime.now(timezone.utc)
        except Exception:
            logger.exception("Benchmark auto-refresh failed")
```

Update `start()` to launch the benchmark loop:

```python
async def start(self) -> None:
    # ... existing poll loop start ...
    if self._benchmark_enabled:
        self._benchmark_task = asyncio.create_task(self._benchmark_loop())
        logger.info("Benchmark auto-refresh enabled (every %d days)", self._benchmark_interval_days)
```

Update `stop()` to cancel the benchmark task:

```python
async def stop(self) -> None:
    # ... existing task cancel ...
    if self._benchmark_task:
        self._benchmark_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._benchmark_task
```

Update `get_status()` to include benchmark info:

```python
"benchmark_enabled": self._benchmark_enabled,
"last_benchmark_run": self._last_benchmark_run.isoformat() if self._last_benchmark_run else None,
```

**Step 3: Run tests**

```bash
pytest code/tests/pipeline/test_auto_ingest.py -v
```

Expected: PASS

**Step 4: Commit**

```bash
git add code/shukketsu/pipeline/auto_ingest.py code/tests/pipeline/test_auto_ingest.py
git commit -m "feat: add weekly benchmark auto-refresh to AutoIngestService"
```

---

## Task 12: Run Full Test Suite + Lint

Verify nothing is broken.

**Step 1: Run all tests**

```bash
pytest code/tests/ -v
```

Expected: All tests pass (existing + new)

**Step 2: Run linter**

```bash
ruff check code/
```

Expected: No errors

**Step 3: Fix any issues found**

Address lint errors or test failures. Common issues:
- Missing imports (ruff I rule)
- Line length > 99 chars (ruff E501)
- Unused imports (ruff F401)

**Step 4: Final commit**

```bash
git add -u
git commit -m "fix: address lint and test issues from benchmark pipeline"
```

---

## Task 13: Update CLAUDE.md and Memory

Update project documentation to reflect the new benchmark system.

**Step 1: Update CLAUDE.md**

Add to the "Known issues" or appropriate sections:
- Benchmark pipeline description
- New tables (3)
- New tools (2, total now 32)
- New CLI scripts (2, total now 9)
- New API endpoints (7)

**Step 2: Update memory**

Update `MEMORY.md` with new table count (21), tool count (32), script count (9), endpoint count (~61).

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for benchmark pipeline"
```
