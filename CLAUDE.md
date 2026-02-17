# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

**Shukketsu Raid Analyzer** — an agentic AI tool that collects Warcraft Logs (WCL) data for World of Warcraft Classic Fresh and provides raid improvement analysis via a LangGraph CRAG agent powered by Nemotron 3 Nano 30B (served via ollama).

**Game context:** WoW Classic Fresh. WCL zone IDs for Fresh are in the 2000+ range (e.g., zone 2017 = Fresh Naxxramas, encounter IDs 201107-201121). Reports may contain fights from multiple zones/raids.

**Architecture:** Three-layer monolith:
1. **Data pipeline** — Python scripts + pipeline modules pull from WCL GraphQL API v2 into PostgreSQL
2. **FastAPI server** — serves health, analysis endpoints; lifespan wires DB + LLM + agent
3. **LangGraph agent** — CRAG pattern: route → query DB (via tools) → grade → analyze → END

**Tech stack:** Python 3.12, FastAPI, LangGraph, langchain-openai (OpenAI-compatible ollama), PostgreSQL 16, SQLAlchemy 2.0 async, httpx, pydantic-settings v2, tenacity, structlog

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
│   ├── config.py           # Pydantic settings (nested: wcl, db, llm, app)
│   ├── wcl/                # WCL API client layer
│   │   ├── auth.py         # OAuth2 client credentials
│   │   ├── rate_limiter.py # Points-based rate limiting
│   │   ├── models.py       # WCL API response models (camelCase alias)
│   │   ├── queries.py      # GraphQL query strings
│   │   └── client.py       # GraphQL HTTP client (tenacity retry on 429/5xx)
│   ├── db/                 # Database layer
│   │   ├── engine.py       # Async engine + session factory
│   │   ├── models.py       # SQLAlchemy ORM models (8 tables)
│   │   └── queries.py      # Analytical SQL queries for agent tools (12 queries)
│   ├── pipeline/           # Data transformation
│   │   ├── ingest.py       # WCL response → DB rows (delete-then-insert, supports --with-tables)
│   │   ├── normalize.py    # Fight normalization (DPS/HPS calc, boss detection)
│   │   ├── characters.py   # Character registration + retroactive fight_performances marking
│   │   ├── constants.py    # Class/spec/zone data (TBC_SPECS, TBC_ZONES, FRESH_ZONES, ALL_BOSS_NAMES)
│   │   ├── progression.py  # Snapshot computation (best/median parse/DPS via statistics.median)
│   │   ├── rankings.py     # Top rankings ingestion (delete-then-insert, staleness checks)
│   │   ├── seeds.py        # Encounter seed data (upsert from WCL API or manual list)
│   │   ├── speed_rankings.py # Speed (kill time) rankings ingestion from fightRankings API
│   │   └── table_data.py   # WCL table() API → ability_metrics + buff_uptimes (per-fight)
│   ├── agent/              # LangGraph agent
│   │   ├── llm.py          # LLM client (ChatOpenAI pointing at ollama)
│   │   ├── tools.py        # 12 SQL query tools (@tool decorated)
│   │   ├── state.py        # AnalyzerState (extends MessagesState)
│   │   ├── prompts.py      # System prompts and templates
│   │   └── graph.py        # CRAG state graph (6 nodes, MAX_RETRIES=2)
│   ├── api/                # FastAPI layer
│   │   ├── app.py          # App factory + lifespan (wires DB, LLM, graph)
│   │   ├── deps.py         # Dependency injection
│   │   └── routes/
│   │       ├── health.py   # GET /health
│   │       └── analyze.py  # POST /api/analyze (strips think tags from LLM output)
│   └── scripts/            # CLI entry points (6 total, registered in pyproject.toml)
│       ├── pull_my_logs.py       # pull-my-logs: fetch report data from WCL
│       ├── pull_rankings.py      # pull-rankings: fetch top rankings per encounter/spec
│       ├── pull_speed_rankings.py # pull-speed-rankings: fetch speed (kill time) rankings
│       ├── register_character.py # register-character: register tracked characters
│       ├── seed_encounters.py    # seed-encounters: bootstrap encounter table from WCL
│       ├── snapshot_progression.py # snapshot-progression: compute progression snapshots
│       └── pull_table_data.py   # pull-table-data: backfill ability/buff data for existing reports
├── tests/                  # Test suite (mirrors package structure)
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

Tools use a **module-level global** pattern — no DI framework:

1. `lifespan()` in `app.py` calls `set_session_factory(factory)` on `tools.py` module
2. Each `@tool` function calls `_get_session()` → creates fresh session from factory
3. Sessions are **always closed in `finally`** blocks — one session per tool invocation
4. All tools catch `Exception` and return `"Error retrieving data: {e}"` instead of propagating tracebacks
5. The compiled graph and its tools are also injected into the analyze route via `set_graph()`

## Agent tools (14 total)

