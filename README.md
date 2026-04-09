# Illinois Report Card API

A comprehensive REST API for accessing Illinois public school data from the Illinois Report Card. Provides programmatic access to school, district, and state-level education data including enrollment, demographics, assessment scores, and more.

## Live API

**Base URL:** `https://reportcard-api-production.up.railway.app`

- `GET /health` — public health check (no auth required)
- All other endpoints require `Authorization: Bearer <api_key>`

**To request an API key**, email [kpfister44@gmail.com](mailto:kpfister44@gmail.com) with a brief description of your intended use.

## Features

- **15 Years of Data**: 2010–2024 Illinois Report Card data fully imported and queryable
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

All 15 years (2010–2024) are imported. The schema varies by era:

| Years | Tables per year |
|-------|----------------|
| 2010–2017 | `schools_{year}` — demographics + ACT scores |
| 2018–2024 | `schools_{year}`, `districts_{year}`, `state_{year}` + supplementary tables (finance, IAR, SAT, CTE, etc.) |

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
| `tests/test_real_data/` | Real `data/reportcard.db` | Row counts, data shape, year boundary conditions across all 15 years |

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
