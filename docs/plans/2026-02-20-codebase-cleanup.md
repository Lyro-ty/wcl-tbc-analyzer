# Codebase Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove fake/dead/duplicate features and fix inconsistencies identified in the codebase audit — no new features, only cuts and fixes.

**Architecture:** Six independent cleanups across all layers (pipeline, agent tools, API, frontend, tests). Each cleanup removes or fixes a specific issue. Ordered from lowest to highest risk. CRAG simplification deferred to a separate plan due to scope/risk.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, React/TypeScript, pytest

---

## Task 1: Remove discord_format + summaries dead code

The `discord_format.py` and `summaries.py` pipeline modules build a deterministic raid summary that duplicates what the AI agent already does. The `night-summary` API endpoint is not called by the frontend. Remove all of it.

**Files:**
- Delete: `code/shukketsu/pipeline/discord_format.py`
- Delete: `code/shukketsu/pipeline/summaries.py`
- Modify: `code/shukketsu/api/routes/data/reports.py` — remove endpoint + import
- Modify: `code/shukketsu/api/models.py` — remove 3 response models
- Modify: `code/shukketsu/db/queries/api.py` — remove 4 queries + `__all__` entries
- Delete: `code/tests/pipeline/test_summaries.py`
- Delete: `code/tests/pipeline/test_discord_format.py`
- Modify: `code/tests/db/test_queries_logic.py` — remove 2 test methods
- Modify: `code/tests/integration/test_queries.py` — remove 4 integration tests

**Step 1: Delete pipeline modules**

```bash
rm code/shukketsu/pipeline/discord_format.py
rm code/shukketsu/pipeline/summaries.py
```

**Step 2: Remove the night_summary endpoint from reports.py**

In `code/shukketsu/api/routes/data/reports.py`:
- Remove `RaidNightSummary` from the import block at line 17
- Delete the entire `night_summary` function (lines 319-394)

**Step 3: Remove response models from models.py**

In `code/shukketsu/api/models.py`, delete lines 448-487 (the three models):
```python
class FightHighlight(BaseModel):
    ...

class PlayerHighlight(BaseModel):
    ...

class RaidNightSummary(BaseModel):
    ...
```

**Step 4: Remove queries from api.py**

In `code/shukketsu/db/queries/api.py`:
- Remove these 4 entries from the `__all__` list (lines 29-32):
  - `"NIGHT_SUMMARY_FIGHTS"`
  - `"NIGHT_SUMMARY_PLAYERS"`
  - `"WEEK_OVER_WEEK"`
  - `"PLAYER_PARSE_DELTAS"`
- Delete the 4 query bodies (lines 264-375):
  - `NIGHT_SUMMARY_FIGHTS` (lines 264-282)
  - `NIGHT_SUMMARY_PLAYERS` (lines 284-293)
  - `WEEK_OVER_WEEK` (lines 295-329)
  - `PLAYER_PARSE_DELTAS` (lines 331-375)

**Step 5: Delete test files**

```bash
rm code/tests/pipeline/test_summaries.py
rm code/tests/pipeline/test_discord_format.py
```

**Step 6: Remove test methods from shared test files**

In `code/tests/db/test_queries_logic.py`, delete the 2 tests (lines 99-107):
```python
def test_night_summary_fights_has_hps(self):
    ...

def test_night_summary_players_has_hps(self):
    ...
```

In `code/tests/integration/test_queries.py`, delete the 4 integration tests for these queries (lines ~340-358):
- `test_week_over_week_query`
- `test_night_summary_fights_query`
- `test_night_summary_players_query`
- `test_player_parse_deltas_query`

**Step 7: Run tests**

```bash
python3 -m pytest code/tests/ -v --timeout=30
```

Expected: all tests pass, test count drops by ~30 (10 summaries + 10 discord + 2 query logic + 4 integration + tool name set size stays same since these were pipeline-only).

**Step 8: Lint**

```bash
python3 -m ruff check code/
```

Fix any unused import warnings.

**Step 9: Commit**

