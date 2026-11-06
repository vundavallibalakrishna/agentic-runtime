"""Health routes for api."""

from fastapi.testclient import TestClient

from ar_testing.demo import demo_application


def test_ar_api_healthz() -> None:
    client = TestClient(demo_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
