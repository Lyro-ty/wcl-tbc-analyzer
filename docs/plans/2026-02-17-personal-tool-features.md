# Personal Tool Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 12 features that make Shukketsu a proactive personal raid analyzer — auto-ingesting logs, tracking personal bests, detecting regressions, and generating actionable summaries.

**Architecture:** Six phases with clear data dependencies. Phase 1 commits pending work and lays foundation. Phase 2 adds passive data collection (auto-ingest, CombatantInfo). Phases 3-4 build analytics on top of collected data. Phase 5-6 add output formatting and agent UX.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, LangGraph, PostgreSQL 16, asyncio background tasks, React + TypeScript + Recharts

**Prerequisite:** The in-progress event data feature (death_details, cast_metrics, cooldown_usage) MUST be committed before starting this plan. It's currently uncommitted across 14 modified + 14 new files.

---

## Phase 1: Foundation

### Task 1: Auto-Snapshots After Ingest

**Goal:** Automatically run `compute_progression_snapshots` for all tracked characters after every report ingest, eliminating the manual `snapshot-progression` step.

**Files:**
- Modify: `code/shukketsu/pipeline/ingest.py` (add snapshot call after ingest)
- Modify: `code/shukketsu/pipeline/progression.py` (add `snapshot_all_characters` helper)
- Test: `code/tests/pipeline/test_progression.py` (test auto-snapshot trigger)

**Implementation:**

1. Add `snapshot_all_characters(session)` to `progression.py`:
   - Query all `my_characters` rows
   - For each character, call existing `compute_progression_snapshots(session, character)`
   - Return count of snapshots created

2. In `ingest_report()`, after all data is ingested and before the final log line:
   ```python
   # Auto-snapshot progression for tracked characters
   from shukketsu.pipeline.progression import snapshot_all_characters
   snapshot_count = await snapshot_all_characters(session)
   ```

3. Add `snapshots` field to `IngestResult` dataclass

4. Tests:
   - Mock `my_characters` query returning 2 characters
   - Verify `compute_progression_snapshots` called for each
   - Verify IngestResult.snapshots count

**Commit:** `feat: auto-snapshot progression after report ingest`

---

### Task 2: Add `fight_percentage` Column to Fights Table

**Goal:** Store the boss HP% at wipe (already fetched from WCL but discarded). Required for wipe progression tracking in Phase 3.

**Files:**
- Create: `code/alembic/versions/008_add_fight_percentage.py`
- Modify: `code/shukketsu/db/models.py` (add column to Fight)
- Modify: `code/shukketsu/pipeline/ingest.py` (store fightPercentage in parse_fights)
- Test: `code/tests/pipeline/test_ingest.py` (verify fightPercentage stored)

**Implementation:**

1. Migration `008_add_fight_percentage.py`:
   ```python
   op.add_column("fights", sa.Column("fight_percentage", sa.Float, nullable=True))
   ```

2. Add to Fight model:
   ```python
   fight_percentage: Mapped[float | None] = mapped_column(Float)
   ```

3. In `parse_fights()`, add:
   ```python
   fight_percentage=f.get("fightPercentage"),
   ```

4. Tests: Verify `fightPercentage: 45.2` from WCL data appears in parsed Fight object

**Commit:** `feat: store fight_percentage from WCL for wipe tracking`

---

### Task 3: Guild Reports WCL Query

**Goal:** Add GraphQL query to list reports from a guild. Foundation for auto-ingest polling.

**Files:**
- Modify: `code/shukketsu/wcl/queries.py` (add GUILD_REPORTS query)
- Modify: `code/shukketsu/wcl/models.py` (add GuildReportEntry model)
- Test: `code/tests/wcl/test_models.py` (test parsing guild reports response)

**Implementation:**

1. New GraphQL query in `queries.py`:
   ```graphql
   query GuildReports($guildID: Int!, $zoneID: Int, $limit: Int) {
       reportData {
           reports(guildID: $guildID, zoneID: $zoneID, limit: $limit) {
               data {
                   code
                   title
                   startTime
                   endTime
                   zone { id name }
               }
           }
       }
       RATE_LIMIT
   }
   ```

2. New Pydantic model:
   ```python
   class GuildReportEntry(WCLBaseModel):
       code: str
       title: str
       start_time: int
       end_time: int
       zone: dict | None = None
   ```

3. Tests: Parse sample JSON response into GuildReportEntry list

**Commit:** `feat: add WCL guild reports query for auto-polling`

---

## Phase 2: Auto-Ingest & CombatantInfo Pipeline

### Task 4: Auto-Ingest Background Service

**Goal:** Background poller that checks WCL for new guild reports and auto-ingests them with full data (tables + events). Configurable interval. Manageable via API.

**Files:**
- Create: `code/shukketsu/pipeline/auto_ingest.py` (polling logic)
- Modify: `code/shukketsu/config.py` (add GuildConfig + AutoIngestConfig)
- Modify: `code/shukketsu/api/app.py` (start poller in lifespan)
- Create: `code/shukketsu/api/routes/auto_ingest.py` (status/trigger endpoints)
- Modify: `code/shukketsu/api/models.py` (response models)
- Test: `code/tests/pipeline/test_auto_ingest.py`