### Player/encounter-level tools
| Tool | Purpose |
|------|---------|
| `get_my_performance` | Player's recent performance on an encounter |
| `get_top_rankings` | Top N rankings for encounter+class+spec |
| `compare_to_top` | Side-by-side: player vs top 10 average |
| `get_fight_details` | All player performances in a specific fight |
| `get_progression` | Time-series progression for a character |
| `get_deaths_and_mechanics` | Death/interrupt/dispel analysis |
| `get_raid_summary` | Overview of all fights in a report |
| `search_fights` | Search fights by encounter name |
| `get_spec_leaderboard` | Cross-spec DPS leaderboard for an encounter |

### Raid-level comparison tools
| Tool | Purpose |
|------|---------|
| `compare_raid_to_top` | Compare full raid speed/execution to WCL global top kills |
| `compare_two_raids` | Side-by-side comparison of two raid reports |
| `get_raid_execution` | Detailed execution quality analysis for a raid |

### Ability/buff analysis tools
| Tool | Purpose |
|------|---------|
| `get_ability_breakdown` | Per-ability damage/healing breakdown for a player in a fight |
| `get_buff_analysis` | Buff/debuff uptimes for a player in a fight |

These tools require table data to be ingested (via `--with-tables` or `pull-table-data`).

Tools are in `code/shukketsu/agent/tools.py`, SQL queries (raw `text()` with named params, PostgreSQL-specific) in `code/shukketsu/db/queries.py`.

## Database schema (10 tables)

- `encounters` — WCL encounter definitions (PK: WCL encounter ID, not auto-increment)
- `my_characters` — tracked player characters (unique: name+server+region)
- `reports` — WCL report metadata (PK: code)
- `fights` — individual boss fights (computed `duration_ms` at DB level, FK to encounters+reports)
- `fight_performances` — per-player fight metrics (DPS, HPS, parse%, deaths, interrupts, dispels; `is_my_character` flag)
- `top_rankings` — top player rankings per encounter/class/spec
- `speed_rankings` — top 100 fastest kills per encounter (from WCL `fightRankings` API, indexed on `encounter_id, rank_position`)
- `progression_snapshots` — time-series character progression data
- `ability_metrics` — per-player per-fight ability breakdowns (damage/healing by spell, indexed on `fight_id, player_name` and `spell_id, metric_type`)
- `buff_uptimes` — per-player per-fight buff/debuff uptimes (indexed on `fight_id, player_name`)

**Key DB patterns:**
- `session.merge()` used for idempotent upserts (encounters, reports, snapshots, characters)
- Report ingestion uses **delete-then-insert** for fights+performances, `session.merge()` for the report itself
- Rankings use **delete-then-insert** refresh with staleness checks (default 24h)
- Speed rankings follow the same delete-then-insert + staleness pattern, one API call per encounter
- `register_character()` retroactively marks existing `fight_performances` rows via bulk UPDATE
- Agent queries use raw SQL with CTEs and PostgreSQL functions (`PERCENTILE_CONT`, `ROUND(...::numeric, 1)`)
- Raid comparison queries use CTEs to aggregate `fight_performances` per fight, then JOIN against `speed_rankings` or FULL OUTER JOIN two reports

## Configuration

Uses nested pydantic-settings with `env_nested_delimiter="__"`:
- `WCL__CLIENT_ID`, `WCL__CLIENT_SECRET` — WCL API credentials
- `DB__URL` — PostgreSQL connection string (default: `postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu`)
- `LLM__BASE_URL` — LLM endpoint (default for ollama: `http://localhost:11434/v1`)
- `LLM__MODEL` — Model name (current: `nemotron-3-nano:30b`)
- `LLM__API_KEY` — API key (set to `ollama` for ollama)
- `APP__HOST`, `APP__PORT` — FastAPI server config
- `LANGFUSE__ENABLED` — Enable Langfuse tracing (default: `false`)
- `LANGFUSE__PUBLIC_KEY`, `LANGFUSE__SECRET_KEY` — Langfuse API keys (from Langfuse UI project settings)
- `LANGFUSE__HOST` — Langfuse endpoint (default: `http://localhost:3000`)

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

# CLI scripts (all registered as entry points in pyproject.toml)
pull-my-logs --report-code <CODE>
pull-my-logs --report-code <CODE> --with-tables  # Also fetch ability/buff data
pull-table-data --report-code <CODE>             # Backfill ability/buff for existing report
pull-rankings --encounter "Patchwerk" --zone-id 2017
pull-speed-rankings --zone-id 2017 --force
register-character --name Lyro --server Whitemane --region US --class-name Warrior --spec Arms
seed-encounters --zone-ids 2017
snapshot-progression --character Lyro

