# Benchmark Pipeline: Auto-Ingest Top Players & Guilds

**Date:** 2026-02-19
**Status:** Design approved

## Goal

Build an automated pipeline that ingests reports from the best players and guilds on fresh.warcraftlogs.com, computes structured performance benchmarks per encounter, and exposes them to the AI agent for comparison-based analysis and proactive coaching.

When analyzing a player's raid, the agent should:
- Compare execution against what top guilds/players achieve (deaths, cooldown timing, composition)
- Proactively coach players on what to improve based on concrete benchmark gaps
- Reference specific numbers ("top Destro Locks average 1420 DPS with 91% GCD uptime on Gruul")

## Architecture Overview

```
[Speed Rankings] ──┐
                   ├──→ Discover Reports ──→ Ingest Reports ──→ Compute Benchmarks ──→ encounter_benchmarks
[Watched Guilds] ──┘         │                    │                     │
                        (deduplicate)      (existing pipeline:     (SQL aggregation
                                           ingest_report() with    over existing
                                           --with-tables           tables)
                                           --with-events)
```

Three new DB tables, one new pipeline module, two new agent tools, two new CLI scripts, seven new API endpoints. No new infrastructure — reuses existing ingestion pipeline and DB schema.

## 1. Fresh WCL Support

Switch default WCL API URLs to fresh.warcraftlogs.com. Same OAuth credentials work for both sites.

**Config changes** (`config.py`):
```python
class WCLConfig:
    api_url: str = "https://fresh.warcraftlogs.com/api/v2/client"
    oauth_url: str = "https://fresh.warcraftlogs.com/oauth/token"
```

Already configurable via `WCL__API_URL` / `WCL__OAUTH_URL` env vars. No client code changes needed — `WCLClient` and `WCLAuth` already accept URL parameters.

## 2. New DB Tables

### `watched_guilds`

Manual guild watchlist for tracking top guilds.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, auto-increment |
| `guild_name` | String | NOT NULL, unique |
| `server_slug` | String | NOT NULL |
| `server_region` | String(2) | NOT NULL ("US"/"EU") |
| `added_at` | DateTime | NOT NULL, default utcnow |
| `is_active` | Boolean | NOT NULL, default true |

### `benchmark_reports`

Tracks which top reports have been ingested for benchmarks to avoid re-ingestion.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, auto-increment |
| `report_code` | String | NOT NULL, unique |
| `source` | String | NOT NULL ("speed_ranking" / "watched_guild") |
| `encounter_id` | Integer | FK → encounters, nullable |
| `guild_name` | String | nullable |
| `ingested_at` | DateTime | NOT NULL, default utcnow |

### `encounter_benchmarks`

Pre-computed aggregate benchmarks per encounter. Uses a JSON column for flexibility.

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | Integer | PK, auto-increment |
| `encounter_id` | Integer | FK → encounters, unique |
| `sample_size` | Integer | NOT NULL |
| `computed_at` | DateTime | NOT NULL |
| `benchmarks` | JSON | NOT NULL |

**Benchmark JSON structure:**

```python
{
    "kill": {
        "avg_duration_ms": 245000,
        "median_duration_ms": 240000,
        "fastest_duration_ms": 198000,
    },
    "deaths": {
        "avg_per_kill": 0.8,
        "pct_zero_death_kills": 0.6,
    },
    "composition": {
        "avg_healers": 2.3,
        "avg_tanks": 2.0,
        "avg_dps": 5.7,
        "common_specs": [
            {"class": "Warlock", "spec": "Destruction", "frequency": 0.85},
            ...
        ],
    },
    "by_spec": {
        "Warlock_Destruction": {
            "avg_dps": 1420,
            "median_dps": 1380,
            "p75_dps": 1520,
            "avg_gcd_uptime": 0.91,
            "avg_cpm": 28.5,
            "top_abilities": [
                {"name": "Shadow Bolt", "avg_damage_pct": 0.62},
                {"name": "Immolate", "avg_damage_pct": 0.15},
                ...
            ],
            "avg_buff_uptimes": {
                "Curse of the Elements": 0.95,
                ...
            },
            "avg_cooldown_efficiency": {
                "Infernal": {"avg_times_used": 1.2, "avg_efficiency": 0.85},
                ...
            },
        },
        ...
    },
    "consumables": {
        "flask_rate": 0.95,
        "food_rate": 0.98,
        "oil_rate": 0.88,
        "weapon_stone_rate": 0.72,
    },
    "cooldowns": {
        "bloodlust_timing_pct": [0.0, 0.15, 0.60],  # timestamps as % of fight
    },
}
```

