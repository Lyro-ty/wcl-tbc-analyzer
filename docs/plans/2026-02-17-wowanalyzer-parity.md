# WoWAnalyzer Parity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close all remaining gaps between Shukketsu Raid Analyzer and WoWAnalyzer by building the event pipeline, adding missing DB tables/migrations, implementing all missing backend API routes, consolidating agent tools, and cleaning up dead code.

**Architecture:** Hybrid approach — use WCL `table(dataType: Casts)` and `table(dataType: Deaths)` for summary-level data where sufficient. Use WCL `events()` API for features needing individual timestamps (cast timeline, cooldown windows, DoT refresh analysis, resource changes). New pipeline modules process raw events into derived metric tables. Agent tools consolidated from 26 → ~20 by merging overlapping raid-summary tools and adding the 5 missing analysis tools.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, PostgreSQL 16, Alembic migrations, FastAPI, WCL GraphQL API v2, pytest with AsyncMock

---

## Phase 1: Event Pipeline Foundation (Migrations + Pipeline Modules)

### Task 1: Add `resource_snapshots` and `cast_events` tables via migration

The `resource_snapshots` table is referenced by an orphaned query and frontend type but has no ORM model or migration. The `cast_events` table stores individual cast events needed for cast timeline, rotation scoring, DoT refresh, and cooldown window analysis.

**Files:**
- Create: `code/alembic/versions/012_add_resource_and_cast_events.py`
- Modify: `code/shukketsu/db/models.py`

**Step 1: Write the migration**

```python
"""Add resource_snapshots and cast_events tables.

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa

revision = "012_add_resource_and_cast_events"
down_revision = "011_add_combatant_info"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "resource_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer(), sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("min_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_value", sa.Float(), nullable=False, server_default="0"),
        sa.Column("time_at_zero_ms", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("time_at_zero_pct", sa.Float(), nullable=False, server_default="0"),
        sa.Column("samples_json", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_resource_snapshots_fight_player", "resource_snapshots",
        ["fight_id", "player_name"],
    )

    op.create_table(
        "cast_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("fight_id", sa.Integer(), sa.ForeignKey("fights.id"), nullable=False),
        sa.Column("player_name", sa.String(100), nullable=False),
        sa.Column("timestamp_ms", sa.BigInteger(), nullable=False),
        sa.Column("spell_id", sa.Integer(), nullable=False),
        sa.Column("ability_name", sa.String(200), nullable=False),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("target_name", sa.String(100), nullable=True),
    )
    op.create_index(
        "ix_cast_events_fight_player", "cast_events",
        ["fight_id", "player_name"],
    )
    op.create_index(
        "ix_cast_events_fight_spell", "cast_events",
        ["fight_id", "spell_id"],
    )


def downgrade() -> None:
    op.drop_table("cast_events")
    op.drop_table("resource_snapshots")
```

**Step 2: Add ORM models**

Add to `db/models.py`:

```python
class ResourceSnapshot(Base):
    __tablename__ = "resource_snapshots"
    __table_args__ = (
        Index("ix_resource_snapshots_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    min_value: Mapped[int] = mapped_column(Integer, default=0)
    max_value: Mapped[int] = mapped_column(Integer, default=0)
    avg_value: Mapped[float] = mapped_column(Float, default=0.0)
    time_at_zero_ms: Mapped[int] = mapped_column(BigInteger, default=0)
    time_at_zero_pct: Mapped[float] = mapped_column(Float, default=0.0)
    samples_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="resource_snapshots")


class CastEvent(Base):
    __tablename__ = "cast_events"
    __table_args__ = (
        Index("ix_cast_events_fight_player", "fight_id", "player_name"),
        Index("ix_cast_events_fight_spell", "fight_id", "spell_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    timestamp_ms: Mapped[int] = mapped_column(BigInteger)
    spell_id: Mapped[int] = mapped_column(Integer)
    ability_name: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(20))
    target_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    fight: Mapped["Fight"] = relationship(back_populates="cast_events")
```

Add relationship to Fight model: `cast_events`, `resource_snapshots`.

**Step 3: Write test for ORM model**

