"""Controlled browser: it runs in the sandbox, navigation is gated, and nothing stands in.

Spec: docs/03-specs/12-sandbox-manager.md. The browser tools drive Chromium on the agent's
computer. Until 25 November 2026 a second, in-process HTML engine answered them in dev
and CI when no computer was running (OQ-197). It is removed: with no computer there is no
browser, in any environment. What stays the same wherever the browser runs is the gate
on a navigation, which these tests cover with the call to the computer replaced.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.sandboxes import runtime
from ar_domain.sandboxes.browser import navigation_class
from ar_domain.sandboxes.runtime import run_tool
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import pytest

_NAMES = (
    "navigate",
    "snapshot",
    "click",
    "type",
    "press",
    "scroll",
    "submit_form",
    "screenshot",
    "new_tab",
)


def _arm(store: ChatService) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent = next(row for row in store.agents.values() if row.get("slug") == "revenue-analyst")
    version = store.versions[agent["published_version_id"]]
    version["definition"]["sandbox"] = {
        "enabled": True,
        "template": "browser",
        "scope": "conversation",
        "extra_egress_allowlist": ["127.0.0.1"],
    }
    settings = store.tenant_settings.setdefault(tenant, {})
    allow = settings.setdefault("egress_allowlist", ["example.com"])
    if isinstance(allow, list) and "127.0.0.1" not in allow:
        allow.append("127.0.0.1")
    template = next(row for row in store.sandbox_templates.values() if row.get("slug") == "browser")
    hosts = template.setdefault("egress_allowlist", [])
    if isinstance(hosts, list) and "127.0.0.1" not in hosts:
        hosts.append("127.0.0.1")
    return tenant, user, uuid.UUID(str(agent["id"]))


def _call(
    store: ChatService,
    name: str,
    *,
    tenant: uuid.UUID,
    user: uuid.UUID,
    agent: uuid.UUID,
    conversation: uuid.UUID,
    run: uuid.UUID | None,
    **extra: object,
) -> dict[str, object]:
    version_id = next(
        row["published_version_id"] for row in store.agents.values() if row.get("id") == agent
    )
    arguments: dict[str, object] = {
        "_tenant_id": tenant,
        "_user_id": user,
        "_agent_id": agent,
        "_agent_version_id": version_id,
        "_conversation_id": conversation,
    }
    if run is not None:
        arguments["_run_id"] = run
    arguments.update(extra)
    return run_tool(store, name, arguments)


def _computer(
    monkeypatch: pytest.MonkeyPatch, store: ChatService
) -> list[tuple[str, dict[str, object]]]:
    """Give every sandbox of ``store`` an address and record what is sent to it."""
    sent: list[tuple[str, dict[str, object]]] = []
    real = runtime._ensure_for_call

    def ensure(store_: object, arguments: dict[str, object]) -> dict[str, object]:
        book = real(store_, arguments)
        sandbox = book.get("sandbox")
        if isinstance(sandbox, dict):
            sandbox["endpoint_url"] = "http://computer.invalid:8090"
        return book

    def proxy(sandbox: dict[str, object], name: str, arguments: dict[str, object]) -> object:
        del sandbox
        public = {key: value for key, value in arguments.items() if not key.startswith("_")}
        sent.append((name, public))
        return {"text": f"{name} done", "structured": {"engine": "chromium"}, "is_error": False}

    monkeypatch.setattr(runtime, "_ensure_for_call", ensure)
    monkeypatch.setattr(runtime, "_proxy", proxy)
    return sent


def test_with_no_computer_every_browser_tool_says_so() -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    conversation = uuid.uuid4()
    for name in _NAMES:
        answer = _call(
            store,
            name,
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=None,
            url="https://example.com",
            ref="e1",
            text="hello",
        )
        assert answer["is_error"] is True, name
        assert answer["code"] == "sandbox_unavailable", name
        assert "no computer is running" in str(answer["text"]), name
    assert "engine" not in str(store.sandboxes), "no page was read in this process"


def test_an_allowed_page_goes_to_the_computer_and_a_private_one_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    sent = _computer(monkeypatch, store)
    conversation = uuid.uuid4()
    opened = _call(
        store,
        "navigate",
        tenant=tenant,
        user=user,
        agent=agent,
        conversation=conversation,
        run=None,
        url="https://example.com/desk",
    )
    assert opened["is_error"] is False
    assert sent == [("navigate", {"url": "https://example.com/desk"})]
    blocked = _call(
        store,
        "navigate",
        tenant=tenant,
        user=user,
        agent=agent,
        conversation=conversation,
        run=None,
        _browser_cleared=True,
        url="http://169.254.169.254/latest/meta-data",
    )
    assert blocked["code"] == "egress_denied"
    unnamed = _call(
        store, "click", tenant=tenant, user=user, agent=agent, conversation=conversation, run=None
    )
    assert unnamed["code"] == "validation_failed"
    assert len(sent) == 1, "neither refusal reached the computer"


def test_off_list_navigation_waits_and_private_hosts_stay_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    sent = _computer(monkeypatch, store)
    version_id = next(
        row["published_version_id"] for row in store.agents.values() if row.get("id") == agent
    )
    tool_id = next(
        row["id"]
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "browser.navigate"
    )
    store.browser_resolve = lambda host: ["93.184.216.34"]  # type: ignore[attr-defined]
    arguments = {"url": "https://off-list.example/desk"}
    digest = call_args_hash(str(tool_id), arguments)
    request = {
        "tenant_id": tenant,
        "user_id": user,
        "agent_id": agent,
        "agent_version_id": version_id,
        "tool_version_id": tool_id,
        "arguments": arguments,
        "args_hash": digest,
    }
    held = ToolPipeline(store).execute({**request, "run_id": uuid.uuid4()})
    assert held["status"] == "awaiting_approval"
    assert held["risk_class"] == "W2"
    assert sent == []
    approval_id = uuid.UUID(str(held["approval_id"]))
    store.approvals[approval_id]["status"] = "approved"
    opened = ToolPipeline(store).execute(
        {**request, "approval_id": approval_id, "run_id": uuid.uuid4()}
    )
    assert opened["status"] == "succeeded"
    assert sent == [("navigate", {"url": "https://off-list.example/desk"})]
    context = {"tenant_id": tenant, "agent_id": agent, "agent_version_id": version_id}
    assert navigation_class(store, context, "http://169.254.169.254/") == "deny"
    assert navigation_class(store, context, "https://off-list.example/desk") == "approve"
    # Without the approval the same address is refused before the computer is asked.
    direct = run_tool(
        store,
        "navigate",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_id": agent,
            "_agent_version_id": version_id,
            "_conversation_id": uuid.uuid4(),
            "url": "https://off-list.example/desk",
        },
    )
    assert direct["code"] == "egress_denied"
    assert len(sent) == 1
