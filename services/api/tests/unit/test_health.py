"""Health routes for api."""

from fastapi.testclient import TestClient

from ar_api.main import create_application


def test_ar_api_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