```bash
git add -A && git commit -m "chore: remove dead discord_format + summaries pipeline and night-summary endpoint"
```

---

## Task 2: Remove cooldown windows (fake data)

`get_cooldown_windows` returns a hardcoded 20% DPS gain for every cooldown. Three layers of code present a made-up number. The `get_cooldown_efficiency` tool already provides real cooldown usage data (times used, max possible, efficiency %). Remove cooldown windows entirely.

**Files:**
- Modify: `code/shukketsu/agent/tools/event_tools.py` — remove `get_cooldown_windows` function
- Modify: `code/shukketsu/agent/tools/__init__.py` — remove import + `ALL_TOOLS` entry
- Modify: `code/shukketsu/api/routes/data/events.py` — remove endpoint + model import
- Modify: `code/shukketsu/api/models.py` — remove `CooldownWindowResponse` (lines 513-522)
- Modify: `code/shukketsu/db/queries/event.py` — remove `COOLDOWN_WINDOWS` query + `__all__` entry
- Delete: `code/frontend/src/components/charts/CooldownWindowChart.tsx`
- Modify: `code/frontend/src/pages/PlayerFightPage.tsx` — remove cooldown windows section
- Modify: `code/frontend/src/lib/api.ts` — remove `fetchCooldownWindows`
- Modify: `code/frontend/src/lib/types.ts` — remove `CooldownWindowEntry`
- Modify: `code/tests/agent/test_tools.py` — update tool count (30→29) + remove from expected set
- Modify: `code/tests/api/test_data_events.py` — remove 2 tests
- Modify: `code/tests/integration/test_queries.py` — remove 1 integration test

**Step 1: Remove the agent tool**

In `code/shukketsu/agent/tools/event_tools.py`, delete the entire `get_cooldown_windows` function (lines 179-220).

**Step 2: Update tools __init__.py**

