# Illinois Report Card API — Project Context

This document is the primary orientation for any new Claude Code session. Read it before touching code.

---

## What This Is

A REST API that provides programmatic access to Illinois public school data from the Illinois State Board of Education (ISBE) Illinois Report Card. It handles 15 years of historical data (2010–2024), each year stored in its own table to accommodate schema changes across years. All endpoints are implemented, all tests pass, and the database is fully populated with real data.

---

## Tech Stack

| Layer | Tool |
|-------|------|
| Runtime | Python 3.12+ |
| Framework | FastAPI |
| Database | SQLite with FTS5 extension |
| ORM | SQLAlchemy |
| Validation | Pydantic + pydantic-settings |
| Package manager | uv |
| Testing | pytest + httpx |
| Containers | Docker / docker-compose |

Always use `.venv/bin/python` or `uv run` for Python commands — never bare `python`.

---

## Architecture

### Year-Partitioned Tables

Each year of data gets its own table: `schools_2024`, `districts_2023`, etc. This handles the fact that the Excel format changes across years — some columns appear only in certain years. The `table_manager` service (`app/services/table_manager.py`) creates these tables dynamically from a schema definition.

### entities_master

A central registry of stable entity identifiers (RCDTS codes). Every school, district, and state entity has one row here regardless of year. It powers cross-year queries and is the source table for FTS5 full-text search.

### schema_metadata

Tracks what columns exist in each year's table, their data types (`string | integer | float | percentage`), and their category (`demographics | assessment | enrollment | attendance | graduation`). Written during import, read by the `/schema/{year}` endpoint.

### Authentication + Rate Limiting

Every request (except `/health`) requires `Authorization: Bearer <api_key>`. Keys are stored as SHA-256 hashes. Rate limits are enforced per key by tier: free (100/min), standard (1,000/min), premium (10,000/min). All requests are logged to `usage_logs`.

### Data Import Pipeline

Excel files → `excel_parser` (openpyxl) → `schema_detector` (auto-detects types/categories) → `data_cleaners` (handle percentages, commas in numbers, suppressed `*` values) → dynamic year table via `table_manager`. The CLI entry point is `app/cli/import_data.py`.

---

## Project Structure

```
ReportCardAPI/
├── app/
│   ├── main.py              # FastAPI app factory, router registration, middleware
│   ├── config.py            # pydantic-settings: env vars, rate limits, database URL
│   ├── database.py          # SQLAlchemy engine/session, init_db() with FTS5 setup
│   ├── dependencies.py      # verify_api_key(): Bearer auth + rate limiting
│   ├── api/
│   │   ├── health.py        # GET /health (no auth)
│   │   ├── years.py         # GET /years
│   │   ├── schema.py        # GET /schema/{year}[/{category}]
│   │   ├── schools.py       # GET /schools/{year}[/{rcdts}]
│   │   ├── districts.py     # GET /districts/{year}[/{district_id}]
│   │   ├── state.py         # GET /state/{year}
│   │   ├── search.py        # GET /search (FTS5 full-text)
│   │   ├── query.py         # POST /query (flexible filtering/sorting)
│   │   └── admin.py         # POST/GET/DELETE /admin/keys, POST /admin/import, GET /admin/usage
│   ├── services/
│   │   ├── table_manager.py # create/get year-partitioned tables, get_available_years()
│   │   └── fts5.py          # setup_fts5(), rebuild_fts5_index()
│   ├── models/
│   │   ├── database.py      # ORM: APIKey, UsageLog, EntitiesMaster, SchemaMetadata, ImportJob
│   │   └── errors.py        # Error response definitions
│   ├── utils/
│   │   ├── data_cleaners.py # clean_percentage(), clean_enrollment(), handle_suppressed(), normalize_column_name()
│   │   ├── excel_parser.py  # parse_excel_file(): reads sheets, returns structured data
│   │   └── schema_detector.py # detect_column_type(), detect_column_category()
│   ├── cli/
│   │   ├── __main__.py      # CLI entry point
│   │   └── import_data.py   # import_excel_file(), list_available_years()
│   └── middleware/
│       └── logging.py       # UsageLoggingMiddleware: logs status code + response time
├── tests/
│   ├── conftest.py          # Fixtures: test DB, test client, sample API keys
│   ├── test_api/            # 9 files covering all endpoints
│   ├── test_cli/            # CLI import tests
│   ├── test_integration/    # End-to-end import + schema detection tests
│   ├── test_services/       # table_manager, FTS5
│   ├── test_utils/          # data_cleaners, excel_parser, schema_detector
│   └── test_database.py     # DB init, session management
├── data/
│   ├── report-cards/        # Real Excel files: 2010–2024 from ISBE
│   └── reportcard.db        # SQLite database (fully populated)
├── Dockerfile               # Production image (python:3.12-slim)
├── docker-compose.yml       # Dev setup with live reload
└── pyproject.toml           # Dependencies + dev dependencies
```

---

## Current Status

- **Tests:** 125/125 passing (100%)
- **All API endpoints:** Implemented and tested
- **Database:** Fully populated — all 15 years (2010–2024) imported
- **Data files:** `data/report-cards/` contains Excel files for 2010–2024
- **Import pipeline:** Fully operational — entity type splitting, multi-sheet support, digit-leading column prefix, duplicate column deduplication all in place

---

## Data Coverage

| Years | Format | Tables created |
|-------|--------|----------------|
| 2010–2017 | Single General sheet, all rows are schools | `schools_{year}` only |
| 2018–2024 | Multi-sheet, Type column splits rows | `schools_{year}`, `districts_{year}`, `state_{year}` + supplementary sheets (finance, IAR, SAT, etc.) |

### Supplementary files not imported

The `data/report-cards/` directory contains several files that are **not** imported into the database:

- **`school_11.xlsx` – `school_14.xlsx`** — Grade-level ISAT/PSAE/ACT proficiency data for 2011–2014. These use a non-standard multi-row header format incompatible with the current import pipeline. The main `schools_{year}` tables for those years already include ACT composite and subject scores from the main Report Card files, which covers most use cases. If grade-level ISAT/PSAE breakdowns are needed in the future, a custom parser would be required.
- **`2018-PARCC-SAT-Proficient.xlsx`** — Supplementary PARCC/SAT proficiency file for 2018. The main `schools_2018` table already contains PARCC and SAT data from the primary import.
- **`RC13_layout.xlsx` – `RC17_layout.xlsx`** — Schema layout/documentation files, not data.

---

## What's Next

### 1. New API Features

Add endpoints or capabilities as needed based on real-world usage. Follow TDD.

### 2. Deployment

The app is Docker-ready. Deployment targets: Railway or Fly.io (both have docs in README.md). A persistent volume at `/app/data` is required for the SQLite database.

---

## How to Run

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Start dev server (with live reload)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or via Docker
docker compose up
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | `development` or `production` | `development` |
| `DATABASE_URL` | SQLite path | `sqlite:///./data/reportcard.db` |
| `ADMIN_API_KEY` | Bootstrap admin key | — |
| `RATE_LIMIT_REQUESTS` | Requests per window | `100` |
| `RATE_LIMIT_WINDOW_SECONDS` | Window size in seconds | `60` |