Add to `code/tests/db/test_models.py` tests verifying the new models can be instantiated with expected fields.

**Step 4: Run tests**

Run: `python3 -m pytest code/tests/db/test_models.py -v`

**Step 5: Commit**

```
feat: add resource_snapshots and cast_events tables (migration 012)
```

---

### Task 2: Build death events pipeline module

Fetches WCL `Deaths` events and populates the existing `death_details` table (which currently has an ORM model but no pipeline writer).

**Files:**
- Create: `code/shukketsu/pipeline/death_events.py`
- Create: `code/tests/pipeline/test_death_events.py`

**Step 1: Write failing test**

Test `parse_death_events()` transforms WCL Death event JSON into `DeathDetail` ORM objects with correct fields (killing_blow_ability, killing_blow_source, damage_taken_total, events_json with last 5 damage events, timestamp_ms).

Test data shape (from WCL Deaths event API):
```python
{
    "timestamp": 45000,
    "sourceID": 1,
    "source": {"name": "Patchwerk", "id": 1},
    "targetID": 5,
    "target": {"name": "Lyro", "id": 5},
    "ability": {"name": "Hateful Strike", "guid": 28308},
    "killingBlow": True,
    "fight": 3,
    "hitPoints": 0,
    "events": [
        {"timestamp": 43000, "source": {"name": "Patchwerk"}, "ability": {"name": "Melee"},
         "amount": 4000, "type": "damage"},
        {"timestamp": 44000, "source": {"name": "Patchwerk"}, "ability": {"name": "Hateful Strike"},
         "amount": 8000, "type": "damage"},
    ]
}
```

**Step 2: Implement `parse_death_events()` and `ingest_death_events_for_fight()`**

```python
async def ingest_death_events_for_fight(wcl, session, report_code, fight):
    """Fetch Death events for a fight and store death_details rows."""
```

Key logic:
- WCL Death events come with nested `events[]` (the damage leading to death)
- Extract killing blow from the `ability` field on the death event itself
- Extract `source.name` as killing_blow_source
- Sum `amount` from damage events for `damage_taken_total`
- Store last 5 damage events as JSON in `events_json`
- Delete existing death_details for the fight first (idempotent)

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add death events pipeline (WCL Deaths → death_details)
```

---

### Task 3: Build cast events pipeline module

Fetches WCL `Casts` events and populates the `cast_events` table. Also computes derived metrics into `cast_metrics`, `cancelled_casts`, and `cooldown_usage`.

**Files:**
- Create: `code/shukketsu/pipeline/cast_events.py`
- Modify: `code/tests/pipeline/test_cast_events.py` (already exists, extend it)

**Step 1: Write failing tests**

Test `parse_cast_events()` transforms WCL Cast events into `CastEvent` rows.
Test `compute_cast_metrics()` derives GCD uptime, CPM, gaps from a list of cast events.
Test `compute_cooldown_usage()` derives cooldown efficiency from cast events matching `CLASSIC_COOLDOWNS`.
Test `compute_cancelled_casts()` counts begincast vs cast events to find cancels.

WCL Casts event shape:
```python
# begincast event
{"timestamp": 1000, "type": "begincast", "sourceID": 5,
 "ability": {"name": "Frostbolt", "guid": 25304},
 "targetID": 10, "target": {"name": "Patchwerk"}}
# cast (success) event
{"timestamp": 2500, "type": "cast", "sourceID": 5,
 "ability": {"name": "Frostbolt", "guid": 25304},
 "targetID": 10, "target": {"name": "Patchwerk"}}
```

**Step 2: Implement the pipeline**

`ingest_cast_events_for_fight(wcl, session, report_code, fight, actors)`:
1. Fetch all Casts events via `fetch_all_events(data_type="Casts")`
2. Map `sourceID` → player name using the actors dict from `REPORT_FIGHTS`
3. Store individual `CastEvent` rows
4. Compute `CastMetric` per player: GCD uptime = active_time / fight_duration, CPM, gaps
5. Compute `CooldownUsage` per player per cooldown: match spell_ids against `CLASSIC_COOLDOWNS`, count uses, max_possible = floor(fight_duration / cooldown_sec) + 1, efficiency_pct
6. Compute `CancelledCast` per player: count begincast vs cast for same spell, diff = cancels
7. Delete existing rows for idempotency, insert new ones

GCD uptime calculation:
- Sort casts by timestamp
- Assume 1.5s GCD (base) — for simplicity, all classes
- `active_time` = sum of min(1500, gap_to_next_cast) for each cast
- `downtime` = fight_duration - active_time
- `gcd_uptime_pct` = active_time / fight_duration * 100
- Track gaps > 2500ms as significant gaps

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add cast events pipeline (WCL Casts → cast_events + derived metrics)
```

