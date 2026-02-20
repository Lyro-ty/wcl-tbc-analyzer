# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Shukketsu Raid Analyzer** — an agentic AI tool that collects Warcraft Logs (WCL) data for World of Warcraft TBC Classic (The Burning Crusade) and provides raid improvement analysis via a LangGraph CRAG agent powered by Nemotron 3 Nano 30B (served via ollama).

**Game context:** WoW TBC Classic (The Burning Crusade), Phase 1 only. TBC P1 zone IDs: Karazhan (1047), Gruul's Lair/Magtheridon (1048). Reports may contain fights from multiple zones/raids.

**Architecture:** Three-layer monolith:
1. **Data pipeline** — Python scripts + pipeline modules pull from WCL GraphQL API v2 into PostgreSQL
2. **FastAPI server** — serves REST API (57 endpoints), health, analysis; lifespan wires DB + LLM + agent + auto-ingest
3. **LangGraph agent** — CRAG pattern: route → query DB (via tools) → grade → analyze → END
4. **React frontend** — TypeScript + Tailwind CSS dashboard with 14 pages (charts via Recharts)

**Tech stack:** Python 3.12, FastAPI, LangGraph, langchain-openai (OpenAI-compatible ollama), PostgreSQL 16, SQLAlchemy 2.0 async, httpx, pydantic-settings v2, tenacity

## LLM serving

**ollama** serves Nemotron 3 Nano 30B on port 11434 with an OpenAI-compatible API at `http://localhost:11434/v1`. vLLM does not work on this system because the NVIDIA GB10 (Blackwell, sm_121) GPU is not supported by the current PyTorch build (only sm_80/sm_90).

Nemotron is a thinking model — API responses include a `reasoning` field alongside `content`. The reasoning contains chain-of-thought that sometimes leaks into the final output as `</think>` tags. Tool calling works but the model sometimes uses PascalCase for argument keys.

```bash
ollama list
ollama pull nemotron-3-nano:30b
```

## NVIDIA AI Workbench structure

Layout defined in `.project/spec.yaml`:

| Path | Type | Storage | Purpose |
|------|------|---------|---------|
| `code/` | code | git | Source code (tracked normally) |
| `models/` | models | Git LFS | Model artifacts (tracked via LFS) |
| `data/` | data | Git LFS | Datasets (tracked via LFS) |
| `data/scratch/` | data | gitignore | Temporary/scratch data (not tracked) |

`.gitattributes` enforces LFS for `models/**` and `data/**`. Never commit large binary files outside these paths.

## Package structure