**Implementation:**

1. Config additions:
   ```python
   class GuildConfig(BaseModel):
       id: int = 0  # WCL guild ID (from guild URL)
       name: str = ""
       server_slug: str = ""
       server_region: str = "US"

   class AutoIngestConfig(BaseModel):
       enabled: bool = False
       poll_interval_minutes: int = 30
       zone_ids: list[int] = []  # Filter to specific zones (empty = all)
       with_tables: bool = True
       with_events: bool = True
   ```

2. Polling logic in `auto_ingest.py`:
   ```python
   class AutoIngestService:
       def __init__(self, settings, session_factory, wcl_factory):
           self.settings = settings
           self._task: asyncio.Task | None = None
           self._last_poll: datetime | None = None
           self._status: str = "idle"  # idle, polling, ingesting, error
           self._stats: dict = {}

       async def start(self):
           self._task = asyncio.create_task(self._poll_loop())

       async def stop(self):
           if self._task:
               self._task.cancel()

       async def _poll_loop(self):
           while True:
               await self._poll_once()
               await asyncio.sleep(self.settings.auto_ingest.poll_interval_minutes * 60)

       async def _poll_once(self):
           # 1. Fetch guild reports from WCL
           # 2. Filter to reports not already in DB (check reports table)
           # 3. For each new report: ingest_report(with_tables, with_events)
           # 4. Auto-snapshot runs via Task 1 integration
           # 5. Update _stats (reports_ingested, last_report, errors)

       async def trigger_now(self) -> dict:
           """Manual trigger, returns immediately with status"""
           asyncio.create_task(self._poll_once())
           return {"status": "triggered"}

       def get_status(self) -> dict:
           return {
               "enabled": self.settings.auto_ingest.enabled,
               "status": self._status,
               "last_poll": self._last_poll,
               "stats": self._stats,
           }
   ```

3. API routes:
   - `GET /api/auto-ingest/status` — current poller state
   - `POST /api/auto-ingest/trigger` — manual poll trigger
   - `POST /api/auto-ingest/toggle` — enable/disable

4. Lifespan integration: Start `AutoIngestService` if `auto_ingest.enabled`

5. Tests:
   - Mock WCL returning 3 guild reports, 1 already in DB → verify 2 ingested
   - Test polling skips already-ingested reports
   - Test status endpoint returns correct state
   - Test manual trigger

**Commit:** `feat: add auto-ingest background service for guild reports`

---

### Task 5: CombatantInfo Pipeline (Consumables + Gear)

**Goal:** Fetch WCL CombatantInfo events to extract consumables (flasks, food, oils, scrolls) and equipped gear per player per fight. Shared data source for both features.

**Files:**
- Create: `code/alembic/versions/009_add_combatant_info.py`
- Modify: `code/shukketsu/db/models.py` (add FightConsumable, GearSnapshot)
- Create: `code/shukketsu/pipeline/combatant_info.py` (parsing + ingestion)
- Modify: `code/shukketsu/pipeline/constants.py` (consumable spell ID mappings)
- Modify: `code/shukketsu/pipeline/ingest.py` (integrate CombatantInfo fetch)
- Test: `code/tests/pipeline/test_combatant_info.py`

**DB Schema:**

```python
class FightConsumable(Base):
    __tablename__ = "fight_consumables"
    __table_args__ = (
        Index("ix_fight_consumables_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(String(50))  # flask, elixir, food, weapon_oil, scroll, potion
    spell_id: Mapped[int] = mapped_column(Integer)
    ability_name: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)  # was it active at pull?

class GearSnapshot(Base):
    __tablename__ = "gear_snapshots"
    __table_args__ = (
        Index("ix_gear_snapshots_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    slot: Mapped[int] = mapped_column(Integer)  # WoW inventory slot (0-18)
    item_id: Mapped[int] = mapped_column(Integer)
    item_level: Mapped[int] = mapped_column(Integer, default=0)
    # No item name — would require external DB. Use item_id for comparison.
```

**Constants (consumable mappings):**