---

### Task 4: Build resource events pipeline module

Fetches WCL resource data and populates `resource_snapshots`.

**Files:**
- Create: `code/shukketsu/pipeline/resource_events.py`
- Create: `code/tests/pipeline/test_resource_events.py`

**Step 1: Write failing tests**

Test `compute_resource_snapshots()` takes WCL resource change events and produces per-player per-resource-type snapshots with min/max/avg and time-at-zero.

**Step 2: Implement**

Two approaches depending on WCL API response:
- **Option A (preferred)**: Use `REPORT_TABLE` with `dataType: "Resources"` if WCL supports it for Classic. This gives summary-level resource data per player.
- **Option B**: Use `REPORT_EVENTS` with `dataType: "ResourceChange"` for individual events. Track running resource level per player, compute min/max/avg/time_at_zero.

Resource types: `Mana` (0), `Rage` (1), `Energy` (3) — WCL uses numeric resource type IDs.

`ingest_resource_data_for_fight(wcl, session, report_code, fight, actors)`:
1. Try fetching via table API first (less API cost)
2. If not available, fall back to events API
3. Delete existing resource_snapshots for the fight
4. Insert new ResourceSnapshot rows

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add resource events pipeline (WCL Resources → resource_snapshots)
```

---

### Task 5: Wire event pipeline into ingest flow

Connect all new pipeline modules into the main `ingest_report()` flow and the `--with-events` flag.

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py`
- Modify: `code/tests/pipeline/test_ingest.py`

**Step 1: Write failing test**

Test that `ingest_report(ingest_events=True)` calls the death, cast, and resource pipeline modules for each fight.

**Step 2: Implement**

In `ingest_report()`, when `ingest_events=True`:
1. Call `ingest_death_events_for_fight()` for each fight
2. Call `ingest_cast_events_for_fight()` for each fight (needs actors dict from REPORT_FIGHTS)
3. Call `ingest_resource_data_for_fight()` for each fight
4. Count total event rows added to `IngestResult.event_rows`

The actors dict maps sourceID → player name and is already available from the `REPORT_FIGHTS` query (masterData.actors). Pass it through to the event pipeline.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: wire death/cast/resource event pipeline into ingest flow
```

---

## Phase 2: Missing Backend API Routes

### Task 6: Add events-available endpoint

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/api/models.py`

**Step 1: Add SQL query**

```python
EVENT_DATA_EXISTS = text("""
    SELECT EXISTS(
        SELECT 1 FROM death_details dd
        JOIN fights f ON dd.fight_id = f.id
        WHERE f.report_code = :report_code
    ) OR EXISTS(
        SELECT 1 FROM cast_metrics cm
        JOIN fights f ON cm.fight_id = f.id
        WHERE f.report_code = :report_code
    ) AS has_data
""")
```

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/events-available")
async def events_available(report_code: str):
    # Returns {"has_data": bool}
```

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add events-available API endpoint
```

---

### Task 7: Add cast-timeline endpoint

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/api/models.py`

**Step 1: Add SQL query**

```python
CAST_TIMELINE = text("""
    SELECT ce.player_name, ce.timestamp_ms, ce.spell_id,
           ce.ability_name, ce.event_type, ce.target_name
    FROM cast_events ce
    JOIN fights f ON ce.fight_id = f.id
    WHERE f.report_code = :report_code
      AND f.fight_id = :fight_id
      AND ce.player_name = :player_name
    ORDER BY ce.timestamp_ms ASC
""")
```

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/fights/{fight_id}/cast-timeline/{player}")
async def fight_cast_timeline(report_code: str, fight_id: int, player: str):
    # Returns list[CastEventResponse]
```

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add cast-timeline API endpoint
```

---

### Task 8: Add cooldown-windows endpoint

Computes DPS during cooldown activation windows vs baseline DPS.

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/api/models.py`

