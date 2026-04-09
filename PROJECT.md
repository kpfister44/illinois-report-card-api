# Illinois Report Card API — Project Context

This document is the primary orientation for any new Claude Code session. Read it before touching code.

---

## What This Is

A REST API that provides programmatic access to Illinois public school data from the Illinois State Board of Education (ISBE) Illinois Report Card. It handles 20 years of historical data (2010–2024), each year stored in its own table to accommodate schema changes across years. All endpoints are implemented, all 118 tests pass, and real Excel data is on disk waiting to be imported.

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
│   └── reportcard.db        # SQLite database (empty until import runs)
├── Dockerfile               # Production image (python:3.12-slim)
├── docker-compose.yml       # Dev setup with live reload
└── pyproject.toml           # Dependencies + dev dependencies
```

---

## Current Status

- **Tests:** 118/118 passing (100%)
- **All API endpoints:** Implemented and tested
- **Database:** Empty — no real data has been imported yet
- **Data files:** `data/report-cards/` contains Excel files for 2010–2024

---

## What's Next

### 1. Data Ingestion (immediate priority)

The real Excel files are already on disk. The import pipeline exists. The work is to run it and verify correctness with real data:

```bash
# Import a single year first as a smoke test
.venv/bin/python -m app.cli.import_data data/report-cards/24-RC-Pub-Data-Set.xlsx --year 2024

# List what's now in the database
.venv/bin/python -m app.cli.import_data --list-years
```

Expected issues to watch for:
- Excel files from different years have different column layouts and sheet names
- Some years use layout files (e.g., `RC13_layout.xlsx`) — understand what these contain
- The `--detect-schema` flag controls whether schema_metadata is populated
- After import, run the full test suite to confirm nothing breaks

### 2. New API Features

Add endpoints or capabilities as needed based on real-world usage. Follow TDD.

### 3. Deployment

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