```
code/
├── shukketsu/              # Main Python package
│   ├── config.py           # Pydantic settings (nested: wcl, db, llm, app, guild, auto_ingest)
│   ├── wcl/                # WCL API client layer
│   │   ├── auth.py         # OAuth2 client credentials (tenacity retry on 5xx + network errors)
│   │   ├── rate_limiter.py # Points-based rate limiting
│   │   ├── models.py       # WCL API response models (camelCase alias)
│   │   ├── queries.py      # GraphQL query strings
│   │   ├── events.py       # WCL events() API pagination helper
│   │   └── client.py       # GraphQL HTTP client (tenacity retry on 429/5xx/network errors)
│   ├── db/                 # Database layer
│   │   ├── engine.py       # Async engine + session factory
│   │   ├── models.py       # SQLAlchemy ORM models (18 tables)
│   │   └── queries/        # Analytical SQL queries (~60 queries, domain-grouped)
│   │       ├── player.py       # Player/encounter queries (13)
│   │       ├── raid.py         # Raid comparison queries (4)
│   │       ├── table_data.py   # Table-data queries (4)
│   │       ├── event.py        # Event-data queries (16)
│   │       └── api.py          # REST API queries (23)
│   ├── pipeline/           # Data transformation (15 modules)
│   │   ├── ingest.py       # WCL response → DB rows (delete-then-insert, supports --with-tables/--with-events)
│   │   ├── normalize.py    # Fight normalization (DPS/HPS calc, boss detection)
│   │   ├── characters.py   # Character registration + retroactive fight_performances marking
│   │   ├── constants.py    # Class/spec/zone data, cooldowns, DoTs, trinkets, phase definitions
│   │   ├── progression.py  # Snapshot computation (best/median parse/DPS via statistics.median)
│   │   ├── rankings.py     # Top rankings ingestion (delete-then-insert, staleness checks)
│   │   ├── seeds.py        # Encounter seed data (upsert from WCL API or manual list)
│   │   ├── speed_rankings.py # Speed (kill time) rankings ingestion from fightRankings API
│   │   ├── benchmarks.py   # Benchmark pipeline: discover top reports → ingest → compute aggregates
│   │   ├── table_data.py   # WCL table() API → ability_metrics + buff_uptimes (per-fight)
│   │   ├── combatant_info.py # WCL CombatantInfo events → fight_consumables + gear_snapshots
│   │   ├── death_events.py  # WCL Death events → death_details (per-fight)
│   │   ├── cast_events.py   # WCL Cast events → cast_events + cast_metrics + cooldown_usage + cancelled_casts
│   │   ├── resource_events.py # WCL Resource events → resource_snapshots (per-fight)
│   │   ├── auto_ingest.py   # Background polling + weekly benchmark auto-refresh
│   │   └── benchmarks.py    # Benchmark pipeline (discover/ingest/compute top player data)
│   ├── agent/              # LangGraph agent
│   │   ├── llm.py          # LLM client (ChatOpenAI pointing at ollama)
│   │   ├── tool_utils.py   # @db_tool decorator, session wiring, helper functions
│   │   ├── tools/          # 32 agent tools (domain-grouped, @db_tool decorated)
│   │   │   ├── player_tools.py    # 11 player/encounter tools
│   │   │   ├── raid_tools.py      # 3 raid comparison tools
│   │   │   ├── table_tools.py     # 4 table-data tools
│   │   │   ├── event_tools.py     # 12 event-data tools
│   │   │   └── benchmark_tools.py # 2 benchmark tools
│   │   ├── utils.py        # strip_think_tags() for Nemotron output cleanup
│   │   ├── state.py        # AnalyzerState (extends MessagesState)
│   │   ├── prompts.py      # System prompts and templates
│   │   └── graph.py        # CRAG state graph (6 nodes, MAX_RETRIES=2)
│   ├── api/                # FastAPI layer (57 endpoints across 10 route files)
│   │   ├── app.py          # App factory + lifespan (wires DB, LLM, graph, auto-ingest)
│   │   ├── deps.py         # Dependency injection
│   │   └── routes/
│   │       ├── health.py       # GET /health (DB + LLM ping)
│   │       ├── analyze.py      # POST /api/analyze + POST /api/analyze/stream (SSE)
│   │       ├── auto_ingest.py  # GET /status + POST /trigger for background auto-ingest service
│   │       └── data/           # 49 REST endpoints (domain-grouped)
│   │           ├── reports.py      # Report CRUD + summaries (13 endpoints)
│   │           ├── fights.py       # Fight details + performances (11 endpoints)
│   │           ├── characters.py   # Character management + progression (9 endpoints)
│   │           ├── events.py       # Event-data endpoints (10 endpoints)
│   │           ├── rankings.py     # Rankings + leaderboards (4 endpoints)
│   │           ├── comparison.py   # Raid comparisons (2 endpoints)
│   │           └── benchmarks.py  # Benchmark data + watched guilds (7 endpoints)
│   └── scripts/            # CLI entry points (9 total, registered in pyproject.toml)
│       ├── pull_my_logs.py       # pull-my-logs: fetch report data from WCL
│       ├── pull_rankings.py      # pull-rankings: fetch top rankings per encounter/spec
│       ├── pull_speed_rankings.py # pull-speed-rankings: fetch speed (kill time) rankings
│       ├── pull_benchmarks.py    # pull-benchmarks: pull top guild reports and compute benchmarks
│       ├── manage_watched_guilds.py # manage-watched-guilds: manage guild watchlist
│       ├── register_character.py # register-character: register tracked characters
│       ├── seed_encounters.py    # seed-encounters: bootstrap encounter table from WCL
│       ├── snapshot_progression.py # snapshot-progression: compute progression snapshots
│       └── pull_table_data.py   # pull-table-data: backfill ability/buff data for existing reports
├── frontend/               # React + TypeScript + Tailwind CSS + Recharts dashboard
│   └── src/
│       ├── lib/            # api.ts (API client), types.ts (TypeScript interfaces)
│       └── pages/          # 15 page components (Dashboard, Reports, Roster, Chat, etc.)
├── tests/                  # Test suite (713 tests, mirrors package structure)
└── alembic/                # Database migrations (async-aware)
```

