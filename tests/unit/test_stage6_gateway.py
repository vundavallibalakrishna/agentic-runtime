"""Stage 6 gateway, worker steps, and sandbox confinement.

Proof labels: the cases in this file are unit (no cluster and no model).
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from ar_common.sandbox_docker import confined_host_config
from ar_domain.chat.service import demo_id
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.service import SandboxBook
from ar_domain.tools.agent_loop import run_agent_loop
from ar_domain.tools.gateway_client import execute_tool
from ar_mcp_gateway.main import create_application
from ar_testing.demo import demo_store
from ar_testing.demo_tenant import seed_demo_tenant
from ar_testing.internal_client import signed_client

if TYPE_CHECKING:
    import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_missing_gateway_url_is_a_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_MCP_GATEWAY_URL", raising=False)
    store = demo_store()
    store.tool_gateway_http = True
    result = execute_tool(store, {"tool_version_id": uuid.uuid4(), "arguments": {}})
    assert result["error"]["code"] == "gateway_unavailable"  # type: ignore[index]


def test_http_gateway_posts_the_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_MCP_GATEWAY_URL", "http://gateway.test")
    store = demo_store()
    store.tool_gateway_http = True
    seen: dict[str, object] = {}

    class _Response:
        status_code = 200

        def json(self) -> dict[str, str]:
            return {"status": "succeeded", "result_preview": "ok"}

        def close(self) -> None:
            return None

    def send(url: str, body: dict[str, object], timeout: float) -> _Response:
        seen["url"] = url
        seen["body"] = body
        seen["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("ar_domain.tools.gateway_client._send", send)
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    result = execute_tool(
        store,
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "tool_version_id": version["id"],
            "arguments": {},
            "model_call_id": "list",
        },
    )
    assert result["status"] == "succeeded"
    assert seen["url"] == "http://gateway.test/internal/v1/tool-calls:execute"
    body = seen["body"]
    assert isinstance(body, dict)
    assert body["tool_version_id"] == str(version["id"])


def test_gateway_audits_and_denies_a_host_off_the_allowlist() -> None:
    app = create_application()
    seed_demo_tenant(app.state.chat)
    store = app.state.chat
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    server = store.tool_server_versions[version["tool_server_version_id"]]
    server["endpoint_url"] = "https://blocked.example/mcp"
    client = signed_client(app)
    called = client.post(
        "/internal/v1/tool-calls:execute",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "modelCallId": "remote",
        },
    )
    assert called.status_code == 200, called.text
    body = called.json()
    assert body["error"]["code"] == "egress_denied"
    audit = [row for row in store.audit_log if row.get("detail", {}).get("via") == "gateway"]
    assert audit[-1]["action"] == "tool.denied"
    recorded = audit[-1]["detail"]["timeout_s"]
    expected = version.get("timeout_s")
    assert recorded == (expected if isinstance(expected, int) else 30)


def test_gateway_records_a_builtin_call(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_application()
    seed_demo_tenant(app.state.chat)
    store = app.state.chat

    def deny(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {"decision": "deny", "reasons": ["no"], "approval": None}

    monkeypatch.setattr("ar_domain.policy.engine.evaluate_call", deny)
    version = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "files.list"
    )
    client = signed_client(app)
    called = client.post(
        "/internal/v1/tool-calls:execute",
        json={
            "tenantId": str(demo_id("tenant")),
            "userId": str(demo_id("admin")),
            "toolVersionId": str(version["id"]),
            "arguments": {},
            "modelCallId": "policy",
        },
    )
    assert called.status_code == 200, called.text
    assert called.json()["error"]["code"] == "policy_denied"
    assert any(row.get("action") == "tool.denied" for row in store.audit_log)


def test_one_activity_is_one_step() -> None:
    store = demo_store()
    store._completion_call = lambda _tenant, alias="reasoning": (  # type: ignore[method-assign]
        "Qwen/Qwen3-32B",
        {},
        5.0,
        True,
    )
    pending = [
        {
            "text": "",
            "tool_calls": [
                {"id": "c1", "name": "control__checkpoint", "arguments": {"note": "ready"}}
            ],
            "usage": {"tokens_in": 2, "tokens_out": 2},
        },
        {
            "text": "Checkpoint saved: ready",
            "tool_calls": [],
            "usage": {"tokens_in": 2, "tokens_out": 4},
        },
    ]

    async def complete(*_args: object, **_kwargs: object) -> dict[str, object]:
        return pending.pop(0)

    store.complete_turn = complete  # type: ignore[method-assign]
    tenant = demo_id("tenant")
    user = demo_id("admin")
    conversation = store.create_conversation(tenant, user, None, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "Save a checkpoint", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    run = store.runs[run_id]
    conversation_row = store.conversations[uuid.UUID(str(run["conversation_id"]))]
    agent = store.agents[uuid.UUID(str(conversation_row["agent_id"]))]
    store._prepare_run(run, conversation_row, agent, "Save a checkpoint")
    assistant = store.messages[uuid.UUID(str(run["assistant_message_id"]))]
    assert asyncio.run(run_agent_loop(store, run, assistant, "Save a checkpoint", one_step=True))
    assert run["step_kind"] == "tools"
    assert run["status"] == "running"
    assert len(pending) == 1
    assert asyncio.run(run_agent_loop(store, run, assistant, "Save a checkpoint", one_step=True))
    assert run["step_kind"] == "model"
    assert len(pending) == 1
    assert asyncio.run(run_agent_loop(store, run, assistant, "Save a checkpoint", one_step=True))
    assert run["status"] == "completed"
    assert pending == []


def test_only_the_sandbox_manager_starts_a_confined_container() -> None:
    host = confined_host_config(
        "agentic-runtime_sandbox", cpu_millis=500, memory_mb=512, pids_limit=64
    )
    assert host["Memory"] == 512 * 1024 * 1024
    assert host["CapDrop"] == ["ALL"]
    for folder in ("services/api", "services/runtime", "services/mcp_gateway"):
        for path in (ROOT / folder).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "create_namespaced_pod" not in text
            assert "kubernetes_asyncio" not in text


def test_production_screenshot_needs_chromium() -> None:
    store = demo_store()
    store.fake_models_allowed = False
    SandboxBook(store).ensure_platform()
    conversation = store.create_conversation(demo_id("tenant"), demo_id("admin"), None)
    posted = store.post_message(
        demo_id("tenant"),
        demo_id("admin"),
        uuid.UUID(str(conversation["id"])),
        "look",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    result = runtime._browser(
        store,
        {
            "id": uuid.uuid4(),
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "template_id": demo_id("sandbox-template-browser"),
            "endpoint_url": None,
        },
        "screenshot",
        {"_run_id": str(run_id), "_tenant_id": demo_id("tenant"), "_user_id": demo_id("admin")},
    )
    assert result["is_error"] is True
    assert result["code"] == "sandbox_unavailable"


def test_compose_confines_sandbox_egress() -> None:
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "name: agentic-runtime_sandbox" in text
    assert "internal: true" in text
    assert "AR_SANDBOX_DOCKER_NETWORK: agentic-runtime_sandbox" in text
