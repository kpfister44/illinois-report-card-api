# ABOUTME: Real-data integration tests against the populated reportcard.db
# ABOUTME: Sanity-checks row counts, data shape, and boundary conditions across all imported years

import re


# ---------------------------------------------------------------------------
# Year coverage
# ---------------------------------------------------------------------------

def test_years_returns_all_16_years(real_client, auth_header):
    """GET /years must include every year from 2010 through 2025 (exactly 16)."""
    response = real_client.get("/years", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    years = data["data"]
    assert data["meta"]["count"] == 16
    assert set(years) == set(range(2010, 2026))


# ---------------------------------------------------------------------------
# Schools endpoints
# ---------------------------------------------------------------------------

def test_schools_2024_row_count(real_client, auth_header):
    """schools_2024 should have roughly 3835 rows (allow ±50 for data revisions)."""
    response = real_client.get("/schools/2024?limit=1", headers=auth_header)
    assert response.status_code == 200
    total = response.json()["meta"]["total"]
    assert 3785 <= total <= 3885, f"Unexpected schools_2024 row count: {total}"


def test_schools_oldest_year_has_data(real_client, auth_header):
    """schools_2010 must have rows and each record must include rcdts and school_name."""
    response = real_client.get("/schools/2010?limit=5", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] > 0
    for record in data["data"]:
        assert "rcdts" in record
        assert "school_name" in record


def test_schools_last_single_sheet_year(real_client, auth_header):
    """schools_2017 (last pre-multi-sheet year) must have rows with core fields."""
    response = real_client.get("/schools/2017?limit=5", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] > 0
    record = data["data"][0]
    assert "rcdts" in record
    assert "school_name" in record


# ---------------------------------------------------------------------------
# Districts endpoints
# ---------------------------------------------------------------------------

def test_districts_2024_row_count(real_client, auth_header):
    """districts_2024 should have roughly 866 rows (allow ±30)."""
    response = real_client.get("/districts/2024?limit=1", headers=auth_header)
    assert response.status_code == 200
    total = response.json()["meta"]["total"]
    assert 836 <= total <= 896, f"Unexpected districts_2024 row count: {total}"


def test_districts_first_available_year(real_client, auth_header):
    """districts_2018 (first year with district tables) must return data."""
    response = real_client.get("/districts/2018?limit=1", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["meta"]["total"] > 0


def test_districts_pre2018_returns_404(real_client, auth_header):
    """Requesting districts for a pre-2018 year must return 404 NOT_FOUND."""
    response = real_client.get("/districts/2017", headers=auth_header)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# State endpoints
# ---------------------------------------------------------------------------

def test_state_2024_returns_single_record(real_client, auth_header):
    """GET /state/2024 must return exactly one record containing an rcdts field."""
    response = real_client.get("/state/2024", headers=auth_header)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data is not None
    assert "rcdts" in data


def test_state_first_available_year(real_client, auth_header):
    """GET /state/2018 (first year with state table) must return a record."""
    response = real_client.get("/state/2018", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["data"] is not None


def test_state_pre2018_returns_404(real_client, auth_header):
    """Requesting state for a pre-2018 year must return 404 NOT_FOUND."""
    response = real_client.get("/state/2015", headers=auth_header)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_returns_real_results(real_client, auth_header):
    """Searching for 'Chicago' must return at least one result with a valid entity_type."""
    response = real_client.get("/search?q=Chicago", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["total"] > 0
    valid_types = {"school", "district", "state"}
    for record in data["data"]:
        assert record["entity_type"] in valid_types


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def test_rcdts_format_is_valid(real_client, auth_header):
    """RCDTS codes in schools_2024 must be 15-digit numeric strings."""
    response = real_client.get("/schools/2024?limit=10", headers=auth_header)
    assert response.status_code == 200
    for record in response.json()["data"]:
        rcdts = record.get("rcdts", "")
        assert re.match(r"^\d{15}$", rcdts), f"Invalid RCDTS format: {rcdts!r}"