## CRAG agent flow

```
route → query → [tool_executor if tool_calls] → grade
                                                   ↓
  ← rewrite ←──────────────────────────── insufficient?
                                                   ↓
                                                relevant
                                                   ↓
                                              analyze → END
```

- **route**: Classifies query as `my_performance | comparison | trend | general`
- **query**: LLM with bound tools retrieves data
- **tool_executor**: ToolNode executes tool calls, results feed back to grade
- **grade**: LLM judges data as "relevant" or "insufficient" (`_format_messages` includes ToolMessage content)
- **rewrite**: Reformulates query, increments `retry_count`
- **MAX_RETRIES = 2**: After 2 retries, grade forces "relevant" and proceeds

## Tool ↔ DB session wiring

Tools use a **module-level global** pattern via `tool_utils.py` — no DI framework:

1. `lifespan()` in `app.py` calls `set_session_factory(factory)` from `tool_utils.py`
2. The `@db_tool` decorator in `tool_utils.py` wraps each tool function:
   - Strips the `session` parameter from the LLM-visible schema
   - Creates a fresh session via `_get_session()` and passes it as first arg
   - Catches all exceptions and returns `"Error retrieving data: {e}"`
   - Always closes the session in a `finally` block
3. Individual tool functions receive a `session` arg automatically — no manual session management
4. The compiled graph and its tools are also injected into the analyze route via `set_graph()`

## Agent tools (30 total)

### Player/encounter-level tools
| Tool | Purpose |
|------|---------|
| `get_my_performance` | Player's recent performance on an encounter (set `bests_only=True` for personal records) |
| `get_top_rankings` | Top N rankings for encounter+class+spec |
| `compare_to_top` | Side-by-side: player vs top 10 average |
| `get_fight_details` | All player performances in a specific fight |
| `get_progression` | Time-series progression for a character |
| `get_deaths_and_mechanics` | Death/interrupt/dispel analysis |
| `search_fights` | Search fights by encounter name |
| `get_spec_leaderboard` | Cross-spec DPS leaderboard for an encounter |
| `resolve_my_fights` | Find recent fights for tracked characters (optional encounter filter) |
| `get_wipe_progression` | Attempt-by-attempt wipe-to-kill progression |
| `get_regressions` | Performance regression/improvement detection for farm bosses |

### Raid-level comparison tools
| Tool | Purpose |
|------|---------|
| `compare_raid_to_top` | Compare full raid speed/execution to WCL global top kills |
| `compare_two_raids` | Side-by-side comparison of two raid reports |
| `get_raid_execution` | Raid overview + execution quality analysis (deaths, interrupts, DPS, parse) |

### Ability/buff analysis tools (require `--with-tables`)
| Tool | Purpose |
|------|---------|
| `get_ability_breakdown` | Per-ability damage/healing breakdown for a player in a fight |
| `get_buff_analysis` | Buff/debuff uptimes for a player in a fight |
| `get_overheal_analysis` | Per-ability overhealing breakdown for healers |

### Event-level analysis tools (require `--with-events`)
| Tool | Purpose |
|------|---------|
| `get_death_analysis` | Detailed death recap with killing blow and damage sequence |
| `get_activity_report` | GCD uptime / ABC analysis (casts/min, gaps, downtime) |
| `get_cooldown_efficiency` | Major cooldown usage efficiency per ability |
| `get_cancelled_casts` | Cast cancel rate analysis (begincast vs cast) |
| `get_consumable_check` | Consumable preparation audit (flasks, food, oils) |
| `get_resource_usage` | Mana/rage/energy usage analysis (min/max/avg, time at zero) |
| `get_dot_management` | DoT refresh timing analysis (early refreshes, clipped ticks) |
| `get_rotation_score` | Rule-based rotation quality score (GCD uptime, CPM, CD efficiency) |
| `get_gear_changes` | Gear comparison between two raids (slot-by-slot ilvl delta) |
| `get_phase_analysis` | Per-phase fight breakdown with player performance |
| `get_enchant_gem_check` | Enchant/gem validation (flags missing enchants, empty gem sockets) |

