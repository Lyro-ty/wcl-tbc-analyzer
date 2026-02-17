# Shukketsu Raid Analyzer

An agentic AI tool that pulls data from Warcraft Logs, stores it in PostgreSQL, and provides raid performance analysis through a conversational AI agent and a web dashboard. Built for WoW Classic Fresh (Naxxramas) with support for TBC content.

## How it works

The system has three layers:

1. **Data pipeline** — CLI scripts pull raid reports, rankings, and speed data from the WCL GraphQL API v2 into PostgreSQL. Ingestion is idempotent (safe to re-run).

2. **FastAPI server** — Serves the web UI, REST data endpoints for dashboards, and the `/api/analyze` endpoint for the AI agent.

3. **LangGraph CRAG agent** — A Corrective RAG agent that classifies your question, queries the database using 12 specialized tools, grades whether the data is sufficient (retrying up to 2 times if not), then generates analysis with actionable advice.

```
User question
     |
   route  ──→  classify as: my_performance | comparison | trend | general
     |
   query  ──→  LLM selects tools, queries PostgreSQL
     |
   grade  ──→  "relevant" → analyze → respond
     |            "insufficient" → rewrite → query (max 2 retries)
```

The LLM is **Nemotron 3 Nano 30B** served locally via ollama on an NVIDIA GB10 GPU.

## Get Started

### Prerequisites