```python
# In constants.py — map known Classic consumable buff IDs to categories
CONSUMABLE_CATEGORIES = {
    # Flasks
    17628: ("flask", "Flask of Supreme Power"),
    17626: ("flask", "Flask of the Titans"),
    17627: ("flask", "Flask of Distilled Wisdom"),
    # Battle Elixirs
    28490: ("elixir", "Elixir of Major Strength"),
    28491: ("elixir", "Elixir of Healing Power"),
    28493: ("elixir", "Elixir of Major Frost Power"),
    28501: ("elixir", "Elixir of Major Firepower"),
    28503: ("elixir", "Elixir of Major Shadow Power"),
    # Guardian Elixirs
    28502: ("elixir", "Elixir of Major Armor"),
    28509: ("elixir", "Elixir of Major Mageblood"),
    28514: ("elixir", "Elixir of Empowerment"),
    # Food
    33254: ("food", "Well Fed"),
    33257: ("food", "Well Fed"),  # Different food same buff
    # Weapon Oils
    28898: ("weapon_oil", "Brilliant Wizard Oil"),
    28891: ("weapon_oil", "Superior Wizard Oil"),
    # ... expand as needed from actual WCL data
}

# Slot names for gear display
GEAR_SLOTS = {
    0: "Head", 1: "Neck", 2: "Shoulder", 3: "Shirt",
    4: "Chest", 5: "Waist", 6: "Legs", 7: "Feet",
    8: "Wrist", 9: "Hands", 10: "Ring 1", 11: "Ring 2",
    12: "Trinket 1", 13: "Trinket 2", 14: "Back",
    15: "Main Hand", 16: "Off Hand", 17: "Ranged",
}
```

**CombatantInfo parsing:**

WCL CombatantInfo events have this structure (fetched via `dataType: "CombatantInfo"`):
```json
{
  "sourceID": 5,
  "gear": [
    {"id": 30104, "itemLevel": 141, "slot": 0},
    {"id": 30098, "itemLevel": 141, "slot": 2},
    ...
  ],
  "auras": [
    {"source": 5, "ability": 28490, "name": "Elixir of Major Strength", "stacks": 1},
    {"source": 0, "ability": 33254, "name": "Well Fed", "stacks": 0},
    ...
  ],
  "specIDs": [71],
  "talents": [...]
}
```

**Pipeline:**
1. Fetch `CombatantInfo` events for each fight (one per player, no pagination needed)
2. Parse `gear[]` → `GearSnapshot` rows (one per slot per player)
3. Parse `auras[]` → match against `CONSUMABLE_CATEGORIES` → `FightConsumable` rows
4. Unknown auras that look like consumables (heuristic: no sourceID = external buff) can be stored as category "unknown"
5. Delete-then-insert per fight (idempotent)

**Integration:**
- Add `--with-combatant-info` flag to `pull-my-logs` OR always fetch when `--with-events` is set (CombatantInfo is cheap — one event per player, no pagination)
- Better: always ingest CombatantInfo when `ingest_events=True` since it shares the same event fetcher

**Tests:**
- Parse sample CombatantInfo JSON → verify FightConsumable rows
- Parse gear array → verify GearSnapshot rows
- Verify unknown auras stored as "unknown" category
- Verify delete-then-insert idempotency
- Verify missing consumable detection (player has no flask → flag)

**Commit:** `feat: add CombatantInfo pipeline for consumables and gear`

---

### Task 6: Consumable Check Agent Tool + API

**Goal:** Agent tool and API endpoint to check consumable preparation per player per fight. Flag missing flasks, food, oils.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add CONSUMABLE_CHECK, CONSUMABLE_HISTORY queries)
- Modify: `code/shukketsu/agent/tools.py` (add get_consumable_check tool)
- Modify: `code/shukketsu/api/routes/data.py` (add consumable endpoints)
- Modify: `code/shukketsu/api/models.py` (response models)
- Modify: `code/shukketsu/agent/prompts.py` (update tool list in system prompt)
- Test: `code/tests/agent/test_tools.py` (tool tests)

**SQL Queries:**

```sql
-- CONSUMABLE_CHECK: Per-player consumable status for a fight
SELECT fc.player_name, fc.category, fc.ability_name, fc.spell_id, fc.active
FROM fight_consumables fc
JOIN fights f ON fc.fight_id = f.id
WHERE f.report_code = :report_code AND f.fight_id = :fight_id
ORDER BY fc.player_name, fc.category

-- CONSUMABLE_AUDIT: Players missing expected consumables in a raid
-- Cross-join all players × expected categories, LEFT JOIN actual consumables
-- Returns gaps like "Lyro missing flask on fight #3"
```

**Agent Tool:**
```python
@tool
async def get_consumable_check(
    report_code: str, fight_id: int, player_name: str | None = None
) -> str:
    """Check consumable preparation (flasks, food, oils) for players in a fight.
    Shows what each player had active and flags missing consumables."""
```

**API Endpoints:**
- `GET /api/data/reports/{code}/fights/{fight_id}/consumables` → all players
- `GET /api/data/reports/{code}/fights/{fight_id}/consumables/{player}` → specific player
- `GET /api/data/reports/{code}/consumable-audit` → raid-wide missing consumables report

**Commit:** `feat: add consumable check tool and API endpoints`

---

### Task 7: Gear Tracking Agent Tool + API

**Goal:** Agent tool and API endpoint to track gear changes over time per character. Show gear snapshots and detect upgrades.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add GEAR_SNAPSHOT, GEAR_CHANGES queries)
- Modify: `code/shukketsu/agent/tools.py` (add get_gear_changes tool)
- Modify: `code/shukketsu/api/routes/data.py` (add gear endpoints)
- Modify: `code/shukketsu/api/models.py` (response models)
- Test: `code/tests/agent/test_tools.py`