### Benchmark tools
| Tool | Purpose |
|------|---------|
| `get_encounter_benchmarks` | Overall encounter benchmarks from top guild kills (kill stats, deaths, consumables, composition, DPS targets) |
| `get_spec_benchmark` | Spec-specific performance targets (DPS, GCD uptime, top abilities, buff uptimes, cooldown efficiency) |

Tools are in `code/shukketsu/agent/tools/` (5 domain-grouped modules), SQL queries (raw `text()` with named params, PostgreSQL-specific) in `code/shukketsu/db/queries/` (6 domain-grouped modules).

## Database schema (21 tables)

### Core tables
- `encounters` — WCL encounter definitions (PK: WCL encounter ID, not auto-increment)
- `my_characters` — tracked player characters (unique: name+server+region)
- `reports` — WCL report metadata (PK: code)
- `fights` — individual boss fights (computed `duration_ms` at DB level, FK to encounters+reports)
- `fight_performances` — per-player fight metrics (DPS, HPS, parse%, deaths, interrupts, dispels; `is_my_character` flag)
- `top_rankings` — top player rankings per encounter/class/spec
- `speed_rankings` — top 100 fastest kills per encounter (from WCL `fightRankings` API)
- `progression_snapshots` — time-series character progression data

### Table-data tables (populated via `--with-tables`)
- `ability_metrics` — per-player per-fight ability breakdowns (damage/healing by spell)
- `buff_uptimes` — per-player per-fight buff/debuff uptimes

### Event-data tables (populated via `--with-events`)
- `death_details` — detailed death recaps per player per fight (killing blow, damage sequence)
- `cast_events` — individual cast events (timestamp, spell, target) for timeline analysis
- `cast_metrics` — derived GCD uptime, CPM, gap analysis per player per fight
- `cooldown_usage` — cooldown efficiency tracking (times used vs max possible)
- `cancelled_casts` — cast cancel rate analysis per player per fight
- `resource_snapshots` — mana/rage/energy tracking (min/max/avg, time at zero)
- `fight_consumables` — consumable buffs active per player per fight
- `gear_snapshots` — per-slot gear snapshots with enchant/gem data from CombatantInfo events

### Benchmark tables
- `watched_guilds` — guild watchlist for benchmark tracking (name, WCL guild ID, server)
- `benchmark_reports` — tracks which top reports have been ingested for benchmarks
- `encounter_benchmarks` — pre-computed aggregate benchmarks per encounter (JSON column)

**Key DB patterns:**
- `session.merge()` used for idempotent upserts (encounters, reports, snapshots, characters, benchmarks)
- Report ingestion uses **delete-then-insert** for fights+performances, `session.merge()` for the report itself
- Rankings use **delete-then-insert** refresh with staleness checks (default 24h)
- Speed rankings follow the same delete-then-insert + staleness pattern, one API call per encounter
- `register_character()` retroactively marks existing `fight_performances` rows via case-insensitive bulk UPDATE
- Agent queries use raw SQL with CTEs and PostgreSQL functions (`PERCENTILE_CONT`, `ROUND(...::numeric, 1)`)
- Raid comparison queries use CTEs to aggregate `fight_performances` per fight, then JOIN against `speed_rankings` or FULL OUTER JOIN two reports

## Configuration

