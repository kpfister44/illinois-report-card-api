# ABOUTME: Health endpoint tests
# ABOUTME: Verifies the /health endpoint works without authentication


def test_health_endpoint_returns_ok(client):
    """Health endpoint should return status ok without authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