# Test the agent
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"question": "What specs top DPS on Patchwerk?"}'
```

## Testing patterns

- **asyncio_mode = "auto"** in pytest config — async tests just use `async def test_*()`
- **Minimal fixtures** — only `anyio_backend` in conftest.py; each test creates its own mocks
- **AsyncMock-heavy** — tests mock LLM, WCL client, DB sessions; no integration tests against a real DB
- **respx** for HTTP mocking (httpx client)
- **Class-based grouping** — tests organized by class (e.g., `TestParseZoneRankings`)
- **No SQL execution in tests** — queries could have syntax errors undetectable by unit tests

## WCL API notes

- OAuth2 client credentials flow (WCL registration requires redirect URI — use `http://localhost:8000/oauth/callback`)
- GraphQL API v2 at `https://www.warcraftlogs.com/api/v2/client`
- Rate limited by points per hour; every response includes `rateLimitData`
- Rankings API returns `{"data": [{"fightID": N, "roles": {...}}]}` — a list with fightID fields, not a dict keyed by fight ID
- `characterRankings` may return JSON string OR dict — `parse_zone_rankings()` handles both
- `fightRankings(metric: speed)` returns fastest raid kills per encounter; same JSON string/dict ambiguity — `parse_speed_rankings()` handles both
- Fresh Classic zones are in the 2000+ ID range (zone 2017 = Fresh Naxxramas)
- Reports may contain fights from other raids — the ingest pipeline auto-inserts unknown encounters as stubs via `session.merge()`

## Known issues

- **top_rankings table:** Only populated via `pull-rankings` script, not from report ingestion.
- **speed_rankings table:** Only populated via `pull-speed-rankings` script, not from report ingestion.
- **ability_metrics/buff_uptimes tables:** Only populated when `--with-tables` flag is used with `pull-my-logs` or via `pull-table-data` backfill.

## Resolved issues

- **Think tags in output:** `_strip_think_tags()` in `analyze.py` strips Nemotron's leaked `<think>...</think>` reasoning from API responses via regex.
- **429 rate limits:** `WCLClient.query()` has a `tenacity` retry decorator (exponential backoff, 5 attempts) for 429, 502/503/504, connection errors, and read timeouts.
- **Grader blindness:** `_format_messages()` in `graph.py` now includes `ToolMessage` content so the grader can see DB query results.
- **Ingest idempotency:** `ingest_report()` uses delete-then-insert for fights+performances, `session.merge()` for reports — safe to re-ingest the same report.
- **Tool error handling:** All 12 agent tools catch exceptions and return friendly error strings instead of propagating tracebacks to the LLM.
- **Missing indexes:** Migration 003 adds indexes on `fight_performances(fight_id, player_name, class+spec)`, `fights(report_code, encounter_id)`, and `top_rankings(encounter_id, class, spec)`.
- **Think tags in agent nodes:** `_strip_think_tags()` now applied in both `route_query` and `grade_results` graph nodes, not just the API response.
- **Tool arg case normalization:** `_normalize_tool_args()` in `graph.py` converts Nemotron's PascalCase tool argument keys to snake_case.
- **Dead respond node:** Removed the near-noop `generate_insight` node; `analyze` now flows directly to END.
- **Deaths query:** `DEATHS_AND_MECHANICS` now includes players with `deaths=0` who have interrupt/dispel contributions.
- **Health check:** `/health` endpoint now pings the database (`SELECT 1`) and LLM (`/v1/models`) and returns 503 when either is unreachable.
- **LLM guardrails:** `max_tokens` (4096) and `timeout` (300s) now configured on the ChatOpenAI client.
- **Batch deaths endpoint:** `GET /api/data/reports/{code}/deaths` replaces N+1 per-fight queries on the roster page.
- **Dead code removed:** `compute_dps`/`compute_hps` (unused), `CHARACTER_RANKINGS`/`REPORT_EVENTS`/`RATE_LIMIT_FRAGMENT` (unused WCL queries).
- **No streaming:** `POST /api/analyze/stream` SSE endpoint streams analysis tokens via LangGraph `astream(stream_mode="messages")`. Think-tag buffering strips `<think>...</think>` before forwarding. Frontend uses `fetch` + `ReadableStream` for incremental message rendering.
- **No event-level data:** WCL `table()` API now ingested into `ability_metrics` and `buff_uptimes` tables. Provides per-ability damage/healing breakdowns and buff/debuff uptimes. Agent tools `get_ability_breakdown` and `get_buff_analysis` expose this to Nemotron. Frontend `PlayerFightPage` renders interactive charts.
- **Context window truncation:** ollama `num_ctx` now explicitly set to 32768 via `LLM__NUM_CTX` config. Previously defaulted to 2048, causing silent context truncation.
- **No observability:** Langfuse `CallbackHandler` traces all LLM calls, tool executions, and CRAG loop iterations. Self-hosted via `docker-compose.langfuse.yml`. Toggleable via `LANGFUSE__ENABLED`.

## Conventions

- All source code goes in `code/shukketsu/`, tests in `code/tests/` (mirroring package structure).
- TDD: write failing tests first, then implement.
- `ruff` for linting — line-length 99, rules: E, F, I, N, W, UP, B, SIM.
- `tenacity` for retries on external API calls.
- Large files in `models/` or `data/` (Git LFS). Scratch data in `data/scratch/` (gitignored).
- Never commit `.env`.
