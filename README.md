# Illinois Report Card API

A comprehensive REST API for accessing Illinois public school data from the Illinois Report Card. Provides programmatic access to school, district, and state-level education data including enrollment, demographics, assessment scores, and more.

## Live API

**Base URL:** `https://reportcard-api-production.up.railway.app`

- `GET /health` — public health check (no auth required)
- All other endpoints require `Authorization: Bearer <api_key>`

**To request an API key**, email [kpfister44@gmail.com](mailto:kpfister44@gmail.com) with a brief description of your intended use.

## Quickstart for Researchers

This section is for researchers who want to pull data without setting up any local infrastructure. All you need is an API key and a way to make HTTP requests — a terminal, Python, or R all work fine.

### Step 1 — Get an API key

Email [kpfister44@gmail.com](mailto:kpfister44@gmail.com) with a brief description of your project. You'll receive a key that looks like `rc_live_xxxxx`. Keep it handy — every request requires it.

### Step 2 — Make your first request

Paste this into a terminal (replace `rc_live_xxxxx` with your key):

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "https://reportcard-api-production.up.railway.app/years"
```

You should get back a list of available years (2010–2025). If you see that, you're good to go.

### Step 3 — Discover what fields are available

Each year has different fields. Use the `/schema/{year}` endpoint to see what's available:

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "https://reportcard-api-production.up.railway.app/schema/2024" \
  | python3 -m json.tool | head -60
```

Each field entry tells you the column name, data type, category, and — importantly — which table it belongs to (`table_name`). Fields in the main district table will show `"table_name": "districts_2024"`; finance fields will show `"table_name": "districts_finance_2024"`, and so on.

### Step 4 — Pull data

#### District demographics (race, income, enrollment)

Demographics live in the main district table. No special suffix needed:

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer rc_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2024,
    "entity_type": "district",
    "fields": ["district_id", "district_name", "city", "county",
               "total_enrollment", "white_pct", "black_pct",
               "hispanic_pct", "low_income_pct"],
    "limit": 100
  }'
```

#### District finance data

Finance data is in a supplementary table. Add `"table_suffix": "finance"`:

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer rc_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2024,
    "entity_type": "district",
    "table_suffix": "finance",
    "fields": ["district_id", "district_name", "total_revenue_per_pupil",
               "local_revenue_per_pupil", "property_tax_per_pupil",
               "total_expenditure_per_pupil"],
    "limit": 100
  }'
```

Merge the two datasets on `district_id` to get demographics and finance side by side.

> **Finance data lags one year.** The 2024 report card contains 2022-23 actuals. If you need finance data for a specific fiscal year, pull from the report card year that is one year later (e.g., for FY2023 actuals, query year 2024).

#### Paginating through all districts

There are roughly 865 districts per year. Use `limit` and `offset` to page through them:

```bash
# Page 1 (first 500)
-d '{"year": 2024, "entity_type": "district", "limit": 500, "offset": 0}'

# Page 2 (next 500)
-d '{"year": 2024, "entity_type": "district", "limit": 500, "offset": 500}'
```

#### Pulling data in Python

```python
import requests

API_KEY = "rc_live_xxxxx"
BASE_URL = "https://reportcard-api-production.up.railway.app"
headers = {"Authorization": f"Bearer {API_KEY}"}

def query(year, entity_type, fields=None, table_suffix=None, limit=500, offset=0):
    payload = {
        "year": year,
        "entity_type": entity_type,
        "fields": fields,
        "table_suffix": table_suffix,
        "limit": limit,
        "offset": offset,
    }
    r = requests.post(f"{BASE_URL}/query", json=payload, headers=headers)
    r.raise_for_status()
    return r.json()

# Get all district demographics for 2024
result = query(2024, "district", fields=["district_id", "district_name",
                                          "total_enrollment", "white_pct",
                                          "black_pct", "hispanic_pct",
                                          "low_income_pct"])
districts = result["data"]
```

### What fields are actually called?

Field names are normalized versions of the original ISBE Excel column headers (lowercased, spaces replaced with underscores). Because they vary by year, always check `/schema/{year}` first — or omit `fields` entirely to get all columns for a given table. See **[docs/query-guide.md](docs/query-guide.md)** for a full explanation of how tables and fields work across years.