**Step 1: Add response model**

```python
class CooldownWindowResponse(BaseModel):
    player_name: str
    ability_name: str
    spell_id: int
    window_start_ms: int
    window_end_ms: int
    window_damage: int
    window_dps: float
    baseline_dps: float
    dps_gain_pct: float
```

**Step 2: Add route**

This requires joining `cooldown_usage` (for when CDs were used) with `ability_metrics` or calculating from `cast_events`. Since we have `first_use_ms` and `last_use_ms` in `cooldown_usage` and cooldown `duration_sec` in constants, we can estimate windows. The actual damage during windows requires either:
- Summing damage from `cast_events` during the window timestamps, OR
- Approximating from overall DPS and the cooldown's damage multiplier

**Pragmatic approach**: Use cast_events timestamps to identify cooldown windows, sum damage from cast_events within each window, compare to fight-wide DPS from fight_performances.

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add cooldown-windows API endpoint
```

---

### Task 9: Add resources endpoint

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/api/models.py`

**Step 1: Add response model**

```python
class ResourceSnapshotResponse(BaseModel):
    player_name: str
    resource_type: str
    min_value: int
    max_value: int
    avg_value: float
    time_at_zero_ms: int
    time_at_zero_pct: float
    samples_json: str | None
```

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/fights/{fight_id}/resources/{player}")
async def fight_resources(report_code: str, fight_id: int, player: str):
    # Uses RESOURCE_USAGE query (already exists in queries.py)
```

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add resources API endpoint
```

---

### Task 10: Add dot-refreshes endpoint

Computes DoT refresh analysis from cast_events — early refreshes, avg remaining time, clipped ticks.

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/api/models.py`
- Modify: `code/shukketsu/pipeline/constants.py` (add DOT_DEFINITIONS)

**Step 1: Define DoT spell data**

Add to `constants.py`:
```python
@dataclass(frozen=True)
class DotDef:
    spell_id: int
    name: str
    duration_ms: int  # Base duration
    tick_interval_ms: int

CLASSIC_DOTS: dict[str, list[DotDef]] = {
    "Warlock": [
        DotDef(30108, "Unstable Affliction", 18000, 3000),
        DotDef(27216, "Corruption", 18000, 3000),
        DotDef(27218, "Curse of Agony", 24000, 2000),
        DotDef(30405, "Seed of Corruption", 18000, 3000),
        DotDef(27215, "Immolate", 15000, 3000),
    ],
    "Priest": [
        DotDef(25368, "Shadow Word: Pain", 18000, 3000),
        DotDef(25218, "Vampiric Touch", 15000, 3000),
        DotDef(25387, "Devouring Plague", 24000, 3000),
    ],
    "Druid": [
        DotDef(27013, "Moonfire", 12000, 3000),
        DotDef(27012, "Insect Swarm", 12000, 2000),
    ],
}
```

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/fights/{fight_id}/dot-refreshes/{player}")
async def fight_dot_refreshes(report_code: str, fight_id: int, player: str):
```

Logic:
1. Query cast_events for the player, filter to DoT spell_ids
2. Group casts by spell_id, sort by timestamp
3. For each consecutive pair, check if refresh came before previous duration expired
4. If `next_cast_ts < prev_cast_ts + dot_duration_ms`, it's a refresh
5. If `remaining_ms > 0.3 * duration_ms` (outside pandemic window), it's an "early" refresh
6. Compute avg_remaining_ms, early_refresh_pct, estimated clipped ticks

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add dot-refreshes API endpoint with DoT definitions
```

---

### Task 11: Add rotation scoring endpoint

Simple rule-based rotation scoring per spec.

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/api/models.py`
- Create: `code/shukketsu/pipeline/rotation_rules.py`
- Create: `code/tests/pipeline/test_rotation_rules.py`

**Step 1: Define rotation rules**