**SQL Queries:**

```sql
-- GEAR_SNAPSHOT: Current gear for player in a specific fight
SELECT gs.slot, gs.item_id, gs.item_level, gs.player_name
FROM gear_snapshots gs
JOIN fights f ON gs.fight_id = f.id
WHERE f.report_code = :report_code AND f.fight_id = :fight_id
  AND gs.player_name ILIKE :player_name
ORDER BY gs.slot

-- GEAR_CHANGES: Detect gear changes between two reports for a player
-- Compare gear_snapshots from report A vs B, flag slots where item_id changed
-- Show old item_id, old ilvl, new item_id, new ilvl, slot name
```

**Agent Tool:**
```python
@tool
async def get_gear_changes(player_name: str, report_code_old: str, report_code_new: str) -> str:
    """Compare a player's gear between two raids. Shows which slots changed
    and the item level difference for each upgrade/downgrade."""
```

**API Endpoints:**
- `GET /api/data/reports/{code}/fights/{fight_id}/gear/{player}` → gear snapshot
- `GET /api/data/gear/compare?player={name}&old={code}&new={code}` → gear diff

**Commit:** `feat: add gear tracking tool and API endpoints`

---

## Phase 3: Core Analytics

### Task 8: Personal Best Tracking

**Goal:** Track personal records (PRs) per player per encounter. Show delta from personal best on every fight.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add PERSONAL_BESTS, PERSONAL_BEST_DELTA queries)
- Modify: `code/shukketsu/agent/tools.py` (add get_personal_bests tool)
- Modify: `code/shukketsu/api/routes/data.py` (add personal best endpoints)
- Modify: `code/shukketsu/api/models.py`
- Modify: `code/shukketsu/agent/prompts.py`
- Test: `code/tests/agent/test_tools.py`

**SQL Queries:**

```sql
-- PERSONAL_BESTS: Player's best DPS, parse, and HPS per encounter (kills only)
SELECT e.name AS encounter_name,
       MAX(fp.dps) AS best_dps,
       MAX(fp.parse_percentile) AS best_parse,
       MAX(fp.hps) AS best_hps,
       COUNT(*) AS kill_count,
       MAX(fp.item_level) AS peak_ilvl
FROM fight_performances fp
JOIN fights f ON fp.fight_id = f.id
JOIN encounters e ON f.encounter_id = e.id
WHERE fp.player_name ILIKE :player_name
  AND f.kill = true
GROUP BY e.id, e.name
ORDER BY e.name

-- PERSONAL_BEST_DELTA: Recent fights with delta from personal best
-- Shows each fight's DPS alongside the player's PR for that encounter
-- Computes gap%: (fight_dps - best_dps) / best_dps * 100
```

**Agent Tool:**
```python
@tool
async def get_personal_bests(player_name: str, encounter_name: str | None = None) -> str:
    """Get a player's personal records (best DPS, parse, HPS) per encounter.
    Shows PR values and how recent fights compare to personal bests."""
```

**API Endpoints:**
- `GET /api/data/characters/{name}/personal-bests` → all PRs
- `GET /api/data/characters/{name}/personal-bests/{encounter}` → PR + recent delta

**Frontend Integration:**
- Add PR badge/indicator on PlayerFightPage when current fight is a new PR
- Add PR column to CharacterProfilePage recent parses table

**Commit:** `feat: add personal best tracking with PR indicators`

---

### Task 9: Wipe Progression Tracking

**Goal:** Analyze wipe-to-kill progression on boss encounters. Show attempt sequence with boss HP%, DPS trends, deaths per attempt.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add WIPE_PROGRESSION query)
- Modify: `code/shukketsu/agent/tools.py` (add get_wipe_progression tool)
- Modify: `code/shukketsu/api/routes/data.py` (add wipe progression endpoint)
- Modify: `code/shukketsu/api/models.py`
- Create: `code/frontend/src/components/charts/WipeProgressionChart.tsx`
- Modify: `code/frontend/src/pages/ReportDetailPage.tsx` (add progression view)
- Test: `code/tests/agent/test_tools.py`

**SQL Query:**

```sql
-- WIPE_PROGRESSION: All attempts on an encounter within a report, ordered by attempt
SELECT f.fight_id,
       f.kill,
       f.fight_percentage,
       f.duration_ms,
       COUNT(fp.id) AS player_count,
       ROUND(AVG(fp.dps)::numeric, 1) AS avg_dps,
       SUM(fp.deaths) AS total_deaths,
       ROUND(AVG(fp.parse_percentile)::numeric, 1) AS avg_parse
FROM fights f
JOIN fight_performances fp ON f.id = fp.fight_id
WHERE f.report_code = :report_code
  AND f.encounter_id = (
      SELECT id FROM encounters WHERE name ILIKE :encounter_name LIMIT 1
  )
GROUP BY f.id, f.fight_id, f.kill, f.fight_percentage, f.duration_ms
ORDER BY f.fight_id
```

