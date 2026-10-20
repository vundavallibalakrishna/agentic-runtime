"""Health routes for system-worker."""

from fastapi.testclient import TestClient

from ar_system.main import TASK_QUEUE, create_application


def test_ar_system_healthz() -> None:
    client = TestClient(create_application())
    assert client.get("/healthz").status_code == 200
    assert TASK_QUEUE