---

## Features

- **16 Years of Data**: 2010–2025 Illinois Report Card data fully imported and queryable
- **Year-Partitioned Architecture**: Handles format changes across years — each year has its own table
- **Full-Text Search**: FTS5-powered search across schools, districts, and state entities
- **Flexible Query API**: Advanced filtering, sorting, and field selection via POST /query
- **API Key Authentication**: Secure access with tiered rate limiting
- **Schema Introspection**: Discover available fields and data types per year

## Technology Stack

- **Runtime**: Python 3.12+
- **Framework**: FastAPI
- **Database**: SQLite with FTS5 for full-text search
- **ORM**: SQLAlchemy
- **Validation**: Pydantic
- **Package Manager**: uv
- **Testing**: pytest with TDD methodology

## Quick Start

### Prerequisites

- Python 3.12+
- uv package manager (will be installed automatically)

### Setup

```bash
# Clone the repository
git clone https://github.com/kpfister44/illinois-report-card-api.git
cd illinois-report-card-api

# Run the setup script
./init.sh

# Activate the virtual environment
source .venv/bin/activate

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Docker

**Development (with live reload):**
```bash
# Uses docker-compose.yml with volume mounts for code changes
docker compose up

# Stop and remove containers
docker compose down
```

**Production:**
```bash
# Build the image
docker build -t reportcard-api .

# Run with environment variables
docker run -d \
  -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e DATABASE_URL=sqlite:///./data/reportcard.db \
  -v $(pwd)/data:/app/data \
  --name reportcard-api \
  reportcard-api

# View logs
docker logs -f reportcard-api

# Stop container
docker stop reportcard-api && docker rm reportcard-api
```

## API Endpoints

### Public Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |

### Authenticated Endpoints

All endpoints below require `Authorization: Bearer <api_key>` header.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/years` | List available data years |
| GET | `/schema/{year}` | Get field metadata for a year |
| GET | `/schema/{year}/{category}` | Get fields filtered by category |
| GET | `/schools/{year}` | List schools with filtering/pagination |
| GET | `/schools/{year}/{rcdts}` | Get single school details |
| GET | `/districts/{year}` | List districts with filtering/pagination |
| GET | `/districts/{year}/{district_id}` | Get single district details |
| GET | `/state/{year}` | Get state-level aggregates |
| GET | `/search` | Full-text search across entities |
| POST | `/query` | Flexible query endpoint |

### Admin Endpoints

Require admin API key.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/admin/import` | Upload and import Excel file |
| GET | `/admin/import/status/{id}` | Check import status |
| GET | `/admin/keys` | List all API keys |
| POST | `/admin/keys` | Create new API key |
| DELETE | `/admin/keys/{id}` | Revoke an API key |
| GET | `/admin/usage` | Get usage statistics |

## Usage Examples

Replace `rc_live_xxxxx` with your API key. Examples use the live API — swap the base URL for `http://localhost:8000` when running locally.

For a deep dive into `POST /query`, supplementary tables (`table_suffix`), schema-variation gotchas, and safe field-selection patterns, see **[docs/query-guide.md](docs/query-guide.md)**.

### Search for schools

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "https://reportcard-api-production.up.railway.app/search?q=Lincoln&type=school&limit=10"
```

### Get schools with filtering

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "https://reportcard-api-production.up.railway.app/schools/2024?city=Chicago&limit=20"
```

### Get districts for a year

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "https://reportcard-api-production.up.railway.app/districts/2023"
```

### Flexible query

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer rc_live_xxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2024,
    "entity_type": "school",
    "fields": ["rcdts", "name", "enrollment", "act_composite"],
    "filters": {
      "city": "Chicago",
      "enrollment": {"gte": 500}
    },
    "sort": {"field": "enrollment", "order": "desc"},
    "limit": 100
  }'
```

## Data Coverage

All 16 years (2010–2025) are imported. The schema varies by era:

| Years | Tables per year |
|-------|----------------|
| 2010–2017 | `schools_{year}` — demographics + ACT scores |
| 2018–2024 | `schools_{year}`, `districts_{year}`, `state_{year}` + supplementary tables (finance, IAR, SAT, CTE, etc.) |
| 2025 | `schools_2025` + supplementary tables including a separate `schools_act_2025` sheet |