- Python 3.12+
- PostgreSQL 16 (or Docker)
- [ollama](https://ollama.com) with the Nemotron model
- A [Warcraft Logs API](https://www.warcraftlogs.com/api/clients) client (OAuth2 client credentials)
- Node.js 20+ (only if rebuilding the frontend)

### 1. Clone and install

```bash
git clone <repo-url>
cd wcl-tbc-analyzer

# Install the Python package in dev mode
pip install -e ".[dev]"
```

### 2. Set up the database

```bash
# Option A: Docker (recommended)
docker compose -f docker-compose.dev.yml up -d

# Option B: Use an existing PostgreSQL instance
# Just make sure the database and user exist

# Run migrations
alembic upgrade head
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```env
# Required — get from https://www.warcraftlogs.com/api/clients
WCL__CLIENT_ID=your_client_id
WCL__CLIENT_SECRET=your_client_secret

# Database (defaults work with the Docker Compose setup)
DB__URL=postgresql+asyncpg://shukketsu:shukketsu@localhost:5432/shukketsu

# LLM (defaults work with ollama)
LLM__BASE_URL=http://localhost:11434/v1
LLM__MODEL=nemotron-3-nano:30b
LLM__API_KEY=ollama
```

### 4. Pull the LLM model

```bash
ollama pull nemotron-3-nano:30b
```

### 5. Seed and populate data

```bash
# Bootstrap encounter definitions from WCL
seed-encounters --zone-ids 2017

# Register your character(s) so they get flagged in performance data
register-character --name Lyro --server Whitemane --region US --class-name Warrior --spec Arms

# Pull a raid report
pull-my-logs --report-code ABC123xyz

# Pull top rankings for comparison (optional)
pull-rankings --encounter "Patchwerk" --zone-id 2017

# Pull speed rankings for kill time comparisons (optional)
pull-speed-rankings --zone-id 2017

# Snapshot progression data for a character (optional)
snapshot-progression --character Lyro
```

### 6. Start the server

```bash
uvicorn shukketsu.api.app:create_app --factory --port 8000
```

The web UI is at `http://localhost:8000`. The API docs are at `http://localhost:8000/docs`.

## Web UI

The frontend is a React + TypeScript SPA served by FastAPI. It includes:

| Page | What it shows |
|------|---------------|
| **Chat** | Conversational interface to the AI agent — ask questions in natural language |
| **Reports** | All ingested raid reports with fight breakdowns, plus a form to pull new reports |
| **Character Reports** | Per-character report filtering and fight details |
| **Progression** | Time-series charts of parse%, DPS, and kills over time per character |
| **Speed** | Kill time comparisons against the WCL global top 100 |
| **Leaderboard** | Spec-based DPS rankings per encounter |
| **Roster** | Manage tracked characters |
| **Compare** | Side-by-side comparison of two raid reports |

The frontend is pre-built in `code/frontend/dist/`. To rebuild after changes:

```bash
cd code/frontend
npm install
npm run build
```

## CLI scripts

All scripts are registered as entry points and available after `pip install -e .`:

| Command | Purpose |
|---------|---------|
| `pull-my-logs --report-code CODE` | Fetch a WCL report and store fights + player performances |
| `pull-rankings --encounter NAME --zone-id ID` | Fetch top player rankings for an encounter and spec |
| `pull-speed-rankings --zone-id ID` | Fetch top 100 fastest kills per encounter |
| `register-character --name N --server S --region R --class-name C --spec P` | Register a character for tracking |
| `seed-encounters --zone-ids ID [ID ...]` | Bootstrap encounter definitions from WCL |
| `snapshot-progression --character NAME` | Compute progression snapshots for a character |

## Agent tools

The AI agent has 12 database query tools:

| Tool | What it answers |
|------|-----------------|
| `get_my_performance` | "How did I do on Patchwerk?" |
| `get_top_rankings` | "What are the top Arms Warrior parses on Thaddius?" |
| `compare_to_top` | "How do I compare to the best rogues on Sapphiron?" |
| `get_fight_details` | "Show me everyone's DPS on fight #3" |
| `get_progression` | "Am I improving on Heigan over time?" |
| `get_deaths_and_mechanics` | "Who died the most on Four Horsemen?" |
| `get_raid_summary` | "Give me an overview of last night's raid" |
| `search_fights` | "Find all our Loatheb kills" |
| `get_spec_leaderboard` | "What specs are topping DPS on Patchwerk?" |
| `compare_raid_to_top` | "How fast are our kills compared to top guilds?" |
| `compare_two_raids` | "Compare last week's raid to this week's" |
| `get_raid_execution` | "Where are we losing the most time?" |

## REST API

The server exposes structured data endpoints under `/api/data/`:

```
GET  /api/data/reports                              — List all reports
GET  /api/data/reports/{code}/summary               — Fight breakdown for a report
GET  /api/data/reports/{code}/execution             — Execution quality analysis
GET  /api/data/reports/{code}/speed                 — Speed comparison vs top 100
GET  /api/data/reports/{code}/fights/{id}           — Player details for a fight
GET  /api/data/compare?a={code1}&b={code2}          — Compare two raids
GET  /api/data/progression/{character}?encounter=X  — Progression time series
GET  /api/data/leaderboard/{encounter}              — Spec leaderboard
GET  /api/data/encounters                           — List encounters
GET  /api/data/characters                           — List registered characters
POST /api/data/characters                           — Register a character
GET  /api/data/characters/{name}/reports            — Reports for a character
GET  /api/data/characters/{name}/reports/{code}     — Character detail in a report
POST /api/data/ingest                               — Pull a WCL report into the DB
POST /api/analyze                                   — Ask the AI agent a question
GET  /health                                        — Health check
```

## Project structure

```
code/
├── shukketsu/                  # Python package
│   ├── config.py               # Pydantic settings (WCL, DB, LLM, App)
│   ├── wcl/                    # WCL API client (OAuth2, rate limiting, retries)
│   ├── db/                     # SQLAlchemy models + analytical SQL queries
│   ├── pipeline/               # Data ingestion, normalization, rankings
│   ├── agent/                  # LangGraph CRAG agent (graph, tools, prompts)
│   ├── api/                    # FastAPI app, routes, response models
│   └── scripts/                # CLI entry points
├── tests/                      # Unit tests (pytest + pytest-asyncio)
├── frontend/                   # React + TypeScript + Tailwind web UI
└── alembic/                    # Database migrations
```

## Development

```bash
# Run tests
pytest code/tests/ -v

# Lint
ruff check code/

# Run a single test
pytest code/tests/path/test_file.py::test_name -v

# Database migrations
alembic upgrade head          # Apply all migrations
alembic downgrade -1          # Rollback one migration

# Test the agent from the command line
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"question": "Give me a summary of my last raid"}'
```

## Known limitations

- **Fight-level data only** — the database stores DPS, HPS, parse%, deaths, interrupts, and dispels per fight. It does not have spell casts, buff uptimes, or ability breakdowns, so rotation-level analysis is not possible.
- **Rankings require manual refresh** — `top_rankings` and `speed_rankings` are populated by CLI scripts, not automatically from report ingestion.
- **Single-user** — no authentication on API endpoints. Intended for personal/guild use on a local network.

## Tech stack

Python 3.12, FastAPI, LangGraph, langchain-openai, PostgreSQL 16, SQLAlchemy 2.0 (async), ollama, Nemotron 3 Nano 30B, React 19, TypeScript, Tailwind CSS, Vite

## NVIDIA AI Workbench

This project uses NVIDIA AI Workbench for GPU-accelerated development. The workspace layout follows the Workbench convention:

- `code/` — source code (git-tracked)
- `models/` — model artifacts (Git LFS)
- `data/` — datasets (Git LFS)
- `data/scratch/` — temporary data (gitignored)
