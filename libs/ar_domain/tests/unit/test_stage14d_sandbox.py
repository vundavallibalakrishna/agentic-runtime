"""A computer is started by the sandbox manager, and code runs in it. Proof: unit.

The agent in these tests is the product's own sandbox agent, served in process over a
temporary folder. No container is started: the launcher is registered from test setup.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from fastapi.testclient import TestClient

from ar_common.settings import BaseServiceSettings, EnvName
from ar_domain.chat.service import demo_id
from ar_domain.readmodel.boot import build_product_store
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.manager_launch import (
    NoSandboxImage,
    SandboxManagerLauncher,
    docker_launcher,
)
from ar_domain.sandboxes.runtime import SandboxStartError, agent_token, ensure_scope, terminate_row
from ar_domain.tools.handlers import dispatch
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from pathlib import Path

_ENDPOINT = "http://computer.test"


class _Computer:
    """A launcher that hands out the in-process agent, as docker would hand out a container."""

    def __init__(self) -> None:
        self.stopped: list[str] = []

    def start(self, name: str, token: str) -> dict[str, object]:
        return {"container_id": name, "endpoint_url": _ENDPOINT, "token": token}

    def stop(self, container_id: str) -> None:
        self.stopped.append(container_id)


@pytest.fixture
def computer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Serve the sandbox agent in process and send the product's calls to it."""
    from ar_sandbox_agent.main import create_application

    monkeypatch.setenv("AR_SANDBOX_ROOT", str(tmp_path))
    monkeypatch.delenv("AR_SANDBOX_TOKEN", raising=False)
    agent = create_application()
    monkeypatch.setattr(
        runtime.httpx, "Client", lambda **_kw: TestClient(agent, base_url=_ENDPOINT)
    )
    monkeypatch.setattr(
        runtime.httpx, "get", lambda url, **_kw: TestClient(agent, base_url=_ENDPOINT).get(url)
    )
    return tmp_path


def _call(store: Any, tool: str, **arguments: object) -> dict[str, Any]:
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, None)
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "run it", schedule=False
    )
    who = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_conversation_id": uuid.UUID(str(conversation["id"])),
        "_run_id": uuid.UUID(str(posted["run"]["id"])),
    }
    return dispatch(store, "builtin://general", tool, {**arguments, **who}, "")


def _ensure(store: Any, scope_key: str) -> dict[str, object]:
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


def test_code_runs_in_the_computer_and_its_file_comes_back(computer: Path) -> None:
    store = demo_store()
    store.sandbox_launcher = _Computer()
    source = "open('answer.txt', 'w').write('forty-two')\nprint(6 * 7)"
    result = _call(store, "code", source=source)
    assert result["is_error"] is False, result
    assert "42" in result["text"]
    # The script ran in the computer's folder, not in this process's.
    assert (computer / "workspace" / "answer.txt").read_text() == "forty-two"
    names = [row["name"] for row in result["structured"]["presentation"]["files"]]
    assert "answer.txt" in names


def test_a_shell_command_runs_in_the_computer(computer: Path) -> None:
    store = demo_store()
    store.sandbox_launcher = _Computer()
    result = _call(store, "shell", command="echo from-the-computer && pwd")
    assert result["is_error"] is False, result
    assert "from-the-computer" in result["text"]
    assert str(computer) in result["text"] or "/workspace" in result["text"]


def test_without_a_computer_code_does_not_run_on_a_host_that_forbids_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ar_domain.tools import general

    monkeypatch.setattr(general, "host_exec_allowed", lambda: False)
    result = _call(demo_store(), "code", source="print(1)")
    assert result["is_error"] is True
    assert result["code"] == "sandbox_unavailable"


def test_a_file_is_read_whole_however_long_it_is(computer: Path) -> None:
    store = demo_store()
    store.sandbox_launcher = _Computer()
    row = _ensure(store, "conv:long")
    long = bytes(range(256)) * 1000  # 256 kB, four read windows
    (computer / "workspace").mkdir(exist_ok=True)
    (computer / "workspace" / "long.bin").write_bytes(long)
    assert runtime.read_computer_file(row, "/workspace/long.bin") == long
    assert runtime.read_computer_file(row, "/workspace/absent.bin") is None