For a full reference of supplementary table suffixes (sat, iar, act, finance, etc.) and how to query them, see **[docs/query-guide.md](docs/query-guide.md)**.

### Supplementary files not imported

The following files in `data/report-cards/` are intentionally excluded:

- **`school_11.xlsx` – `school_14.xlsx`** — Grade-level ISAT/PSAE/ACT proficiency for 2011–2014. These use a non-standard multi-row header format that requires a custom parser. The main `schools_{year}` tables for those years already include ACT composite and subject scores. Grade-level breakdowns could be added in the future if needed.
- **`2018-PARCC-SAT-Proficient.xlsx`** — Supplementary PARCC/SAT proficiency for 2018. PARCC and SAT data is already present in the main `schools_2018` table.
- **`RC13_layout.xlsx` – `RC17_layout.xlsx`** — Schema layout documentation files, not data.

## Data Import

### CLI Import

```bash
# Import a single year (always dry-run first)
.venv/bin/python -m app.cli.import_data data/report-cards/24-RC-Pub-Data-Set.xlsx --year 2024 --dry-run
.venv/bin/python -m app.cli.import_data data/report-cards/24-RC-Pub-Data-Set.xlsx --year 2024

# List imported years
.venv/bin/python -m app.cli.import_data --list-years
```

## Development

### Running Tests

```bash
# Run all tests (unit + integration + real-data)
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run only the real-data sanity tests (requires populated reportcard.db)
uv run pytest tests/test_real_data/ -v

# Run a specific test file
uv run pytest tests/test_api/test_schools.py
```

### Test Strategy

| Suite | DB | What it tests |
|-------|----|---------------|
| `tests/test_api/`, `tests/test_services/`, `tests/test_utils/` | In-memory SQLite | API logic, endpoint behaviour, utility functions |
| `tests/test_integration/` | Temp file-based SQLite | Full import pipeline end-to-end |
| `tests/test_real_data/` | Real `data/reportcard.db` | Row counts, data shape, year boundary conditions across all 16 years |

The real-data tests skip automatically if `data/reportcard.db` is absent or empty, so CI without the database still passes cleanly.

### Project Structure

```
ReportCardAPI/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings, environment variables
│   ├── dependencies.py      # Dependency injection
│   ├── api/                 # API route handlers
│   ├── services/            # Business logic
│   ├── models/              # Database and Pydantic models
│   ├── cli/                 # CLI commands
│   └── utils/               # Utility functions
├── tests/                   # Test suite
├── data/                    # SQLite database
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | development or production | development |
| `DATABASE_URL` | SQLite database path | sqlite:///./data/reportcard.db |
| `ADMIN_API_KEY` | Initial admin key for bootstrapping | - |
| `RATE_LIMIT_REQUESTS` | Default requests per window | 100 |
| `RATE_LIMIT_WINDOW_SECONDS` | Rate limit window | 60 |

## Rate Limiting Tiers

| Tier | Requests/Minute |
|------|-----------------|
| free | 100 |
| standard | 1,000 |
| premium | 10,000 |

## Deployment

The app is deployed on Railway using a Docker image hosted on Docker Hub (`kpfister44/reportcard-api:latest`). The database is baked into the image — no persistent volume required.

### Redeploying after code changes

```bash
# 1. Rebuild for linux/amd64 and push to Docker Hub
docker buildx build --platform linux/amd64 -t kpfister44/reportcard-api:latest --push .

# 2. Trigger Railway redeploy
railway redeploy --service reportcard-api --yes
```

### Required environment variables (set in Railway dashboard)

| Variable | Value |
|----------|-------|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `sqlite:///./data/reportcard.db` |
| `ADMIN_API_KEY` | Bootstrap admin key — set once, creates the first admin key on startup |

### Self-hosting

The app runs on any platform that supports Docker. Set the environment variables above, expose port `8000`, and use `GET /health` as your health check endpoint.

## License

[License TBD]

## Data Source

Data sourced from the [Illinois State Board of Education (ISBE)](https://www.isbe.net/) Illinois Report Card Public Data Set.
