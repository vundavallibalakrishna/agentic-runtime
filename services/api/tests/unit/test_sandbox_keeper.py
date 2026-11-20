"""An API that starts computers itself ends them when it stops. Proof: unit."""

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_domain.sandboxes.runtime import ensure_scope
from ar_testing.demo import demo_application


class _Docker:
    """Stands in for docker: it records the containers it was asked to start and stop."""

    install_id = "keeper-test"

    def __init__(self) -> None:
        self.running: set[str] = set()

    def start(
        self, name: str, token: str, sandbox_id: str = "", tenant_id: str = ""
    ) -> dict[str, object]:
        del sandbox_id, tenant_id
        self.running.add(name)
        return {"container_id": name, "endpoint_url": "http://127.0.0.1:1", "token": token}

    def stop(self, container_id: str) -> None:
        self.running.discard(container_id)

    def containers(self) -> list[dict[str, object]]:
        return []

    def unlabelled(self) -> list[str]:
        return []


def test_shutdown_ends_the_computers_this_process_started() -> None:
    app = demo_application()
    store = app.state.chat
    docker = _Docker()
    store.sandbox_launcher = docker
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        row = ensure_scope(
            store,
            tenant_id=demo_id("tenant"),
            template_slug="python-data",
            scope="conversation",
            scope_key="conv:keeper",
            conversation_id=None,
            agent_id=None,
            user_id=demo_id("admin"),
        )
        assert docker.running == {row["container_id"]}
    # Leaving the block is the server shutting down.
    assert not docker.running
    assert row["status"] == "terminated"
    assert "sandbox.terminated" in [item["action"] for item in store.audit_log]