```python
@dataclass
class RotationRule:
    name: str
    check: Callable  # (cast_events, fight_data, abilities) -> (passed: bool, detail: str)

SPEC_RULES: dict[str, list[RotationRule]] = {
    "Arms Warrior": [...],
    "Fury Warrior": [...],
    ...
}
```

Example rules per spec:
- **Arms Warrior**: Mortal Strike on CD (gap < 8s between casts), Execute in execute phase, Whirlwind used
- **Fury Warrior**: Bloodthirst on CD, Whirlwind used, Heroic Strike during high rage
- **Arcane Mage**: Arcane Blast stacking (3+ consecutive), Arcane Power aligned with Icy Veins
- **Shadow Priest**: SW:P uptime > 90%, VT uptime > 90%, Mind Blast on CD
- **Affliction Warlock**: UA uptime > 90%, Corruption uptime > 90%, CoA uptime > 90%

Rules check against `ability_metrics` (uptime/cast counts), `cast_events` (sequence), and `cooldown_usage` (CD alignment). Start with 3-5 rules per spec for the most played specs, skip exotic specs initially.

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/fights/{fight_id}/rotation/{player}")
async def fight_rotation_score(report_code: str, fight_id: int, player: str):
```

Returns: `{"player_name", "spec", "score_pct", "rules_checked", "rules_passed", "violations_json"}`

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add rotation scoring with per-spec rules
```

---

### Task 12: Add trinket proc tracking endpoint

Tracks trinket buff uptimes from buff_uptimes data.

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/api/models.py`
- Modify: `code/shukketsu/pipeline/constants.py` (add TRINKET_DEFINITIONS)

**Step 1: Define trinket data**

```python
@dataclass(frozen=True)
class TrinketDef:
    spell_id: int
    name: str
    expected_uptime_pct: float  # Theoretical uptime
    slot: str  # "trinket1" or "trinket2"

CLASSIC_TRINKETS: dict[int, TrinketDef] = {
    # Naxx trinkets
    28830: TrinketDef(28830, "Dragonspine Trophy", 22.0, "trinket"),
    23046: TrinketDef(23046, "The Restrained Essence of Sapphiron", 15.0, "trinket"),
    28789: TrinketDef(28789, "Eye of Magtheridon", 25.0, "trinket"),
    ...
}
```

**Step 2: Add route**

```python
@router.get("/reports/{report_code}/fights/{fight_id}/trinkets/{player}")
async def fight_trinket_procs(report_code: str, fight_id: int, player: str):
```

Logic:
1. Query `buff_uptimes` for the player
2. Cross-reference spell_ids against `CLASSIC_TRINKETS`
3. Compare actual uptime_pct against expected_uptime_pct
4. Grade: EXCELLENT if actual >= expected, GOOD if >= 80% of expected, POOR otherwise

**Step 3: Write test, verify pass**

**Step 4: Commit**

```
feat: add trinket proc tracking endpoint
```

---

### Task 13: Fix phases endpoint signature mismatch

Frontend calls `GET /api/data/reports/{code}/fights/{id}/phases/{player}` expecting `PhaseMetricEntry[]`.
Backend implements `GET /api/data/reports/{code}/fights/{id}/phases` returning `PhaseAnalysis`.

**Files:**
- Modify: `code/shukketsu/api/routes/data.py`
- Modify: `code/shukketsu/api/models.py`
- Modify: `code/tests/api/test_phase_endpoint.py`

**Step 1: Add the per-player phases route**

Keep the existing `/phases` route for the fight-level view. Add a new route:

```python
@router.get("/reports/{report_code}/fights/{fight_id}/phases/{player}")
async def fight_phases_player(report_code: str, fight_id: int, player: str):
    # Returns list[PhaseMetricEntry]
