"""Health routes for mcp-openapi."""

from fastapi.testclient import TestClient

from ar_mcp_openapi.main import create_application


def test_ar_mcp_openapi_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
