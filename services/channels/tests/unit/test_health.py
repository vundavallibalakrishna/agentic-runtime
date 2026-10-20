"""Health routes for channels."""

from fastapi.testclient import TestClient

from ar_channels.main import create_application


def test_ar_channels_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
