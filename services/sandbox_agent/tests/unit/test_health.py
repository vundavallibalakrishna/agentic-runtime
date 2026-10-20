"""Health routes for sandbox-agent."""

from fastapi.testclient import TestClient

from ar_sandbox_agent.main import create_application


def test_ar_sandbox_agent_healthz() -> None:
    client = TestClient(create_application())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
