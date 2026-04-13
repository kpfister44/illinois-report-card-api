# Query Guide

This guide covers the `POST /query` endpoint and schema introspection in detail. It explains how the data is organized into tables, how to access supplementary data, and the known behavioral quirks every consumer should understand before building on top of the API.

---

## How tables are organized

Data is stored in year-partitioned tables. Every year has a set of **main tables** and, for 2018 and later, a set of **supplementary tables** containing additional data sheets from the ISBE Excel files.

### Main tables

| Entity type | Table pattern | Years available |
|-------------|---------------|-----------------|
| School | `schools_{year}` | 2010–2025 |
| District | `districts_{year}` | 2018–2024 |
| State | `state_{year}` | 2018–2024 |

### Supplementary tables

Supplementary tables follow the pattern `{entity_type}_{suffix}_{year}`. The `entity_type` segment uses the plural form (`schools`, `districts`, `state`).

| Suffix | Content | Entity types | Years available |
|--------|---------|--------------|-----------------|
| `act` | ACT college-readiness scores | schools | 2025 |
| `cte` | Career and technical education | schools, districts, state | 2022–2025 (schools); 2022–2024 (districts, state) |
| `discipline` | Student discipline data | schools, districts, state | 2023–2025 (schools); 2023–2024 (districts, state) |
| `dlm` | Dynamic Learning Maps alternate assessment | schools, districts, state | 2018–2024 (gaps: no 2020) |
| `dlm2` | DLM alternate assessment (extended) | schools, districts, state | 2022–2024 |
| `elamathscience` | ELA, Math, Science proficiency by subgroup | schools, districts, state | 2018–2025 (schools); 2018–2024 (districts, state) |
| `finance` | Per-pupil expenditure and revenue | schools, districts, state | 2019–2025 (schools); 2018–2024 (districts, state) |
| `general2` | Additional general metrics (overflow sheet) | schools, districts, state | 2024–2025 (schools); 2024 (districts, state) |
| `iar` | Illinois Assessment of Readiness (IAR) | schools, districts, state | 2019–2025 (schools); 2019–2024 (districts, state); gap: no 2020 |
| `iar2` | IAR extended subgroup data | schools, districts, state | 2022–2024 |
| `isa` | Illinois Science Assessment | schools, districts, state | 2018–2024 (gap: no 2020) |
| `kids` | Kindergarten Individual Development Survey | schools, districts (2024 only) | 2025 (schools); 2024 (districts, state) |
| `parcc` | PARCC assessment (predecessor to IAR) | schools, districts, state | 2018 only |
| `sat` | SAT college readiness scores | schools, districts, state | 2018–2024 (gap: no 2020) |
| `teacher` | Teacher qualification and retention | schools, districts, state | 2023–2024 |

---

## Using `table_suffix` in POST /query

By default, `POST /query` queries the main table for the requested entity type and year (`schools_2024`, `districts_2023`, etc.). To query a supplementary table, pass `table_suffix` in the request body.

**Table name resolution:**
```
entity_type=school, table_suffix=sat, year=2024  →  schools_sat_2024
entity_type=district, table_suffix=iar, year=2023  →  districts_iar_2023
entity_type=school, year=2024 (no suffix)  →  schools_2024
```

### Example: SAT scores for Chicago schools in 2024

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer <your_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2024,
    "entity_type": "school",
    "table_suffix": "sat",
    "fields": ["rcdts", "school_name", "sat_reading_average_score", "sat_math_average_score"],
    "filters": {"city": "Chicago"},
    "sort": {"field": "sat_reading_average_score", "order": "DESC"},
    "limit": 20
  }'
```

### Example: IAR proficiency for districts in 2023

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer <your_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2023,
    "entity_type": "district",
    "table_suffix": "iar",
    "fields": ["rcdts", "district", "pct_all_students_iar_ela_level_4_grade_3", "pct_all_students_iar_mathematics_level_4_grade_3"],
    "limit": 50
  }'
```

### Example: ACT scores for 2025 (schools only)

```bash
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer <your_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "year": 2025,
    "entity_type": "school",
    "table_suffix": "act",
    "fields": ["rcdts", "school_name", "act_ela_average_score_grade_11", "act_math_average_score_grade_11"],
    "sort": {"field": "act_ela_average_score_grade_11", "order": "DESC"},
    "limit": 25
  }'
```

---

## Known behaviors and workarounds

### Requesting a missing field returns 400, not null

If a field in your `fields` array does not exist in the target table, the API returns a `400 INVALID_PARAMETER` error. This happens because field names are injected directly into the SQL `SELECT` clause — a missing column is a SQLite error.

**This is most likely to happen when:**
- A field exists in one year's table but not another (schemas change year-over-year)
- A field exists in a supplementary table but not the main table (e.g., `sat_composite` is in `schools_sat_2024`, not `schools_2024`)

**Safe pattern — probe before selecting:**

```bash
# Step 1: Check what fields exist in the target table for year X
curl -H "Authorization: Bearer <your_key>" \
  "https://reportcard-api-production.up.railway.app/schema/2022"

# Step 2: Filter the response to the table you care about
# (see "Understanding /schema/{year}" below)

# Step 3: Now query with confidence
curl -X POST "https://reportcard-api-production.up.railway.app/query" \
  -H "Authorization: Bearer <your_key>" \
  -H "Content-Type: application/json" \
  -d '{"year": 2022, "entity_type": "school", "fields": ["rcdts", "<verified_field>"], "limit": 1}'
```

Alternatively, omit `fields` entirely to get all columns with `SELECT *`.

---

### /schema/{year} returns fields from ALL tables for that year

`GET /schema/{year}` returns a flat list of every column across every table imported for that year — main tables and all supplementary tables combined. For a year like 2024, that means hundreds of fields from `schools_2024`, `districts_2024`, `state_2024`, `schools_sat_2024`, `schools_iar_2024`, and many more.

**Each field in the response includes `table_name`**, which tells you exactly which table that field belongs to. Use it to route fields correctly before querying.

**Example response entry:**
```json
{
  "table_name": "schools_sat_2024",
  "column_name": "sat_composite_all",
  "data_type": "float",
  "category": "assessment",
  "source_column_name": "SAT Composite - All Students",
  "is_suppressed_indicator": false
}
```

**Finding fields for a specific table:**

```bash
# Get all fields for the SAT supplementary table in 2024
curl -H "Authorization: Bearer <your_key>" \
  "https://reportcard-api-production.up.railway.app/schema/2024" \
  | jq '[.data[] | select(.table_name == "schools_sat_2024")]'
```

Filtering by `category` alone (via `GET /schema/{year}/{category}`) is **not** sufficient to identify which table a field belongs to — fields from multiple tables can share the same category.

---

## Field availability across years

Schema columns vary significantly by year. Useful strategies:

- **Check schema first**: Call `/schema/{year}` and filter by `table_name` before constructing queries.
- **Use omit-fields for exploration**: Query with no `fields` parameter and `limit=1` to see what a table actually returns.
- **Expect gaps**: Some tables don't exist for every year (see the suffix table above). If a combination of `entity_type + table_suffix + year` doesn't exist, the API returns `400 INVALID_PARAMETER`.
