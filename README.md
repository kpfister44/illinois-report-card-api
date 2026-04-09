# Illinois Report Card API

A comprehensive REST API for accessing Illinois public school data from the Illinois Report Card. Provides programmatic access to school, district, and state-level education data including enrollment, demographics, assessment scores, and more.

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
git clone <repository-url>
cd ReportCardAPI

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

### Search for schools

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "http://localhost:8000/search?q=Lincoln&type=school&limit=10"
```

### Get schools with filtering

```bash
curl -H "Authorization: Bearer rc_live_xxxxx" \
  "http://localhost:8000/schools/2024?city=Chicago&type=high&limit=20"
```

### Flexible query

```bash
curl -X POST "http://localhost:8000/query" \
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
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=app --cov-report=term-missing

# Run specific test file
uv run pytest tests/test_api/test_schools.py
```

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

### Railway

1. Install Railway CLI: `npm i -g @railway/cli`
2. Login: `railway login`
3. Initialize project: `railway init`
4. Deploy: `railway up`
5. Set environment variables in Railway dashboard:
   - `ENVIRONMENT=production`
   - `ADMIN_API_KEY=<your-admin-key>`

### Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Login: `fly auth login`
3. Launch app: `fly launch`
4. Set secrets:
   ```bash
   fly secrets set ENVIRONMENT=production
   fly secrets set ADMIN_API_KEY=<your-admin-key>
   ```
5. Deploy: `fly deploy`

### Docker-Compatible Platforms

The application works on any platform supporting Docker containers (AWS ECS, Google Cloud Run, Azure Container Instances, etc.):

**Required Configuration:**
- Container port: `8000`
- Persistent volume: `/app/data` (for SQLite database)
- Environment variables:
  - `ENVIRONMENT=production`
  - `DATABASE_URL=sqlite:///./data/reportcard.db`
  - `ADMIN_API_KEY=<your-secure-key>` (optional, for admin endpoints)

**Health Check Endpoint:** `GET /health` (returns `{"status": "ok"}`)

## License

[License TBD]

## Data Source

Data sourced from the [Illinois State Board of Education (ISBE)](https://www.isbe.net/) Illinois Report Card Public Data Set.
