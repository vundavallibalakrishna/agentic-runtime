"""Health routes for model-gateway."""

from fastapi.testclient import TestClient

from ar_model_gateway.main import create_application


def test_ar_model_gateway_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