**Agent Tool:**
```python
@tool
async def get_wipe_progression(report_code: str, encounter_name: str) -> str:
    """Show wipe-to-kill progression for a boss encounter in a raid.
    Lists each attempt with boss HP% at wipe, DPS, deaths, and duration.
    Useful for seeing how quickly the raid learned the fight."""
```

**Frontend:**
- `WipeProgressionChart.tsx`: Line chart showing boss HP% decreasing over attempts
  - X-axis: attempt number
  - Y-axis (left): boss HP% at wipe (100% = instant wipe, 0% = kill)
  - Y-axis (right): avg raid DPS
  - Color: red dots for wipes, green for kill
  - Tooltip: deaths, duration, DPS

**Commit:** `feat: add wipe progression tracking with attempt-by-attempt analysis`

---

### Task 10: Regression Detection

**Goal:** Automatically detect when a player's performance on a farm boss drops significantly vs their rolling average. Surface regressions via API + agent.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add REGRESSION_CHECK query)
- Create: `code/shukketsu/pipeline/regressions.py` (regression computation)
- Modify: `code/shukketsu/agent/tools.py` (add get_regressions tool)
- Modify: `code/shukketsu/api/routes/data.py` (add regression endpoint)
- Modify: `code/shukketsu/api/models.py`
- Test: `code/tests/pipeline/test_regressions.py`

**Algorithm:**
- For each tracked character × encounter with ≥5 kills:
  - Compute rolling average parse% over last 5 kills (the "baseline")
  - Compare last 2 kills against baseline
  - Flag regression if avg of last 2 is ≥15 percentile points below baseline
  - Flag improvement if avg of last 2 is ≥15 points above baseline

**SQL Query:**

```sql
-- REGRESSION_CHECK: Rolling performance windows per character per encounter
WITH ranked_fights AS (
    SELECT fp.player_name, e.name AS encounter_name, fp.dps, fp.parse_percentile,
           f.end_time,
           ROW_NUMBER() OVER (
               PARTITION BY fp.player_name, e.id
               ORDER BY f.end_time DESC
           ) AS rn
    FROM fight_performances fp
    JOIN fights f ON fp.fight_id = f.id
    JOIN encounters e ON f.encounter_id = e.id
    WHERE fp.is_my_character = true AND f.kill = true
),
baseline AS (
    SELECT player_name, encounter_name,
           AVG(parse_percentile) AS baseline_parse,
           AVG(dps) AS baseline_dps
    FROM ranked_fights WHERE rn BETWEEN 3 AND 7
    GROUP BY player_name, encounter_name
    HAVING COUNT(*) >= 3
),
recent AS (
    SELECT player_name, encounter_name,
           AVG(parse_percentile) AS recent_parse,
           AVG(dps) AS recent_dps
    FROM ranked_fights WHERE rn BETWEEN 1 AND 2
    GROUP BY player_name, encounter_name
)
SELECT r.player_name, r.encounter_name,
       r.recent_parse, b.baseline_parse,
       r.recent_dps, b.baseline_dps,
       r.recent_parse - b.baseline_parse AS parse_delta,
       ROUND(((r.recent_dps - b.baseline_dps) / NULLIF(b.baseline_dps, 0) * 100)::numeric, 1) AS dps_delta_pct
FROM recent r
JOIN baseline b ON r.player_name = b.player_name AND r.encounter_name = b.encounter_name
WHERE ABS(r.recent_parse - b.baseline_parse) >= 15
ORDER BY parse_delta ASC
```

**Agent Tool:**
```python
@tool
async def get_regressions(player_name: str | None = None) -> str:
    """Check for performance regressions or improvements on farm bosses.
    Compares recent kills (last 2) against rolling baseline (kills 3-7).
    Flags significant drops (≥15 percentile points) as regressions."""
```

**API Endpoint:**
- `GET /api/data/regressions?player={name}` → list of regression/improvement flags

**Commit:** `feat: add regression detection for farm boss performance`

---

### Task 11: Overhealing Analysis

**Goal:** Break down effective healing vs overhealing per player per fight. WCL table data includes overhealing — extract and expose it.

**Files:**
- Modify: `code/shukketsu/pipeline/table_data.py` (store overhealing from WCL response)
- Create: `code/alembic/versions/010_add_overhealing.py` (add overheal columns)
- Modify: `code/shukketsu/db/models.py` (add overheal fields to FightPerformance or AbilityMetric)
- Modify: `code/shukketsu/db/queries.py` (add HEALING_ANALYSIS query)
- Modify: `code/shukketsu/agent/tools.py` (add get_healing_analysis tool)
- Modify: `code/shukketsu/api/routes/data.py` (add healing endpoint)
- Test: `code/tests/pipeline/test_table_data.py` (verify overheal parsing)
- Test: `code/tests/agent/test_tools.py`

**Approach:**

WCL `Healing` table data returns per-ability entries with `total` (raw healing) and `overheal` (overhealing amount). Currently we store `total` but not `overheal`.

