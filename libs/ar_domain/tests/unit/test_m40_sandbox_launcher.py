"""A registered launcher starts a container for a new sandbox and stops it. Task: M40-T01e.

The launcher is injected on the store, so the test registers its own stand-in from setup;
``ensure_scope`` never knows a real docker daemon from this one.
"""

from __future__ import annotations

import pytest

from ar_domain.chat.service import demo_id
from ar_domain.sandboxes.runtime import SandboxStartError, ensure_scope, terminate_row
from ar_testing.demo import demo_store


class _StubLauncher:
    """Records the calls ``ensure_scope`` and ``terminate`` make, without a container."""

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.started: list[tuple[str, str]] = []
        self.stopped: list[str] = []

    def start(self, name: str, token: str) -> dict[str, object]:
        self.started.append((name, token))
        if self.fail:
            raise RuntimeError("daemon unreachable")
        return {
            "container_id": f"cid-{name}",
            "endpoint_url": "http://127.0.0.1:12345",
            "token": token,
        }

    def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)


def _ensure(store: object, launcher: object | None, scope_key: str) -> dict[str, object]:
    if launcher is not None:
        store.sandbox_launcher = launcher  # type: ignore[attr-defined]
    return ensure_scope(
        store,
        tenant_id=demo_id("tenant"),
        template_slug="python-data",
        scope="conversation",
        scope_key=scope_key,
        conversation_id=None,
        agent_id=None,
        user_id=demo_id("admin"),
    )


def test_a_registered_launcher_starts_a_container_and_stamps_the_row() -> None:
    store = demo_store()
    launcher = _StubLauncher()
    row = _ensure(store, launcher, "conv:launch")
    assert row["endpoint_url"] == "http://127.0.0.1:12345"
    assert str(row["container_id"]).startswith("cid-ar-sbx-")
    assert row["agent_token"] == row["token"]
    assert row["driver_ref"] == f"docker:{row['container_id']}"
    # The name the launcher received is derived from the sandbox id, not guessable.
    assert launcher.started and launcher.started[0][0].startswith("ar-sbx-")
    assert launcher.started[0][1] == row["token"]


def test_without_a_launcher_the_tools_run_on_the_host() -> None:
    store = demo_store()
    row = _ensure(store, None, "conv:host")
    assert row["endpoint_url"] is None
    assert row.get("container_id") is None


def test_a_failed_start_fails_the_sandbox_and_does_not_fall_back() -> None:
    store = demo_store()
    launcher = _StubLauncher(fail=True)
    with pytest.raises(SandboxStartError):
        _ensure(store, launcher, "conv:fail")
    failed = [r for r in store.sandboxes.values() if r.get("scope_key") == "conv:fail"]
    assert failed and failed[0]["status"] == "failed"
    assert failed[0]["endpoint_url"] is None
    assert "daemon unreachable" in str(failed[0]["error"])


def test_terminate_stops_the_container() -> None:
    store = demo_store()
    launcher = _StubLauncher()
    row = _ensure(store, launcher, "conv:terminate")
    container_id = row["container_id"]
    terminate_row(store, row, actor=demo_id("admin"))
    assert launcher.stopped == [str(container_id)]
    assert row["status"] == "terminated"
    assert row["endpoint_url"] is None
    assert row["container_id"] is None


def test_terminate_without_a_container_is_a_no_op() -> None:
    store = demo_store()
    row = _ensure(store, None, "conv:nocontainer")
    launcher = _StubLauncher()
    store.sandbox_launcher = launcher  # registered only now, row has no container_id
    terminate_row(store, row, actor=demo_id("admin"))
    assert launcher.stopped == []
    assert row["status"] == "terminated"
