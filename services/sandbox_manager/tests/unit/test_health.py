"""Health routes for sandbox-manager."""

from fastapi.testclient import TestClient

from ar_sandbox_manager.main import create_application


def test_ar_sandbox_manager_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