Uses nested pydantic-settings with `env_nested_delimiter="__"`:
- `WCL__CLIENT_ID`, `WCL__CLIENT_SECRET` — WCL API credentials
- `DB__URL` — PostgreSQL connection string (default: `postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu`)
- `LLM__BASE_URL` — LLM endpoint (default for ollama: `http://localhost:11434/v1`)
- `LLM__MODEL` — Model name (current: `nemotron-3-nano:30b`)
- `LLM__API_KEY` — API key (set to `ollama` for ollama)
- `LLM__NUM_CTX` — Context window size (default: `32768`)
- `APP__HOST`, `APP__PORT` — FastAPI server config
- `GUILD__ID`, `GUILD__NAME`, `GUILD__SERVER_SLUG`, `GUILD__SERVER_REGION` — Guild config for auto-ingest
- `AUTO_INGEST__ENABLED` — Enable background auto-ingest polling (default: `false`)
- `AUTO_INGEST__POLL_INTERVAL_MINUTES` — Polling interval (default: `30`)
- `AUTO_INGEST__ZONE_IDS` — Zones to poll (default: all)
- `AUTO_INGEST__WITH_TABLES`, `AUTO_INGEST__WITH_EVENTS` — Include table/event data (default: `true`)
- `LANGFUSE__ENABLED` — Enable Langfuse tracing (default: `false`)
- `LANGFUSE__PUBLIC_KEY`, `LANGFUSE__SECRET_KEY` — Langfuse API keys (from Langfuse UI project settings)
- `LANGFUSE__HOST` — Langfuse endpoint (default: `http://localhost:3000`)
- `BENCHMARK__ENABLED` — Enable benchmark auto-refresh (default: `true`)
- `BENCHMARK__REFRESH_INTERVAL_DAYS` — Days between auto-refresh (default: `7`)
- `BENCHMARK__MAX_REPORTS_PER_ENCOUNTER` — Top reports to ingest per encounter (default: `10`)
- `BENCHMARK__ZONE_IDS` — Zones for benchmarks (default: all)

Config lives in `.env` (gitignored). Template in `.env.example`. Settings are `@lru_cache(maxsize=1)` — loaded once per process.

## Development commands

```bash
# Install package in dev mode (--break-system-packages needed on this system)
pip install --break-system-packages -e ".[dev]"

# Run tests
pytest code/tests/ -v

# Run single test
pytest code/tests/path/test_file.py::test_name -v

# Lint
ruff check code/

# Database
docker compose -f docker-compose.dev.yml up -d   # Start dev PostgreSQL
alembic upgrade head                              # Run migrations
alembic downgrade -1                              # Rollback one migration

# Langfuse (observability)
docker compose -f docker-compose.langfuse.yml up -d  # Start Langfuse stack
# Then open http://localhost:3000, create a project, copy API keys to .env

# Start FastAPI server (initializes DB + LLM + agent on startup)
uvicorn shukketsu.api.app:create_app --factory --port 8000

# CLI scripts (7 total, all registered as entry points in pyproject.toml)
pull-my-logs --report-code <CODE>
pull-my-logs --report-code <CODE> --with-tables   # Also fetch ability/buff data
pull-my-logs --report-code <CODE> --with-events   # Also fetch event-level data
pull-table-data --report-code <CODE>              # Backfill ability/buff for existing report
pull-rankings --encounter "Gruul the Dragonkiller" --zone-id 1048
pull-speed-rankings --zone-id 1047 --force
register-character --name Lyro --server Whitemane --region US --class-name Warrior --spec Arms
seed-encounters --zone-ids 1047,1048
snapshot-progression --character Lyro
pull-benchmarks                                   # Full: discover top reports → ingest → compute
pull-benchmarks --compute-only                    # Recompute from existing ingested data
pull-benchmarks --encounter "Gruul" --zone-id 1048
manage-watched-guilds --add "APES" --guild-id 12345 --server whitemane --region US
manage-watched-guilds --list
manage-watched-guilds --remove "APES"

# Test the agent
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"question": "What specs top DPS on Gruul?"}'
```

## Testing patterns

- **asyncio_mode = "auto"** in pytest config — async tests just use `async def test_*()`
- **Minimal fixtures** — only `anyio_backend` in conftest.py; each test creates its own mocks
- **AsyncMock-heavy** — tests mock LLM, WCL client, DB sessions; no integration tests against a real DB
- **respx** for HTTP mocking (httpx client)
- **Class-based grouping** — tests organized by class (e.g., `TestParseZoneRankings`)
- **No SQL execution in tests** — queries could have syntax errors undetectable by unit tests
- **Mock sync methods explicitly** — SQLAlchemy `session.add()` is synchronous; always mock as `session.add = MagicMock()` (not `AsyncMock`) to avoid "coroutine was never awaited" warnings

