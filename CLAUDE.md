# CLAUDE.md

## Project overview

**Shukketsu Raid Analyzer** — an agentic AI tool that collects Warcraft Logs (WCL) data for World of Warcraft: The Burning Crusade and provides improvement analysis via a LangGraph CRAG agent powered by Nemotron (served via vLLM).

**Architecture:** Three-layer monolith:
1. **Data pipeline** — cron-scheduled Python scripts pull from WCL GraphQL API v2 into PostgreSQL
2. **FastAPI server** — serves health, analysis endpoints
3. **LangGraph agent** — CRAG pattern: route → query DB → grade → analyze → respond

**Tech stack:** Python 3.12, FastAPI, LangGraph, langchain-openai (OpenAI-compatible vLLM), PostgreSQL 16, SQLAlchemy 2.0 async, httpx, pydantic-settings v2, structlog, tenacity

## NVIDIA AI Workbench structure

This is an NVIDIA AI Workbench project. The directory layout is defined in `.project/spec.yaml`:

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
│   │   └── client.py       # GraphQL HTTP client
│   ├── db/                 # Database layer
│   │   ├── engine.py       # Async engine + session factory
│   │   ├── models.py       # SQLAlchemy ORM models (7 tables)
│   │   └── queries.py      # Analytical SQL queries
│   ├── pipeline/           # Data transformation
│   │   ├── ingest.py       # WCL response → DB rows
│   │   └── normalize.py    # Fight normalization (DPS/HPS calc)
│   ├── agent/              # LangGraph agent
│   │   ├── llm.py          # Nemotron/vLLM client
│   │   ├── tools.py        # SQL query tools (@tool decorated)
│   │   ├── state.py        # AnalyzerState definition
│   │   ├── prompts.py      # System prompts and templates
│   │   └── graph.py        # CRAG state graph
│   ├── api/                # FastAPI layer
│   │   ├── app.py          # App factory + lifespan
│   │   ├── deps.py         # Dependency injection
│   │   └── routes/
│   │       ├── health.py   # GET /health
│   │       └── analyze.py  # POST /api/analyze
│   └── scripts/
│       └── pull_my_logs.py # CLI: fetch report data
├── tests/                  # Test suite (mirrors package structure)
└── alembic/                # Database migrations
```

## Database schema (7 tables)

- `encounters` — WCL encounter definitions (id, name, zone)
- `my_characters` — tracked player characters (unique: name+server+region)
- `reports` — WCL report metadata (PK: code)
- `fights` — individual boss fights within reports (computed duration_ms)
- `fight_performances` — per-player fight metrics (DPS, HPS, parse%, deaths)
- `top_rankings` — top player rankings per encounter/class/spec
- `progression_snapshots` — time-series character progression data

## Configuration

Uses nested pydantic-settings with `env_nested_delimiter="__"`:
- `WCL__CLIENT_ID`, `WCL__CLIENT_SECRET` — WCL API credentials
- `DB__URL` — PostgreSQL connection string
- `LLM__BASE_URL`, `LLM__MODEL` — vLLM endpoint config
- `APP__HOST`, `APP__PORT` — FastAPI server config

Copy `.env.example` to `.env` and fill in credentials.

## Development environment

The container is built from `nvcr.io/nvidia/ai-workbench/pytorch:1.0.6`:

- **OS**: Ubuntu 24.04
- **CUDA**: 12.6.3
- **PyTorch**: 2.6
- **Python**: python3 (3.12+)
- **GPU**: 1 GPU requested, 1024 MB shared memory

The project mounts at **`/project/`** (read-write) inside the container.

### Apps

| App | Port | Notes |
|-----|------|-------|
| JupyterLab | 8888 | Auto-launches; notebook dir is the project mount |
| TensorBoard | 6006 | Reads logs from `/data/tensorboard/logs/` (volume mount) |

## Key configuration files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Package definition, deps, tool config (single source of truth) |
| `alembic.ini` | Alembic migration config |
| `.env.example` | Environment variable template |
| `docker-compose.dev.yml` | Dev PostgreSQL instance |
| `.project/spec.yaml` | Workbench project spec |
| `requirements.txt` | Pulls from pyproject.toml via `-e ".[dev]"` |
| `apt.txt` | System apt packages (libpq-dev) |
| `variables.env` | Non-secret env vars sourced at container start |

## Development commands

```bash
# Install package in dev mode
pip install -e ".[dev]"

# Run tests
pytest code/tests/ -v

# Run tests with coverage
pytest code/tests/ --cov=shukketsu --cov-report=term-missing

# Lint
ruff check code/

# Lint with auto-fix
ruff check code/ --fix

# Database migrations
alembic upgrade head
alembic downgrade -1

# Start FastAPI server
uvicorn shukketsu.api.app:create_app --factory --port 8000

# Pull WCL report data
pull-my-logs --report-code <CODE>

# Start dev PostgreSQL
docker compose -f docker-compose.dev.yml up -d
```

## Conventions

- All source code goes in `code/shukketsu/`.
- Tests mirror the package structure under `code/tests/`.
- TDD: write failing tests first, then implement.
- Large files (models, datasets) go in `models/` or `data/` — Git LFS handles them automatically.
- Temporary or intermediate data goes in `data/scratch/` (gitignored).
- Environment variable `TENSORBOARD_LOGS_DIRECTORY` is set to `/data/tensorboard/logs/`.
- Use `ruff` for linting (line-length 99).
- Use `structlog` for structured logging.
- Use `tenacity` for retries on external API calls.
