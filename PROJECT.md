# Illinois Report Card API — Project Context

This document is the primary orientation for any new Claude Code session. Read it before touching code.

---

## What This Is

A REST API that provides programmatic access to Illinois public school data from the Illinois State Board of Education (ISBE) Illinois Report Card. It handles 17 years of historical data (2010–2026), each year stored in its own table to accommodate schema changes across years. All endpoints are implemented, all tests pass, and the database is fully populated with real data.

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
│   ├── conftest.py          # Fixtures: in-memory test DB, test client, API keys
│   ├── test_api/            # 9 files covering all endpoints (in-memory DB)
│   ├── test_cli/            # CLI import tests
│   ├── test_integration/    # End-to-end import + schema detection tests
│   ├── test_real_data/      # 12 sanity tests against real reportcard.db (skipped if DB absent)
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

- **Tests:** 150/150 passing (100%) — unit/integration tests (real-data tests excluded from CI count)
- **All API endpoints:** Implemented and tested
- **Database:** Fully populated — all 17 years (2010–2026) imported
- **Data files:** `data/report-cards/` contains Excel files for 2010–2026
- **Import pipeline:** Fully operational — entity type splitting, multi-sheet support, digit-leading column prefix, duplicate column deduplication, ACT sheet support all in place
- **POST /query:** Supports optional `table_suffix` parameter to query supplementary tables (e.g., `schools_act_2025`, `schools_iar_2025`)
- **Deployed:** Live on Railway at `https://reportcard-api-production.up.railway.app`

---

## Data Coverage

| Years | Format | Tables created |
|-------|--------|----------------|
| 2010–2017 | Single General sheet, all rows are schools | `schools_{year}` only |
| 2018–2024 | Multi-sheet, Type column splits rows | `schools_{year}`, `districts_{year}`, `state_{year}` + supplementary sheets (finance, IAR, SAT, etc.) |
| 2025–2026 | Multi-sheet, includes separate ACT sheet | `schools_{year}`, `schools_act_{year}`, `schools_iar_{year}`, + 8 other supplementary tables |

### Supplementary files not imported

The `data/report-cards/` directory contains several files that are **not** imported into the database:

- **`school_11.xlsx` – `school_14.xlsx`** — Grade-level ISAT/PSAE/ACT proficiency data for 2011–2014. These use a non-standard multi-row header format incompatible with the current import pipeline. The main `schools_{year}` tables for those years already include ACT composite and subject scores from the main Report Card files, which covers most use cases. If grade-level ISAT/PSAE breakdowns are needed in the future, a custom parser would be required.
- **`2018-PARCC-SAT-Proficient.xlsx`** — Supplementary PARCC/SAT proficiency file for 2018. The main `schools_2018` table already contains PARCC and SAT data from the primary import.
- **`RC13_layout.xlsx` – `RC17_layout.xlsx`** — Schema layout/documentation files, not data.

---

## What's Next

### 1. New API Features

Add endpoints or capabilities as needed based on real-world usage. Follow TDD.

### 2. Redeploying

The database is baked into the Docker image, and every redeploy wipes researcher API keys (see below). Requires Docker Desktop (logged in to Docker Hub as `kpfister44`) and the Railway CLI (logged in; the home directory is linked to the `reportcard-api` project). Run each step separately and check it before moving on:

1. **Build locally:** `docker buildx build --platform linux/amd64 -t kpfister44/reportcard-api:latest --load .`
2. **Check what got baked in:** `docker run --rm --platform linux/amd64 --entrypoint ls kpfister44/reportcard-api:latest -la data/` should list only `reportcard.db` (plus `.DS_Store`). `.dockerignore` patterns only match at the build-context root unless prefixed with `**/`.
3. **Smoke-test:** run the image with `--rm -p 8200:8000 -e ADMIN_API_KEY=<throwaway>`, then check `GET /years` with that key. The throwaway key lives only in the container, never in `data/reportcard.db`.
4. **Push:** `docker push kpfister44/reportcard-api:latest`. The ~490MB database layer timed out repeatedly until Docker Desktop's engine config had `"max-concurrent-uploads": 1` (Settings → Docker Engine); that setting is now in place.
5. **Confirm the push:** `docker buildx imagetools inspect kpfister44/reportcard-api:latest` must show the same digest as the local image. **Do not redeploy until it does** — a redeploy after a failed push restarts the old image and still wipes every key.
6. **Redeploy:** `railway redeploy --service reportcard-api --yes`, then confirm the new deployment runs the new image digest and `/health` returns ok.
7. **Tell Kyle** so he can re-issue researcher keys.

The `ADMIN_API_KEY` bootstrap key is set in Railway environment variables — on startup `init_db()` ensures it exists in the database automatically.

> **⚠️ Known issue: API keys are wiped on every redeploy.** Because the database is baked into the Docker image, any API keys created on the live production instance are lost whenever a new image is built and deployed. Only the bootstrap `ADMIN_API_KEY` survives (it's recreated from the Railway env var on startup). This means any researcher or user keys must be manually re-issued after each deploy. **This needs to be resolved** — the right fix is likely moving API key storage out of the baked-in SQLite database (e.g. a persistent volume, a separate Railway database, or environment-variable-based key provisioning).

### 3. Active Researchers

**Chris** — a researcher doing district-level demographic and finance research. First contacted April 2026. Had trouble with the `/query` endpoint because the README examples contained incorrect field names (fixed 2026-04-11). Has since gotten `/query` working for districts and finance tables. Asked about a column name crosswalk across years — no such feature exists yet; directed him to use `GET /schema/{year}` and ask about specific variables.

Key findings from investigating column stability (2026-04-13):
- Schools primary table (2010–2025): only 7 columns are stable across all 16 years — all identity fields (`rcdts`, `school_name`, `district`, `city`, `county`, `grades_served`, `school_type`). No data columns are universally stable.
- Districts primary table (2018–2025): zero columns stable across all 8 years. Best coverage is 7/8 years (2018–2024) for ~113 columns including chronic absenteeism breakdowns, `admin_avg_salary`, `avg_teaching_exp`, class size, and five essentials survey fields. 2025 introduced a major schema restructure that dropped most of these.

Chris's key was last wiped by the 2026-10-30 redeploy that shipped the 2026 data; Kyle re-issues it. Key re-issued after each deploy — keep this in mind before redeploying. Use the admin key (`ADMIN_API_KEY` in Railway) to issue a new key via `POST /admin/keys` after each redeploy.

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