## WCL API notes

- OAuth2 client credentials flow (WCL registration requires redirect URI — use `http://localhost:8000/oauth/callback`)
- GraphQL API v2 at `https://www.warcraftlogs.com/api/v2/client`
- Rate limited by points per hour; every response includes `rateLimitData`
- Rankings API returns `{"data": [{"fightID": N, "roles": {...}}]}` — a list with fightID fields, not a dict keyed by fight ID
- **GraphQL JSON scalar:** `characterRankings`, `fightRankings`, and report `rankings` may return JSON string OR dict. All parsers handle both via `json.loads()` guard: `if isinstance(data, str): data = json.loads(data)`
- TBC P1 zone IDs: Karazhan (1047), Gruul's Lair/Magtheridon (1048)
- Reports may contain fights from other raids — the ingest pipeline auto-inserts unknown encounters as stubs via `session.merge()`

## Known issues

- **top_rankings table:** Only populated via `pull-rankings` script, not from report ingestion.
- **speed_rankings table:** Only populated via `pull-speed-rankings` script, not from report ingestion.
- **ability_metrics/buff_uptimes tables:** Only populated when `--with-tables` flag is used with `pull-my-logs` or via `pull-table-data` backfill.
- **Event tables:** `death_details`, `cast_events`, `cast_metrics`, `cooldown_usage`, `cancelled_casts`, `resource_snapshots` only populated when `--with-events` flag is used.
- **Rotation scoring:** Uses 3 rules (GCD uptime, CPM, CD efficiency) with per-spec thresholds via `SPEC_ROTATION_RULES` in constants.py. Spec-specific ability priority checking not yet implemented.
- **DoT refresh analysis:** Only covers Warlock, Priest, and Druid DoTs (keyed by class name, no spec filtering).
- **Trinket tracking:** Limited to 5 known TBC P1 trinkets in `CLASSIC_TRINKETS`. Annotated inline within `get_buff_analysis` output (no standalone tool). Expand dict for more coverage.
- **GCD fixed at 1500ms:** `cast_events.py` uses a fixed 1500ms GCD. In WoW, haste reduces GCD to as low as 1.0s for some classes.
- **Healer DPS field:** `parse_rankings_to_performances()` stores WCL's `amount` in the `dps` column for all players. For healers in report rankings, `amount` is actually HPS but gets stored as `dps`. The `total_healing`/`hps` fields are zero from report ingestion (they'd require a separate WCL API call with `metric: hps`).

## Resolved issues