def test_an_exported_file_has_its_bytes_in_the_object_store(computer: Path) -> None:
    from ar_domain.files.objects import fetch_bytes

    store = demo_store()
    store.sandbox_launcher = _Computer()
    (computer / "workspace").mkdir(exist_ok=True)
    (computer / "workspace" / "proof.txt").write_text("bytes-survive")
    who = {"_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin")}
    result = runtime.run_tool(store, "export_file", {"path": "/workspace/proof.txt", **who})
    assert result["is_error"] is False, result
    row = store.files[uuid.UUID(result["structured"]["file_id"])]
    # Another process has no copy in memory. It reads the object store.
    store.blobs.clear()
    assert fetch_bytes(store, row) == b"bytes-survive"


def test_the_token_is_sealed_and_read_back_by_a_later_request() -> None:
    store = demo_store()
    store.sandbox_launcher = _Computer()
    row = _ensure(store, "conv:token")
    token = str(row["token"])
    row.pop("token")
    row.pop("agent_token")
    assert agent_token(store, row) == token
    sealed = [
        r for r in store.named_secrets.values() if str(r["name"]).startswith("sandbox-agent:")
    ]
    assert sealed and token.encode() not in bytes(sealed[0]["ciphertext"])


def test_no_image_says_which_setting_to_change(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_SANDBOX_IMAGE", raising=False)
    launcher = docker_launcher()
    assert isinstance(launcher, NoSandboxImage)
    store = demo_store()
    store.sandbox_launcher = launcher
    with pytest.raises(SandboxStartError, match="AR_SANDBOX_IMAGE"):
        _ensure(store, "conv:no-image")


def test_a_lost_container_is_started_again(computer: Path) -> None:
    del computer
    store = demo_store()
    launcher = _Computer()
    store.sandbox_launcher = launcher
    row = _ensure(store, "conv:lost")
    row["endpoint_url"] = "http://gone.test"
    started: list[str] = []
    original = launcher.start

    def start(name: str, token: str) -> dict[str, object]:
        started.append(name)
        return original(name, token)

    launcher.start = start  # type: ignore[method-assign]
    # The agent at the old address does not answer, so the next call starts a new one.
    import ar_domain.sandboxes.runtime as module

    real = module.httpx.get

    def get(url: str, **kwargs: object) -> httpx.Response:
        if "gone.test" in url:
            raise httpx.ConnectError("gone")
        return real(url, **kwargs)

    module.httpx.get = get  # type: ignore[assignment]
    try:
        again = _ensure(store, "conv:lost")
    finally:
        module.httpx.get = real  # type: ignore[assignment]
    assert started
    assert again["id"] == row["id"]
    assert again["endpoint_url"] == _ENDPOINT


def test_a_client_process_asks_the_manager_for_the_computer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://manager.test")
    store = demo_store()
    store.sandbox_launcher = SandboxManagerLauncher("http://manager.test")
    made = uuid.uuid4()
    answers: list[dict[str, object]] = [
        {
            "id": str(made),
            "status": "ready",
            "endpoint_url": _ENDPOINT,
            "token": "t",
            "driver": "docker",
        },
        {"id": str(made), "status": "ready", "token": "t"},
        {"status": "quota_exceeded", "detail": "no more computers"},
    ]
    asked: list[str] = []

    def post(url: str, **_kw: object) -> httpx.Response:
        asked.append(url)
        return httpx.Response(200, json=answers.pop(0), request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    row = _ensure(store, "conv:managed")
    assert asked == ["http://manager.test/internal/v1/sandboxes:ensure"]
    assert (row["id"], row["endpoint_url"], row["token"], row["driver"]) == (
        made,
        _ENDPOINT,
        "t",
        "docker",
    )
    # The manager is the only one that starts computers: no address is a failure, not a host run.
    with pytest.raises(SandboxStartError, match="no address"):
        _ensure(store, "conv:managed")
    with pytest.raises(RuntimeError, match="no more computers"):
        _ensure(store, "conv:managed")
    # Ending the computer asks the manager to stop the container.
    terminate_row(store, row, actor=demo_id("admin"))
    assert asked[-1] == f"http://manager.test/internal/v1/sandboxes/{made}:release"
    assert row["status"] == "terminated"


def test_every_process_but_the_manager_is_told_where_computers_come_from(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://manager.test")
    monkeypatch.setenv("AR_SANDBOX_DRIVER", "kubernetes")
    settings = BaseServiceSettings(_env_file=None, env=EnvName.DEV)
    client = build_product_store(settings)
    assert isinstance(client.sandbox_launcher, SandboxManagerLauncher)
    manager = build_product_store(settings, starts_sandboxes=True)
    assert manager.sandbox_launcher is None