1. Add to `AbilityMetric` model (for `metric_type='healing'` rows):
   ```python
   overheal: Mapped[int] = mapped_column(BigInteger, default=0)
   overheal_pct: Mapped[float] = mapped_column(Float, default=0.0)
   ```

2. In `table_data.py`, when parsing Healing table entries:
   ```python
   overheal = entry.get("overheal", 0)
   effective = entry["total"] - overheal
   overheal_pct = (overheal / entry["total"] * 100) if entry["total"] > 0 else 0
   ```

3. New query `HEALING_ANALYSIS`:
   ```sql
   SELECT am.player_name, am.ability_name,
          am.total AS raw_healing,
          am.overheal,
          am.total - am.overheal AS effective_healing,
          am.overheal_pct,
          am.pct_of_total
   FROM ability_metrics am
   JOIN fights f ON am.fight_id = f.id
   WHERE f.report_code = :report_code AND f.fight_id = :fight_id
     AND am.metric_type = 'healing'
     AND (:player_name IS NULL OR am.player_name ILIKE :player_name)
   ORDER BY am.player_name, effective_healing DESC
   ```

**Agent Tool:**
```python
@tool
async def get_healing_analysis(
    report_code: str, fight_id: int, player_name: str | None = None
) -> str:
    """Analyze healing effectiveness. Shows effective healing vs overhealing
    per ability per player. Identifies abilities with high overhealing
    that indicate heal sniping or poor assignment coverage."""
```

**Commit:** `feat: add overhealing analysis for healers`

---

## Phase 4: Per-Phase Breakdowns

### Task 12: Phase Definitions & Phase-Level Metrics

**Goal:** Define boss fight phases and compute per-phase DPS/deaths/cooldown metrics. Most complex feature — depends on event data and fight timestamps.

**Files:**
- Create: `code/shukketsu/pipeline/phases.py` (phase definitions + computation)
- Modify: `code/shukketsu/pipeline/constants.py` (ENCOUNTER_PHASES dict)
- Create: `code/alembic/versions/011_add_phase_metrics.py`
- Modify: `code/shukketsu/db/models.py` (add PhaseMetric table)
- Modify: `code/shukketsu/db/queries.py` (add PHASE_BREAKDOWN query)
- Modify: `code/shukketsu/agent/tools.py` (add get_phase_analysis tool)
- Modify: `code/shukketsu/api/routes/data.py`
- Test: `code/tests/pipeline/test_phases.py`

**Phase Definition Approach:**

Two strategies, prioritize (a):

a) **HP-threshold phases** — Define phases by boss HP% thresholds (most bosses have clear phase transitions at specific HP%). This works because we can estimate phase timing from DPS data.

b) **Event-based phases** — Detect phase transitions from specific boss cast events (e.g., KT casts Frost Blast in P3). Requires per-boss event definitions.

Start with HP-threshold for simplicity:

```python
# In constants.py
@dataclass
class PhaseDef:
    name: str
    hp_start: float  # Boss HP% at phase start (100 = full)
    hp_end: float    # Boss HP% at phase end

ENCOUNTER_PHASES = {
    # Naxxramas
    "Patchwerk": [
        PhaseDef("Enrage Check", 100, 5),  # Single phase, essentially
    ],
    "Kel'Thuzad": [
        PhaseDef("P1 - Adds", 100, 100),  # HP doesn't change in P1
        PhaseDef("P2 - Active", 100, 40),
        PhaseDef("P3 - Frostbolts", 40, 0),
    ],
    "Sapphiron": [
        PhaseDef("Ground Phase", 100, 10),
        PhaseDef("Air Phase", 10, 0),  # Repeating, simplified
    ],
    "Loatheb": [
        PhaseDef("Full Fight", 100, 0),  # Single phase
    ],
    # ... expand per encounter
}
```

**DB Schema:**

```python
class PhaseMetric(Base):
    __tablename__ = "phase_metrics"
    __table_args__ = (
        Index("ix_phase_metrics_fight_player", "fight_id", "player_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fight_id: Mapped[int] = mapped_column(ForeignKey("fights.id"))
    player_name: Mapped[str] = mapped_column(String(100))
    phase_name: Mapped[str] = mapped_column(String(100))
    phase_order: Mapped[int] = mapped_column(Integer)
    start_ms: Mapped[int] = mapped_column(BigInteger)  # Phase start relative to fight
    end_ms: Mapped[int] = mapped_column(BigInteger)    # Phase end relative to fight
    damage_done: Mapped[int] = mapped_column(BigInteger, default=0)
    dps: Mapped[float] = mapped_column(Float, default=0.0)
    deaths: Mapped[int] = mapped_column(Integer, default=0)
    casts: Mapped[int] = mapped_column(Integer, default=0)
```

**Computation:**

Phase timing is computed from event data:
1. Use `DamageDone` events to estimate when boss HP crossed thresholds
2. Alternatively: use fight duration ÷ phase count as rough splits for single-phase fights
3. For bosses with known phase timings from events: parse specific boss abilities