- **Dead code cleanup (Feb 2026):** Removed `discord_format.py` + `summaries.py` (deterministic summary path competing with AI agent), `get_cooldown_windows` (hardcoded fake 20% DPS gain), standalone `get_trinket_performance` (folded into `get_buff_analysis` as inline annotation), duplicate `ComparePage` (SpeedPage already covers both modes), unused `fight_phases` endpoint in `fights.py`. Fixed rotation scoring API to use spec-aware thresholds from `SPEC_ROTATION_RULES`. Added phase analysis estimation disclaimer.
- **Think tags in output:** `strip_think_tags()` in `agent/utils.py` strips Nemotron's leaked `<think>...</think>` reasoning from API responses via regex. Imported as `_strip_think_tags` in `analyze.py` and `graph.py`.
- **429 rate limits:** `WCLClient.query()` has a `tenacity` retry decorator (exponential backoff, 5 attempts) for 429, 502/503/504, connection errors, and read timeouts.
- **Auth retry:** `_request_token()` in `auth.py` retries on 5xx responses AND `ConnectError`/`ReadTimeout` network errors (matching the client's behavior).
- **Grader blindness:** `_format_messages()` in `graph.py` now includes `ToolMessage` content so the grader can see DB query results.
- **Ingest idempotency:** `ingest_report()` uses delete-then-insert for fights+performances, `session.merge()` for reports — safe to re-ingest the same report.
- **Tool error handling:** All 30 agent tools catch exceptions and return friendly error strings instead of propagating tracebacks to the LLM.
- **Missing indexes:** Migration 003 adds indexes on `fight_performances(fight_id, player_name, class+spec)`, `fights(report_code, encounter_id)`, and `top_rankings(encounter_id, class, spec)`.
- **Think tags in agent nodes:** `strip_think_tags()` now applied in both `route_query` and `grade_results` graph nodes, not just the API response.
- **Tool arg case normalization:** `_normalize_tool_args()` in `graph.py` converts Nemotron's PascalCase tool argument keys to snake_case.
- **Dead respond node:** Removed the near-noop `generate_insight` node; `analyze` now flows directly to END.
- **Deaths query:** `DEATHS_AND_MECHANICS` now includes players with `deaths=0` who have interrupt/dispel contributions.
- **Health check:** `/health` endpoint now pings the database (`SELECT 1`) and LLM (`/v1/models`) and returns 503 when either is unreachable.
- **LLM guardrails:** `max_tokens` (4096) and `timeout` (300s) now configured on the ChatOpenAI client.
- **Batch deaths endpoint:** `GET /api/data/reports/{code}/deaths` replaces N+1 per-fight queries on the roster page.
- **Dead code removed:** `compute_dps`/`compute_hps` (unused), `CHARACTER_RANKINGS`/`REPORT_EVENTS`/`RATE_LIMIT_FRAGMENT`/`TOP_ENCOUNTER_RANKINGS` (unused WCL queries).
- **No streaming:** `POST /api/analyze/stream` SSE endpoint streams analysis tokens via LangGraph `astream(stream_mode="messages")`. Think-tag buffering strips `<think>...</think>` before forwarding. Frontend uses `fetch` + `ReadableStream` for incremental message rendering.
- **No event-level data:** WCL `table()` API now ingested into `ability_metrics` and `buff_uptimes` tables. WCL `events()` API ingested via `--with-events` for death recaps, cast timelines, GCD metrics, cooldown tracking, cancel rates, and resource snapshots.
- **Context window truncation:** ollama `num_ctx` now explicitly set to 32768 via `LLM__NUM_CTX` config. Previously defaulted to 2048, causing silent context truncation.
- **No observability:** Langfuse `CallbackHandler` traces all LLM calls, tool executions, and CRAG loop iterations. Self-hosted via `docker-compose.langfuse.yml`. Toggleable via `LANGFUSE__ENABLED`.
- **Phantom agent prompt sections:** Sections 9-14 in ANALYSIS_PROMPT (Resource Usage, Cooldown Windows, Phase Performance, DoT Management, Rotation Score, Trinket Performance) now have matching agent tools and DB data backing them.
- **Missing frontend API routes:** All event-data endpoints implemented: `events-available`, `cast-timeline`, `cooldown-windows`, `resources`, `dot-refreshes`, `rotation`, `trinkets`, `phases/{player}`, `event-data` backfill.
- **Agent tool gaps:** Tools consolidated to 30 (removed 2 overlapping, added 6 new). All 17 ANALYSIS_PROMPT sections now have corresponding tools.
- **Case-insensitive player matching:** All SQL queries use `ILIKE` for `player_name`/`character_name`. Agent tools wrap with `%` wildcards. Character registration uses `func.lower()` for retroactive marking. Ingest pipeline uses lowercase set for `is_my_character` check.
- **Consumable name mismatches:** Fixed 4 incorrect spell ID → name mappings in `CONSUMABLE_CATEGORIES` (28490, 28502, 28509, 28514).
- **Enchantable slots:** Corrected from `{0,2,4,5,7,8,9,11,14,15}` to `{0,2,4,6,7,8,9,14,15}` — waist (5) cannot be enchanted, legs (6) can, rings (10-11) are enchanter-only.
- **WCL client assert:** Replaced `assert self._http is not None` with `raise RuntimeError()` — asserts are stripped by `python -O`.
- **Auto-ingest error tracking:** `_last_error` now set in exception handlers; `trigger_now()` stores task reference to prevent GC.
- **Timezone handling:** Staleness checks now handle both naive and timezone-aware datetimes safely.
- **Resource time_at_zero:** `compute_resource_snapshots()` uses actual `fight_start_time` instead of approximating from first event timestamp.
- **Unused parameter:** Removed dead `actor_name_by_id` from `ingest_table_data_for_fight()`.
- **Monolithic queries.py:** Split `db/queries.py` into domain-grouped package `db/queries/` (player, raid, table_data, event, api — 60 queries total).
- **Monolithic tools.py:** Split `agent/tools.py` into domain-grouped package `agent/tools/` (player_tools, raid_tools, table_tools, event_tools). Session wiring extracted to `agent/tool_utils.py` with `@db_tool` decorator.
- **Monolithic data.py route:** Split `api/routes/data.py` into domain-grouped package `api/routes/data/` (reports, fights, characters, events, rankings, comparison).

## Coding rules

These rules prevent bugs that have occurred in this codebase. Follow them strictly.

### Player name matching — ALWAYS case-insensitive
- **SQL queries:** Always use `ILIKE :player_name`, never `= :player_name`
- **Agent tools:** Always wrap with wildcards: `f"%{player_name}%"`
- **Python comparisons:** Use `.lower()` on both sides or lowercase sets: `{n.lower() for n in names}`
- **Why:** WCL API may return names with different casing than registered characters

### WCL API responses — ALWAYS handle JSON string ambiguity
- WCL GraphQL JSON scalars (`rankings`, `characterRankings`, `fightRankings`, `table`) may return either a JSON string or a parsed dict/list
- **Rule:** Always add a string guard before processing: `if isinstance(data, str): data = json.loads(data)`

### Error messages — MUST match the actual CLI flag
- When referencing CLI flags in error messages (e.g., `--with-tables` vs `--with-events`), grep the codebase for the flag name to verify accuracy
- Event-data tools should reference `--with-events`, table-data tools should reference `--with-tables`

### Game constants — single source of truth in constants.py
- All WoW data (spell IDs, consumable names, gear slots, cooldowns, DoTs, trinkets, phase definitions) lives in `pipeline/constants.py`
- **Never duplicate** these values in tool modules or elsewhere — import from constants
- When adding new spell IDs, verify names against Wowhead/WCL

### Runtime preconditions — NEVER use assert
- `assert` statements are stripped by `python -O`; use `if/raise RuntimeError()` for runtime checks

### Retry decorators — MUST cover both HTTP errors and network errors
- External API retry decorators must handle both response-level errors (5xx status) and connection errors (`ConnectError`, `ReadTimeout`)
- Pattern: `retry = retry_if_result(check_status) | retry_if_exception_type((ConnectError, ReadTimeout))`

### Timezone handling — check before replace
- When comparing timestamps, always check `.tzinfo` before calling `.replace(tzinfo=UTC)`
- Pattern: `aware = dt if dt.tzinfo else dt.replace(tzinfo=UTC)`

### AsyncMock in tests — mock sync methods explicitly
- SQLAlchemy `session.add()`, `session.merge()` are synchronous even on async sessions
- **Rule:** Always use `session.add = MagicMock()` with a comment explaining why
- **Why:** `AsyncMock` makes all methods return coroutines; calling sync methods produces "coroutine was never awaited" warnings

### Imports — always at module level
- All imports go at the top of the file (PEP 8), never inline within functions
- **Exception:** Circular import guards in pipeline modules (e.g., `from shukketsu.wcl.queries import ...` inside functions)

### Function parameters — audit for usage
- When adding parameters to functions, ensure they're actually used in the body
- Periodically audit for dead parameters and remove them

## Conventions

- All source code goes in `code/shukketsu/`, tests in `code/tests/` (mirroring package structure).
- TDD: write failing tests first, then implement.
- `ruff` for linting — line-length 99, rules: E, F, I, N, W, UP, B, SIM.
- `tenacity` for retries on external API calls.
- Large files in `models/` or `data/` (Git LFS). Scratch data in `data/scratch/` (gitignored).
- Never commit `.env`.
- CORS restricted to `localhost:5173` (dev frontend) and `localhost:8000` (API).