## 3. Benchmark Pipeline Module

New file: `pipeline/benchmarks.py`

### Step 1: Discover reports

Two sources merged and deduplicated by report code:

1. **Speed rankings** — query `speed_rankings` table, take top N report codes per encounter (default 10). Already populated by `pull-speed-rankings`.
2. **Watched guilds** — query WCL `GUILD_REPORTS` GraphQL for each active guild in `watched_guilds`, filter to P1 zone IDs (1047, 1048).

### Step 2: Ingest reports

For each discovered report code not already in `benchmark_reports`:
- Call existing `ingest_report(wcl, session, report_code, with_tables=True, with_events=True)`
- This populates all existing tables: fights, fight_performances, ability_metrics, buff_uptimes, cast_events, cast_metrics, cooldown_usage, cancelled_casts, fight_consumables, gear_snapshots, resource_snapshots, death_details
- Insert a `benchmark_reports` row with source and guild info

Reuses the entire existing ingestion pipeline. No new WCL API parsing code.

### Step 3: Compute benchmarks

For each encounter, aggregate across all fights from benchmark reports:

| Metric | Source table | Aggregation |
|--------|-------------|-------------|
| Kill duration | `fights` | avg, median, min |
| Deaths per kill | `fight_performances` | avg deaths, % zero-death |
| Per-spec DPS/HPS | `fight_performances` | avg, median, p75 grouped by class+spec |
| GCD uptime + CPM | `cast_metrics` | avg per spec |
| Top abilities | `ability_metrics` | avg damage_pct per ability per spec |
| Buff uptimes | `buff_uptimes` | avg uptime per buff per spec |
| Cooldown efficiency | `cooldown_usage` | avg times_used, avg efficiency per ability per spec |
| Consumable rates | `fight_consumables` | % of players with each type |
| Composition | `fight_performances` | avg count per role, spec frequency |

All queries join through `benchmark_reports.report_code → fights.report_code` to scope to benchmark data only.

### Step 4: Upsert benchmarks

One row per encounter via `session.merge()`. Stores the computed JSON + sample_size + timestamp.

### Functions

```python
async def discover_benchmark_reports(
    wcl: WCLClient,
    session: AsyncSession,
    encounter_ids: list[int] | None = None,
    max_reports_per_encounter: int = 10,
) -> list[dict]:
    """Discover top report codes from speed rankings + watched guilds."""

async def ingest_benchmark_reports(
    wcl: WCLClient,
    session: AsyncSession,
    reports: list[dict],
) -> dict:
    """Ingest discovered reports using existing pipeline. Returns {ingested, skipped, errors}."""

async def compute_encounter_benchmarks(
    session: AsyncSession,
    encounter_ids: list[int] | None = None,
) -> dict:
    """Compute aggregates from ingested benchmark data. Returns {computed, skipped}."""

async def run_benchmark_pipeline(
    wcl: WCLClient,
    session: AsyncSession,
    encounter_ids: list[int] | None = None,
    max_reports_per_encounter: int = 10,
    compute_only: bool = False,
    force: bool = False,
) -> dict:
    """Full pipeline: discover → ingest → compute. Returns combined stats."""
```

## 4. Agent Tools

Two new tools in `agent/tools/player_tools.py` (or a new `benchmark_tools.py`):

### `get_encounter_benchmarks`

```python
@db_tool
async def get_encounter_benchmarks(session, encounter_name: str) -> str:
    """Get performance benchmarks for an encounter computed from top guild kills.
    Returns kill stats, death rates, composition, consumable rates, and cooldown timing.
    Use this to establish what 'good' looks like before analyzing a player."""
```

Returns the full benchmark JSON formatted as readable text.

### `get_spec_benchmark`

```python
@db_tool
async def get_spec_benchmark(
    session, encounter_name: str, class_name: str, spec_name: str
) -> str:
    """Get spec-specific performance targets for an encounter.
    Returns DPS target, GCD uptime target, top abilities, buff uptimes,
    and cooldown efficiency from top players of that spec."""
```

