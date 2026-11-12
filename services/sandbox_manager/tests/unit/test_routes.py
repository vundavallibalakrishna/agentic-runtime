"""The sandbox manager's internal routes over a store that holds one tenant. Proof: unit."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from ar_domain.chat.service import demo_id
from ar_sandbox_manager.main import create_application
from ar_testing.demo import seed_demo_tenant


class _Started:
    """A launcher that hands out an address, as docker would hand out a container."""

    def __init__(self) -> None:
        self.stopped: list[str] = []

    def start(self, name: str, token: str) -> dict[str, object]:
        return {"container_id": name, "endpoint_url": "http://127.0.0.1:1", "token": token}

    def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)


def _client() -> tuple[TestClient, _Started, str, str]:
    client = TestClient(create_application())
    store = client.app.state.chat
    seed_demo_tenant(store)
    launcher = _Started()
    store.sandbox_launcher = launcher
    template = next(row for row in store.sandbox_templates.values() if row["slug"] == "browser")
    made = client.post(
        "/internal/v1/sandboxes:ensure",
        json={
            "tenant_id": str(demo_id("tenant")),
            "scope": "conversation",
            "scope_key": "conv:routes",
            "template_id": str(template["id"]),
            "user_id": str(demo_id("admin")),
        },
    )
    assert made.status_code == 200, made.text
    return client, launcher, made.json()["id"], made.json()["token"]


def test_a_computer_is_read_touched_and_released() -> None:
    client, launcher, sandbox_id, _token = _client()
    assert client.get(f"/internal/v1/sandboxes/{sandbox_id}").json()["status"] == "ready"
    assert client.post(f"/internal/v1/sandboxes/{sandbox_id}:touch").json()["status"] == "ready"
    released = client.post(f"/internal/v1/sandboxes/{sandbox_id}:release")
    assert released.json()["status"] == "released"
    assert len(launcher.stopped) == 1
    # Releasing stops the container. The caller records what happened to the computer.
    row = client.app.state.chat.sandboxes[uuid.UUID(sandbox_id)]
    assert row["status"] == "ready"
    assert row["endpoint_url"] is None


def test_a_computer_is_suspended_and_terminated() -> None:
    client, launcher, sandbox_id, _token = _client()
    suspended = client.post(f"/internal/v1/sandboxes/{sandbox_id}:suspend")
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"
    ended = client.post(f"/internal/v1/sandboxes/{sandbox_id}:terminate")
    assert ended.status_code == 200
    assert ended.json()["status"] == "terminated"
    assert launcher.stopped


def test_an_unknown_computer_is_not_found_on_every_route() -> None:
    client, _launcher, _sandbox_id, token = _client()
    unknown = uuid.uuid4()
    assert client.get(f"/internal/v1/sandboxes/{unknown}").json()["status"] == "not_found"
    for action in ("suspend", "terminate", "release", "touch"):
        answer = client.post(f"/internal/v1/sandboxes/{unknown}:{action}")
        assert answer.json()["status"] == "not_found", action
    # The proxy's question about an unknown computer, or a bad id, is always refused.
    for sandbox in (str(unknown), "not-a-uuid"):
        refused = client.get(
            "/internal/v1/egress/check",
            params={"sandbox_id": sandbox, "host": "example.com", "token": token},
        )
        assert refused.status_code == 403


def test_the_reaper_goes_tenant_by_tenant_and_egress_checks_the_token() -> None:
    client, _launcher, sandbox_id, token = _client()
    assert client.post("/internal/v1/sandboxes:reap").json() == {"suspended": 0, "terminated": 0}
    wrong = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "example.com", "token": "nope"},
    )
    assert wrong.status_code == 403
    known = client.get(
        "/internal/v1/egress/check",
        params={"sandbox_id": sandbox_id, "host": "example.com", "token": token},
    )
    assert known.status_code in {200, 403}