For MVP: Use time-based splits proportional to known phase durations. Can refine with event-based detection later.

**Agent Tool:**
```python
@tool
async def get_phase_analysis(
    report_code: str, fight_id: int, player_name: str | None = None
) -> str:
    """Break down a boss fight by phase. Shows DPS, deaths, and activity
    per phase per player. Identifies phases where performance drops."""
```

**Note:** This is the most complex feature. Consider implementing a simpler version first (time-based splits) and iterating with event-based phase detection later.

**Commit:** `feat: add per-phase fight breakdown with phase-level metrics`

---

## Phase 5: Output & Agent UX

### Task 13: Smart Agent Context

**Goal:** Let the agent resolve natural-language fight references ("my last 3 Patchwerk kills") without requiring explicit report codes or fight IDs.

**Files:**
- Modify: `code/shukketsu/db/queries.py` (add MY_RECENT_KILLS, RESOLVE_FIGHT queries)
- Modify: `code/shukketsu/agent/tools.py` (add resolve_my_fights tool)
- Modify: `code/shukketsu/agent/prompts.py` (update system prompt with context resolution guidance)
- Test: `code/tests/agent/test_tools.py`

**SQL Queries:**

```sql
-- MY_RECENT_KILLS: Last N kills for a tracked character on an encounter
SELECT f.report_code, f.fight_id, e.name AS encounter_name,
       fp.dps, fp.parse_percentile, fp.deaths, fp.item_level,
       f.duration_ms, r.title AS report_title, r.start_time
FROM fight_performances fp
JOIN fights f ON fp.fight_id = f.id
JOIN encounters e ON f.encounter_id = e.id
JOIN reports r ON f.report_code = r.code
WHERE fp.is_my_character = true
  AND f.kill = true
  AND (:encounter_name IS NULL OR e.name ILIKE :encounter_name)
ORDER BY r.start_time DESC, f.fight_id DESC
LIMIT :limit

-- MY_LATEST_RAID: Most recent report for a tracked character
SELECT DISTINCT r.code, r.title, r.start_time, r.guild_name
FROM reports r
JOIN fights f ON f.report_code = r.code
JOIN fight_performances fp ON fp.fight_id = f.id
WHERE fp.is_my_character = true
ORDER BY r.start_time DESC
LIMIT 1
```

**Agent Tool:**
```python
@tool
async def resolve_my_fights(
    encounter_name: str | None = None, count: int = 5
) -> str:
    """Find your recent fights. Returns report codes and fight IDs for your
    tracked character's recent kills. Use this to look up fight details
    without needing to know report codes.
    If encounter_name is provided, filters to that boss.
    Returns up to 'count' recent fights (default 5)."""
```

**Prompt Update:**

Add to SYSTEM_PROMPT:
```
When the user refers to "my last fight", "my recent kills", "last raid", etc.,
use the resolve_my_fights tool first to find the relevant report codes and
fight IDs, then use other tools with those specific identifiers.
```

**Commit:** `feat: add smart context resolution for agent fight references`

---

### Task 14: Raid Night Summaries

**Goal:** Auto-generate a formatted post-raid summary after ingestion. Includes key stats, standouts, regressions, and week-over-week comparison.

**Files:**
- Create: `code/shukketsu/pipeline/summaries.py` (summary generation logic)
- Modify: `code/shukketsu/db/queries.py` (add RAID_NIGHT_SUMMARY, WEEK_OVER_WEEK queries)
- Modify: `code/shukketsu/api/routes/data.py` (add summary endpoint)
- Modify: `code/shukketsu/api/models.py`
- Test: `code/tests/pipeline/test_summaries.py`

**Summary Structure:**

```python
@dataclass
class RaidNightSummary:
    report_code: str
    report_title: str
    date: str
    guild_name: str | None
    # Totals
    total_bosses: int
    total_kills: int
    total_wipes: int
    total_clear_time_ms: int
    # Highlights
    fastest_kill: dict  # {encounter, duration_ms, vs_last_week}
    slowest_kill: dict
    most_deaths_boss: dict  # {encounter, deaths}
    cleanest_kill: dict  # {encounter, deaths=0}
    # Player highlights
    top_dps_overall: dict  # {player, dps, encounter}
    most_improved: dict  # {player, encounter, parse_delta}
    biggest_regression: dict  # {player, encounter, parse_delta}
    mvp_interrupts: dict  # {player, total_interrupts}
    # Week-over-week (if previous report exists)
    previous_report: str | None
    clear_time_delta_ms: int | None
    kills_delta: int | None
    avg_parse_delta: float | None
```

**SQL Queries:**

```sql
-- RAID_NIGHT_SUMMARY: Aggregate stats for a report
-- (builds on existing RAID_SUMMARY + RAID_EXECUTION_SUMMARY patterns)

-- WEEK_OVER_WEEK: Compare this report to previous report from same guild
-- Find previous report by guild_name + start_time < this report's start_time
-- Compare clear times, kill counts, avg parse%, deaths
```