Returns just the `by_spec` slice for the requested class+spec.

### Prompt updates (`agent/prompts.py`)

**SYSTEM_PROMPT** — add tools to the tool list:
```
- get_encounter_benchmarks(encounter_name): Performance benchmarks from top guild kills
- get_spec_benchmark(encounter_name, class_name, spec_name): Spec-specific performance targets
```

**ANALYSIS_PROMPT** — add new section at the top:
```
## Benchmark Comparison
Before analyzing performance, retrieve encounter benchmarks via get_encounter_benchmarks
and spec-specific targets via get_spec_benchmark. Compare the player's metrics against
these targets. Flag areas where the player is significantly below benchmark (>10% gap)
as priority improvements. Frame recommendations in terms of what top players achieve:
"Top Destruction Warlocks average 91% GCD uptime on Gruul — yours was 82%, suggesting
9% DPS upside from reducing downtime."
```

## 5. CLI Scripts

### `pull-benchmarks`

New entry point registered in pyproject.toml.

```
pull-benchmarks                              # Full pipeline: discover → ingest → compute
pull-benchmarks --compute-only               # Recompute from existing ingested data
pull-benchmarks --encounter "Gruul"          # Single encounter
pull-benchmarks --zone-id 1048              # Single zone
pull-benchmarks --max-reports 10            # Reports per encounter (default 10)
pull-benchmarks --force                     # Re-ingest already-tracked reports
```

### `manage-watched-guilds`

New entry point registered in pyproject.toml.

```
manage-watched-guilds --add "APES" --server whitemane --region US
manage-watched-guilds --list
manage-watched-guilds --remove "APES"
manage-watched-guilds --deactivate "APES"
```

## 6. API Endpoints

New route file: `api/routes/data/benchmarks.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/data/benchmarks` | List all encounter benchmarks (summary) |
| `GET` | `/api/data/benchmarks/{encounter}` | Full benchmarks for an encounter |
| `GET` | `/api/data/benchmarks/{encounter}/{class}/{spec}` | Spec-specific benchmark |
| `POST` | `/api/data/benchmarks/refresh` | Trigger benchmark pipeline (1hr cooldown) |
| `GET` | `/api/data/watched-guilds` | List watched guilds |
| `POST` | `/api/data/watched-guilds` | Add a watched guild |
| `DELETE` | `/api/data/watched-guilds/{id}` | Remove a watched guild |

## 7. Auto-Refresh Scheduling

Extend `AutoIngestService` in `pipeline/auto_ingest.py` with a second timer:

```python
AUTO_INGEST__BENCHMARK_ENABLED: bool = True
AUTO_INGEST__BENCHMARK_INTERVAL_DAYS: int = 7
```

Every N days, the service runs `run_benchmark_pipeline()`. Uses the same backoff and error tracking infrastructure. Independent of the guild report polling timer.

## 8. Rate Limit Budget

With `--with-tables --with-events`, each report costs ~5-8 WCL API calls:
- 1 call for report fights
- 1 call for report rankings
- 1-2 calls for table data (damage + healing)
- 2-4 calls for events (deaths, casts, resources, combatant info)

At 10 reports per encounter x 13 encounters = 130 reports = ~800-1040 API calls.
WCL allows 3600 points/hour. Full refresh fits within one rate limit window.

Sequential ingestion with existing `RateLimiter` handles pacing automatically.

## 9. Migration

Single Alembic migration adding the three new tables. No changes to existing tables.

## 10. Implementation Order

1. Alembic migration (3 new tables)
2. Config changes (Fresh WCL URLs, benchmark auto-refresh settings)
3. DB models (WatchedGuild, BenchmarkReport, EncounterBenchmark)
4. DB queries (`db/queries/benchmark.py` — discovery + aggregation queries)
5. Pipeline module (`pipeline/benchmarks.py`)
6. CLI scripts (`scripts/pull_benchmarks.py`, `scripts/manage_watched_guilds.py`)
7. Agent tools (`agent/tools/benchmark_tools.py`)
8. Agent prompt updates
9. API endpoints (`api/routes/data/benchmarks.py`)
10. Auto-refresh integration in `auto_ingest.py`
11. Tests throughout