In `code/shukketsu/agent/tools/__init__.py`:
- Remove `get_cooldown_windows` from the import statement (it's imported from `event_tools`)
- Remove `get_cooldown_windows` from the `ALL_TOOLS` list
- Remove `"get_cooldown_windows"` from the `__all__` list

**Step 3: Remove the API endpoint**

In `code/shukketsu/api/routes/data/events.py`:
- Remove `CooldownWindowResponse` from the import block (line 17)
- Delete the entire `fight_cooldown_windows` function (lines 147-189)

**Step 4: Remove the response model**

In `code/shukketsu/api/models.py`, delete `CooldownWindowResponse` (lines 513-522).

**Step 5: Remove the SQL query**

In `code/shukketsu/db/queries/event.py`:
- Remove `"COOLDOWN_WINDOWS"` from `__all__` (line 21)
- Delete the `COOLDOWN_WINDOWS` query body (lines 181-196)

**Step 6: Remove frontend components**

Delete `code/frontend/src/components/charts/CooldownWindowChart.tsx`.

In `code/frontend/src/pages/PlayerFightPage.tsx`:
- Remove the `fetchCooldownWindows` import
- Remove the `CooldownWindowChart` import
- Remove the `cdWindows` data loading hook (~lines 119-123)
- Remove the "Cooldown Window Throughput" render section (~lines 528-544)

In `code/frontend/src/lib/api.ts`, remove the `fetchCooldownWindows` function (~lines 204-205).

In `code/frontend/src/lib/types.ts`, remove the `CooldownWindowEntry` interface (~lines 319-329).

**Step 7: Update tests**

In `code/tests/agent/test_tools.py`:
- Change `assert len(ALL_TOOLS) == 30` to `assert len(ALL_TOOLS) == 29` (line 38)
- Remove `"get_cooldown_windows"` from the expected set in `test_tool_names` (line 52)

In `code/tests/api/test_data_events.py`, delete `test_cooldown_windows_ok` and `test_cooldown_windows_empty` (~lines 200-237).

In `code/tests/integration/test_queries.py`, delete `test_cooldown_windows_query` (~lines 310-316).

**Step 8: Run tests + lint**

```bash
python3 -m pytest code/tests/ -v --timeout=30
python3 -m ruff check code/
```

**Step 9: Commit**

```bash
git add -A && git commit -m "chore: remove cooldown windows fake data (hardcoded 20% DPS gain)"
```

---

## Task 3: Fold trinket performance into buff analysis

`get_trinket_performance` tracks only 5 trinkets and returns "No known trinket procs found" for most players. The `get_buff_analysis` tool already shows all buffs including trinket procs. Fold trinket annotation into buff analysis and remove the standalone trinket feature.

**Files:**
- Modify: `code/shukketsu/agent/tools/table_tools.py` — add trinket annotation to `get_buff_analysis`, remove `get_trinket_performance`
- Modify: `code/shukketsu/agent/tools/__init__.py` — remove import + entry
- Modify: `code/shukketsu/api/routes/data/events.py` — remove `fight_trinket_procs` endpoint + import
- Modify: `code/shukketsu/api/models.py` — remove `TrinketProcResponse` (lines 545-551)
- Modify: `code/shukketsu/db/queries/table_data.py` — remove `PLAYER_BUFFS_FOR_TRINKETS` + `__all__` entry
- Delete: `code/frontend/src/components/charts/TrinketChart.tsx`
- Modify: `code/frontend/src/pages/PlayerFightPage.tsx` — remove trinket section
- Modify: `code/frontend/src/lib/api.ts` — remove `fetchTrinketProcs`
- Modify: `code/frontend/src/lib/types.ts` — remove `TrinketProc`
- Modify: `code/tests/agent/test_tools.py` — update tool count (29→28) + remove from expected set
- Modify: `code/tests/api/test_data_events.py` — remove trinket test
- Modify: `code/tests/integration/test_queries.py` — remove integration test

**Step 1: Add trinket annotation to get_buff_analysis**

In `code/shukketsu/agent/tools/table_tools.py`, modify `get_buff_analysis` (lines 56-100):

Add import at top of file:
```python
from shukketsu.pipeline.constants import CLASSIC_TRINKETS
```

In the `buff_rows` loop (after line 87), add trinket annotation:
```python
    if buff_rows:
        lines.append("Buffs:")
        for r in buff_rows[:15]:
            tier = grade_above(r.uptime_pct, [(90, "HIGH"), (50, "MED")], "LOW")
            trinket = CLASSIC_TRINKETS.get(r.spell_id)
            if trinket:
                lines.append(
                    f"  [{tier}] {r.ability_name} | "
                    f"Uptime: {r.uptime_pct}% "
                    f"(trinket proc, expected ~{trinket.expected_uptime_pct:.0f}%)"
                )
            else:
                lines.append(
                    f"  [{tier}] {r.ability_name} | "
                    f"Uptime: {r.uptime_pct}%"
                )
```

**Step 2: Remove get_trinket_performance tool**

In `code/shukketsu/agent/tools/table_tools.py`, delete the entire `get_trinket_performance` function (lines 152-199).

**Step 3: Update tools __init__.py**

In `code/shukketsu/agent/tools/__init__.py`:
- Remove `get_trinket_performance` from the import statement (from `table_tools`)
- Remove `get_trinket_performance` from the `ALL_TOOLS` list
- Remove `"get_trinket_performance"` from the `__all__` list

**Step 4: Remove the API endpoint**

In `code/shukketsu/api/routes/data/events.py`:
- Remove `TrinketProcResponse` from the import block (line 22)
- Delete the entire `fight_trinket_procs` function (lines 386-433)

**Step 5: Remove the response model**

In `code/shukketsu/api/models.py`, delete `TrinketProcResponse` (lines 545-551).

**Step 6: Remove the SQL query**

In `code/shukketsu/db/queries/table_data.py`:
- Remove `"PLAYER_BUFFS_FOR_TRINKETS"` from `__all__` (line 12)
- Delete the `PLAYER_BUFFS_FOR_TRINKETS` query body (lines 55-63)

**Step 7: Remove frontend components**

Delete `code/frontend/src/components/charts/TrinketChart.tsx`.

In `code/frontend/src/pages/PlayerFightPage.tsx`:
- Remove the `fetchTrinketProcs` import
- Remove the `TrinketChart` import
- Remove the `trinketProcs` data loading hook (~lines 143-147)
- Remove the "Trinket Performance" render section (~lines 598-611)

In `code/frontend/src/lib/api.ts`, remove the `fetchTrinketProcs` function (~lines 323-324).

In `code/frontend/src/lib/types.ts`, remove the `TrinketProc` interface (~lines 362-369).

**Step 8: Update tests**

In `code/tests/agent/test_tools.py`:
- Change `assert len(ALL_TOOLS) == 29` to `assert len(ALL_TOOLS) == 28` (line 38)
- Remove `"get_trinket_performance"` from the expected set in `test_tool_names` (line 53)

In `code/tests/api/test_data_events.py`, delete `test_trinket_procs_empty` (~lines 340-353).

In `code/tests/integration/test_queries.py`, delete `test_player_buffs_for_trinkets_query` (~lines 460-466).

**Step 9: Write a test for the new trinket annotation in buff analysis**

In the appropriate test file for table_tools, add a test that verifies known trinket spell IDs get annotated with expected uptime in `get_buff_analysis` output. The test should:
- Mock a session returning a buff row with `spell_id=28830` (Dragonspine Trophy) and `uptime_pct=22.0`
- Call `get_buff_analysis`
- Assert output contains "trinket proc, expected ~22%"

**Step 10: Run tests + lint**

```bash
python3 -m pytest code/tests/ -v --timeout=30
python3 -m ruff check code/
```

**Step 11: Commit**

```bash
git add -A && git commit -m "refactor: fold trinket performance into buff analysis, remove standalone trinket tool"
```

---

## Task 4: Fix rotation scoring inconsistency

The API endpoint uses hardcoded thresholds (85% GCD, 20 CPM, 60% CD efficiency) while the agent tool uses spec-aware thresholds from `SPEC_ROTATION_RULES`. The API already fetches `player_spec` and `encounter_name` via `PLAYER_FIGHT_INFO` — it just ignores them. Fix by using the same constants.

**Files:**
- Modify: `code/shukketsu/api/routes/data/events.py` — use spec-aware thresholds
- Modify: `code/tests/api/test_data_events.py` — update tests

**Step 1: Update the API endpoint to use spec-aware thresholds**

In `code/shukketsu/api/routes/data/events.py`, replace the `fight_rotation_score` function (lines 291-383):

```python
@router.get(
    "/reports/{report_code}/fights/{fight_id}/rotation/{player}",
    response_model=RotationScoreResponse,
)
async def fight_rotation_score(
    report_code: str, fight_id: int, player: str,
    session: AsyncSession = Depends(get_db),
):
    """Rule-based rotation scoring for a player in a fight."""
    from shukketsu.pipeline.constants import (
        ENCOUNTER_CONTEXTS,
        ROLE_BY_SPEC,
        ROLE_DEFAULT_RULES,
        SPEC_ROTATION_RULES,
    )

    try:
        info_result = await session.execute(
            q.PLAYER_FIGHT_INFO,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        info_row = info_result.fetchone()
        if not info_row:
            raise HTTPException(
                status_code=404,
                detail=f"No data for {player} in fight {fight_id}",
            )

        spec = info_row.player_spec
        player_class = info_row.player_class
        encounter_name = info_row.encounter_name

        # Look up spec-aware thresholds (same logic as agent tool)
        rules = SPEC_ROTATION_RULES.get((player_class, spec))
        if not rules:
            role = ROLE_BY_SPEC.get(spec, "melee_dps")
            rules = ROLE_DEFAULT_RULES.get(role, ROLE_DEFAULT_RULES["melee_dps"])

        # Apply encounter context modifier
        ctx = ENCOUNTER_CONTEXTS.get(encounter_name)
        modifier = 1.0
        if ctx:
            if rules.role in ("melee_dps", "tank"):
                modifier = ctx.melee_modifier
            elif rules.role in ("ranged_dps", "caster_dps", "healer"):
                modifier = ctx.ranged_modifier
        gcd_target = rules.gcd_target * modifier
        cpm_target = rules.cpm_target * modifier

        cm_result = await session.execute(
            q.FIGHT_CAST_METRICS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cm_row = cm_result.fetchone()

        cd_result = await session.execute(
            q.FIGHT_COOLDOWNS,
            {"report_code": report_code, "fight_id": fight_id,
             "player_name": player},
        )
        cd_rows = cd_result.fetchall()

        rules_checked = 0
        rules_passed = 0
        violations = []

        if cm_row:
            # Rule 1: GCD uptime vs spec target
            rules_checked += 1
            if cm_row.gcd_uptime_pct >= gcd_target:
                rules_passed += 1
            else:
                violations.append(
                    f"GCD uptime {cm_row.gcd_uptime_pct:.1f}% "
                    f"< {gcd_target:.0f}%"
                )

            # Rule 2: CPM vs spec target
            rules_checked += 1
            if cm_row.casts_per_minute >= cpm_target:
                rules_passed += 1
            else:
                violations.append(
                    f"CPM {cm_row.casts_per_minute:.1f} "
                    f"< {cpm_target:.0f}"
                )

        # Rule 3: CD efficiency vs spec target (short/long split)
        long_cd_threshold = 180
        for cd in cd_rows:
            rules_checked += 1
            target = (
                rules.long_cd_efficiency
                if cd.cooldown_sec > long_cd_threshold
                else rules.cd_efficiency_target
            )
            if cd.efficiency_pct >= target:
                rules_passed += 1
            else:
                violations.append(
                    f"{cd.ability_name} efficiency "
                    f"{cd.efficiency_pct:.1f}% < {target:.0f}%"
                )

        score = (
            (rules_passed / rules_checked * 100)
            if rules_checked > 0 else 0.0
        )

        return RotationScoreResponse(
            player_name=player,
            spec=spec,
            score_pct=round(score, 1),
            rules_checked=rules_checked,
            rules_passed=rules_passed,
            violations_json=json.dumps(violations) if violations else None,
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get rotation score")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from None
```

**Step 2: Update API tests**

In `code/tests/api/test_data_events.py`, update the rotation score tests to account for spec-aware thresholds. The `PLAYER_FIGHT_INFO` mock row now needs `player_class` and `encounter_name` fields. The test assertions should reflect that thresholds come from `SPEC_ROTATION_RULES` for the mocked class+spec, not hardcoded values.

Example: if the mock returns `player_class="Warrior"` and `player_spec="Fury"`, thresholds are `gcd_target=90`, `cpm_target=32`, `cd_efficiency_target=85`.

**Step 3: Run tests + lint**

```bash
python3 -m pytest code/tests/ -v --timeout=30
python3 -m ruff check code/
```

**Step 4: Commit**

```bash
git add -A && git commit -m "fix: use spec-aware rotation scoring thresholds in API endpoint (match agent tool)"
```

---

## Task 5: Merge SpeedPage and ComparePage

SpeedPage is a superset of ComparePage — it does single-report speed comparison AND two-report comparison. ComparePage only does two-report comparison with a nearly identical card layout. Absorb ComparePage's route into SpeedPage and remove the duplicate.

**Files:**
- Delete: `code/frontend/src/pages/ComparePage.tsx`
- Modify: `code/frontend/src/App.tsx` — remove ComparePage route + import
- Modify: `code/frontend/src/components/Sidebar.tsx` — remove Compare link from footer

**Step 1: Remove ComparePage**

Delete `code/frontend/src/pages/ComparePage.tsx`.

**Step 2: Update router**

In `code/frontend/src/App.tsx`:
- Remove the `ComparePage` import
- Remove the `<Route path="/compare" element={<ComparePage />} />` line (line 37)

**Step 3: Update sidebar**

In `code/frontend/src/components/Sidebar.tsx`:
- Remove the Compare `<NavLink>` from the footer section (~lines 61-73)
- Remove the `GitCompareArrows` icon import if it's no longer used

**Step 4: Verify frontend builds**

```bash
cd code/frontend && npm run build
```

**Step 5: Commit**

```bash
git add -A && git commit -m "refactor: remove duplicate ComparePage (SpeedPage already covers both modes)"
```

---

## Task 6: Clean up phase analysis

Two issues: (1) the `fight_phases` endpoint in `fights.py` is not called by the frontend (the frontend uses the events.py `/phases/{player}` endpoint), and (2) the agent tool presents estimated phase data with false precision. Remove the unused endpoint and add honesty to the estimates.

**Files:**
- Modify: `code/shukketsu/api/routes/data/fights.py` — remove `fight_phases` endpoint + model imports
- Modify: `code/shukketsu/api/models.py` — remove `PhaseInfo`, `PhasePlayerPerformance`, `PhaseAnalysis` (lines 405-434)
- Modify: `code/shukketsu/agent/tools/event_tools.py` — add estimation disclaimer to phase analysis output
- Delete: `code/tests/api/test_phase_endpoint.py`
- Modify: agent phase tool tests if needed

**Step 1: Remove the unused fights.py phase endpoint**

In `code/shukketsu/api/routes/data/fights.py`:
- Remove `PhaseAnalysis`, `PhaseInfo`, `PhasePlayerPerformance` from the import block (lines 21-23)
- Delete the entire `fight_phases` function (~lines 353-427)

**Step 2: Remove the unused response models**

In `code/shukketsu/api/models.py`, delete `PhaseInfo`, `PhasePlayerPerformance`, and `PhaseAnalysis` (lines 405-434).

**Step 3: Delete the endpoint test file**

```bash
rm code/tests/api/test_phase_endpoint.py
```

**Step 4: Add estimation disclaimer to agent tool output**

In `code/shukketsu/agent/tools/event_tools.py`, in the `get_phase_analysis` function (~line 1035), after the "Phase Timeline:" header, add a disclaimer:

```python
    lines.append("Phase Timeline:")
    lines.append("  (Note: phase timings are estimates based on "
                 "typical fight progression, not actual log events)")
```

**Step 5: Run tests + lint**

```bash
python3 -m pytest code/tests/ -v --timeout=30
python3 -m ruff check code/
```

**Step 6: Commit**

```bash
git add -A && git commit -m "chore: remove unused fights.py phase endpoint, add estimation disclaimer to phase tool"
```

---

## Deferred: CRAG → ReAct simplification

The CRAG loop (route → query → grade → rewrite) adds 2-3 extra LLM calls per request on a local 30B model. The routing step is decorative (changes one sentence in the system prompt). The grader almost always returns "relevant." The rewrite rarely recovers from bad first retrievals.

**Why deferred:** This is the highest-risk change. It touches the core agent graph, streaming behavior, API response model (`query_type` field), and ~230 lines of graph tests. A simpler ReAct loop would produce similar quality with less latency, but the change needs its own plan, branch, and careful testing against the live model.

**Recommendation:** Create a separate plan `2026-02-XX-crag-to-react.md` when ready. Key decisions needed:
1. Use LangGraph `create_react_agent` or hand-rolled loop?
2. How to handle streaming (currently filters by `langgraph_node == "analyze"`)?
3. Drop `query_type` from `AnalyzeResponse` or compute it differently?
4. Max iterations to match current MAX_RETRIES=2 behavior?

---

## Post-cleanup checklist

After all 6 tasks:
- [ ] Total agent tools: 28 (was 30)
- [ ] Total API endpoints: 51 (was 54, removed: night-summary, cooldown-windows, trinkets)
- [ ] Total SQL queries: ~52 (was ~60, removed: 4 summary + 1 cooldown windows + 1 trinkets)
- [ ] Frontend pages: 14 (was 15, removed ComparePage)
- [ ] Pipeline modules: 14 (was 16, removed discord_format + summaries)
- [ ] All tests pass
- [ ] Lint clean
- [ ] Update CLAUDE.md to reflect new counts and removed features
- [ ] Update memory files