**API Endpoint:**
- `GET /api/data/reports/{code}/night-summary` → `RaidNightSummary`

**Commit:** `feat: add raid night summary generation`

---

### Task 15: Discord Export

**Goal:** Format raid summaries, fight breakdowns, and comparisons as Discord-ready markdown. Copy-to-clipboard or webhook delivery.

**Files:**
- Create: `code/shukketsu/pipeline/discord_format.py` (formatting functions)
- Modify: `code/shukketsu/api/routes/data.py` (add ?format=discord query param)
- Modify: `code/shukketsu/config.py` (add DiscordConfig for optional webhook)
- Test: `code/tests/pipeline/test_discord_format.py`

**Formatting Functions:**

```python
def format_raid_summary_discord(summary: RaidNightSummary) -> str:
    """Format raid night summary as Discord markdown (≤2000 char limit)."""
    lines = [
        f"## {summary.report_title} — {summary.date}",
        f"**{summary.total_kills}/{summary.total_bosses} bosses** | "
        f"Clear: {format_duration(summary.total_clear_time_ms)} | "
        f"Wipes: {summary.total_wipes}",
        "",
        "**Highlights:**",
        f"⚔️ Top DPS: **{summary.top_dps_overall['player']}** "
        f"({summary.top_dps_overall['dps']:.0f} on {summary.top_dps_overall['encounter']})",
        f"📈 Most Improved: **{summary.most_improved['player']}** "
        f"(+{summary.most_improved['parse_delta']:.0f}% on {summary.most_improved['encounter']})",
    ]
    if summary.clear_time_delta_ms:
        delta = summary.clear_time_delta_ms
        direction = "faster" if delta < 0 else "slower"
        lines.append(f"⏱️ {format_duration(abs(delta))} {direction} than last week")
    return "\n".join(lines)

def format_fight_breakdown_discord(fight_data: list[dict]) -> str:
    """Format fight roster as Discord code block table."""

def format_comparison_discord(comparison: list[dict]) -> str:
    """Format raid comparison as Discord embed-compatible markdown."""
```

**API Integration:**
- Add `?format=discord` query parameter to existing endpoints:
  - `GET /api/data/reports/{code}/night-summary?format=discord`
  - `GET /api/data/reports/{code}/execution?format=discord`
- Returns plain text with Discord markdown instead of JSON

**Optional Webhook:**
```python
class DiscordConfig(BaseModel):
    webhook_url: str = ""  # If set, can auto-post summaries

# POST /api/discord/send-summary — sends formatted summary to webhook
```

**Commit:** `feat: add Discord export formatting for raid summaries`

---

## Dependency Graph

```
Task 1 (Auto-snapshots) ← standalone, no deps
Task 2 (fight_percentage) ← standalone, no deps
Task 3 (Guild reports query) ← standalone, no deps

Task 4 (Auto-ingest) ← depends on Task 1 + Task 3
Task 5 (CombatantInfo) ← standalone (but integrates into ingest pipeline)
Task 6 (Consumable tool) ← depends on Task 5
Task 7 (Gear tool) ← depends on Task 5

Task 8 (Personal bests) ← standalone
Task 9 (Wipe progression) ← depends on Task 2
Task 10 (Regressions) ← standalone
Task 11 (Overhealing) ← standalone

Task 12 (Phase breakdowns) ← depends on event data (already committed)

Task 13 (Smart context) ← standalone
Task 14 (Raid summaries) ← depends on Task 10 (for regression highlights)
Task 15 (Discord export) ← depends on Task 14
```

## Parallel Execution Groups

These groups can be worked on simultaneously:

**Group A:** Tasks 1, 2, 3 (foundation — no deps between them)
**Group B:** Tasks 5, 8, 10, 11, 13 (no cross-deps)
**Group C:** Tasks 4, 9 (depend on Group A)
**Group D:** Tasks 6, 7 (depend on Task 5)
**Group E:** Task 12 (phase breakdowns — independent but complex)
**Group F:** Tasks 14, 15 (output — depend on prior analytics)

## Estimated Scope

| Phase | Tasks | New Files | New DB Tables | New Agent Tools | New API Endpoints |
|-------|-------|-----------|---------------|-----------------|-------------------|
| 1: Foundation | 1-3 | 1 migration | 0 (+1 column) | 0 | 0 |
| 2: Auto-Ingest + CombatantInfo | 4-7 | 3 modules, 1 migration, 1 route | 2 | 3 | 7 |
| 3: Core Analytics | 8-11 | 1 module, 1 migration | 0 (+2 columns) | 4 | 5 |
| 4: Phase Breakdowns | 12 | 1 module, 1 migration | 1 | 1 | 1 |
| 5: Output & Agent UX | 13-15 | 2 modules | 0 | 1 | 3 |
| **Total** | **15** | **~10 new files** | **3 new tables** | **9 new tools** | **~16 new endpoints** |

After completion: 26 agent tools, 46+ API endpoints, 16 DB tables, 11 migrations.