```

This returns phase metrics for a specific player, using the ENCOUNTER_PHASES definitions to compute estimated DPS/casts per phase (from cast_events if available, otherwise estimated from total DPS * phase duration fraction).

**Step 2: Write test, verify pass**

**Step 3: Commit**

```
feat: add per-player phases endpoint matching frontend expectations
```

---

## Phase 3: Agent Tool Consolidation & New Tools

### Task 14: Consolidate overlapping agent tools

Merge overlapping tools to reduce the tool count and context window usage.

**Files:**
- Modify: `code/shukketsu/agent/tools.py`
- Modify: `code/shukketsu/agent/prompts.py`
- Modify: `code/tests/agent/test_tools.py`

**Consolidations:**

1. **Merge `get_raid_summary` into `get_raid_execution`**: `get_raid_execution` is a strict superset. Remove `get_raid_summary` from ALL_TOOLS, update prompts to direct Nemotron to `get_raid_execution` for report overviews.

2. **Merge `get_personal_bests` into `get_my_performance`**: Add an optional `bests_only: bool = False` parameter. When true, use `PERSONAL_BESTS` query instead. This reduces tool count by 1.

3. **Merge `get_regression_check` + `resolve_my_fights` concept**: Keep both since they serve different purposes, but ensure prompts guide Nemotron to use `resolve_my_fights` first before calling fight-specific tools.

Net change: 26 → 24 tools.

**Step 1: Update tools.py**

Remove `get_raid_summary` and `get_personal_bests` from `ALL_TOOLS`. Modify `get_my_performance` to accept `bests_only` parameter. Modify `get_raid_execution` docstring to say "overview + execution quality for a raid report."

**Step 2: Update prompts.py**

Remove references to removed tools. Update `SYSTEM_PROMPT` tool list.

**Step 3: Run tests, fix any broken ones**

**Step 4: Commit**

```
refactor: consolidate overlapping agent tools (26 → 24)
```

---

### Task 15: Add resource usage agent tool

**Files:**
- Modify: `code/shukketsu/agent/tools.py`
- Modify: `code/shukketsu/db/queries.py` (RESOURCE_USAGE query already exists, just verify it)

**Step 1: Write failing test**

Test `get_resource_usage()` tool returns formatted resource data.

**Step 2: Add tool**

```python
@tool
async def get_resource_usage(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get resource (mana/energy/rage) usage analysis for a player in a fight.
    Shows min/max/avg resource levels and time spent at zero.
    Requires event data ingestion."""
```

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add get_resource_usage agent tool
```

---

### Task 16: Add cooldown window throughput agent tool

**Files:**
- Modify: `code/shukketsu/agent/tools.py`
- Modify: `code/shukketsu/db/queries.py`

**Step 1: Write failing test**

**Step 2: Add tool**

```python
@tool
async def get_cooldown_windows(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get DPS during cooldown activation windows vs baseline.
    Shows how effectively the player uses burst windows.
    Requires event data ingestion."""
```

Queries cooldown_usage for timing, computes window DPS from cast_events damage during window, compares to overall DPS.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add get_cooldown_windows agent tool
```

---

### Task 17: Add DoT management agent tool

**Files:**
- Modify: `code/shukketsu/agent/tools.py`
- Add SQL query: `DOT_REFRESH_ANALYSIS`

**Step 1: Write failing test**

**Step 2: Add tool**

```python
@tool
async def get_dot_management(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get DoT refresh analysis for a player in a fight.
    Shows early refresh rates and clipped ticks for DoT specs.
    Requires event data ingestion."""
```

Queries `cast_events` for DoT spells, computes refresh timing analysis.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add get_dot_management agent tool
```

---

### Task 18: Add rotation score agent tool

**Files:**
- Modify: `code/shukketsu/agent/tools.py`

**Step 1: Write failing test**

**Step 2: Add tool**

```python
@tool
async def get_rotation_score(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get rotation scoring for a player in a fight.
    Evaluates spec-specific rotation rules and returns a grade.
    Requires event data ingestion."""
```

Calls the same rotation_rules module used by the API endpoint.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add get_rotation_score agent tool
```

---

### Task 19: Add trinket performance agent tool

**Files:**
- Modify: `code/shukketsu/agent/tools.py`

**Step 1: Write failing test**

**Step 2: Add tool**

```python
@tool
async def get_trinket_performance(
    report_code: str, fight_id: int, player_name: str,
) -> str:
    """Get trinket proc uptime analysis for a player in a fight.
    Compares actual proc uptime to theoretical maximum.
    Requires table data ingestion."""
```

Queries `buff_uptimes` and cross-references with `CLASSIC_TRINKETS`.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
feat: add get_trinket_performance agent tool
```

---

## Phase 4: Cleanup & Polish

### Task 20: Update agent prompts for new tools

**Files:**
- Modify: `code/shukketsu/agent/prompts.py`

**Step 1: Update SYSTEM_PROMPT**

Add all new tools to the tool descriptions. Remove references to removed tools. Update the Analysis Capabilities section with the full 27-tool list.

**Step 2: Update ANALYSIS_PROMPT**

Sections 9-14 are no longer phantom — they now have real tools backing them. Update the instructions to be more precise about what data to expect.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```
docs: update agent prompts with full tool inventory
```

---

### Task 21: Clean up dead code and orphaned queries

**Files:**
- Modify: `code/shukketsu/db/queries.py`
- Modify: `code/shukketsu/wcl/queries.py`

**Step 1: Remove dead queries**

- Remove `TOP_ENCOUNTER_RANKINGS` from `wcl/queries.py` (never called)
- The `RESOURCE_USAGE` query is now live (used by the new endpoint), keep it
- `GEAR_SNAPSHOT` is used by the gear endpoint, keep it
- `WEEK_OVER_WEEK` and `PLAYER_PARSE_DELTAS` are used by night-summary, keep them

**Step 2: Run tests, verify pass**

**Step 3: Commit**

```
refactor: remove dead WCL query TOP_ENCOUNTER_RANKINGS
```

---

### Task 22: Update CLAUDE.md documentation

**Files:**
- Modify: `/home/lyro/nvidia-workbench/wcl-tbc-analyzer/CLAUDE.md`

Update:
- Table count: 10 → 18 (adding resource_snapshots, cast_events to the existing 16)
- Tool count: 14 → ~27 (reflecting actual state)
- Add new pipeline modules to the package structure
- Document the event pipeline flow
- Move resolved items to "Resolved issues"
- Update "Known issues" to reflect remaining gaps

**Step 1: Edit CLAUDE.md**

**Step 2: Commit**

```
docs: update CLAUDE.md with current table/tool/pipeline state
```

---

### Task 23: Final test run and verification

**Step 1: Run full test suite**

```bash
python3 -m pytest code/tests/ -v
```

Expected: All tests pass (existing 452 + new tests from Tasks 1-19).

**Step 2: Run linter**

```bash
python3 -m ruff check code/
```

Expected: No errors.

**Step 3: Verify frontend-backend alignment**

Check that all 8 previously-missing endpoints now have routes:
1. `events-available` ✓ (Task 6)
2. `cast-timeline/{player}` ✓ (Task 7)
3. `cooldown-windows/{player}` ✓ (Task 8)
4. `resources/{player}` ✓ (Task 9)
5. `dot-refreshes/{player}` ✓ (Task 10)
6. `rotation/{player}` ✓ (Task 11)
7. `trinkets/{player}` ✓ (Task 12)
8. `phases/{player}` ✓ (Task 13)

Verify phases signature mismatch is resolved (Task 13).

**Step 4: Commit any remaining fixes**

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| **Phase 1** | Tasks 1-5 | Event pipeline: death recaps, cast timeline, cast metrics, cooldown usage, cancelled casts, resource tracking — all tables populated |
| **Phase 2** | Tasks 6-13 | All 8 missing API endpoints + phases mismatch fix — frontend fully connected |
| **Phase 3** | Tasks 14-19 | Agent tools consolidated (26→24) + 5 new tools added (→29) — Nemotron has full analytical coverage |
| **Phase 4** | Tasks 20-23 | Prompts updated, dead code removed, docs current, all tests green |

**Final state:**
- 18 DB tables (was 16 + 1 phantom)
- ~29 agent tools covering all 17 analysis prompt sections
- All frontend API calls have matching backend routes
- Event pipeline populates death_details, cast_metrics, cooldown_usage, cancelled_casts, cast_events, resource_snapshots
- Rotation scoring with per-spec rules
- DoT refresh analysis with pandemic window tracking
- Trinket proc tracking with expected uptime comparison
- Cooldown window throughput analysis
