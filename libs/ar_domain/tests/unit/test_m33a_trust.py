"""Fresh-seed approval policy, fetch retries, and the search key path."""

import os
import uuid

import httpx
import pytest

from ar_common.errors import ForbiddenError, ValidationFailedError
from ar_domain.agents.access import Actor
from ar_domain.approvals.service import ApprovalBook
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import SYSTEM_ROLE_PERMISSIONS
from ar_domain.seed.approvals import (
    POLICY_MESSAGE,
    POLICY_NAME,
    install_seeded_write_policy,
    write_approval_document,
)
from ar_domain.tools.general import dispatch_general, remember_named_secret
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.searching import SearchUnavailableError, provider_for


def _actor(tenant: uuid.UUID, user: uuid.UUID, role: str) -> Actor:
    return Actor(
        tenant,
        user,
        frozenset(SYSTEM_ROLE_PERMISSIONS[role]),
        roles=frozenset({role}),
    )


def _http_version(store: ChatService) -> uuid.UUID:
    for version in store.tool_versions.values():
        if version.get("qualified_name") == "general.http":
            return uuid.UUID(str(version["id"]))
    raise AssertionError("general.http")


def _post(
    store: ChatService,
    tenant: uuid.UUID,
    user: uuid.UUID,
    agent_id: uuid.UUID,
    *,
    call: str,
) -> dict[str, object]:
    version_id = _http_version(store)
    arguments = {"method": "POST", "url": "https://example.com/hooks", "json": {"ok": True}}
    return ToolPipeline(store).execute(
        {
            "synthetic": True,
            "tenant_id": tenant,
            "user_id": user,
            "agent_id": agent_id,
            "tool_version_id": version_id,
            "arguments": arguments,
            "args_hash": call_args_hash(str(version_id), arguments),
            "model_call_id": call,
        }
    )


def test_requester_mode_lets_an_approver_decide_when_the_owner_is_the_requester() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    admin = demo_id("admin")
    approver = demo_id("approver")
    agent = store.ensure_assistant(tenant, admin)
    held = _post(store, tenant, admin, uuid.UUID(str(agent["id"])), call="deadlock")
    assert held["status"] == "awaiting_approval"
    approval_id = uuid.UUID(str(held["approval_id"]))
    row = store.approvals[approval_id]
    assert row["approver_rule"]["mode"] == "requester"
    body = {"decision": "approve", "args_hash": row["args_hash"]}
    owner = _actor(tenant, admin, "tenant_admin")
    with pytest.raises(ValidationFailedError, match="sod_violation") as blocked:
        ApprovalBook(store).decide(owner, approval_id, body, stepped_up=True)
    assert blocked.value.status == 422
    # M32-T03: segregation of duties blocks the owner, so another approver may decide
    # instead of the request waiting forever.
    ApprovalBook(store).decide(
        _actor(tenant, approver, "approver"), approval_id, body, stepped_up=True
    )
    assert store.approvals[approval_id]["status"] != "pending"


def test_seeded_users_policy_lets_the_approver_finish_the_write() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    admin = demo_id("admin")
    approver = demo_id("approver")
    member = demo_id("member")
    first = install_seeded_write_policy(store, tenant, approver_id=approver, owner_id=admin)
    assert install_seeded_write_policy(store, tenant, approver_id=approver, owner_id=admin) == first
    document = write_approval_document(approver_id=approver, owner_id=admin)
    rule = document["rules"][0]
    assert rule["approval"]["approvers"]["mode"] == "users"
    assert rule["approval"]["four_eyes"] is False
    agent = store.ensure_assistant(tenant, admin)
    agent_id = uuid.UUID(str(agent["id"]))

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url, kwargs
        return httpx.Response(200, text='{"json": {"ok": true}}')

    store.http_send = send  # type: ignore[attr-defined]
    held = _post(store, tenant, member, agent_id, call="seeded")
    assert held["status"] == "awaiting_approval"
    assert POLICY_MESSAGE in str(held["wrapped"])
    approval_id = uuid.UUID(str(held["approval_id"]))
    row = store.approvals[approval_id]
    assert row["approver_rule"]["mode"] == "users"
    assert str(approver) in row["approver_rule"]["users"]
    assert str(admin) in row["approver_rule"]["users"]
    assert row["policy_reasons"] == [POLICY_MESSAGE]
    body = {"decision": "approve", "args_hash": row["args_hash"]}
    with pytest.raises(ForbiddenError):
        ApprovalBook(store).decide(
            _actor(tenant, member, "member"), approval_id, body, stepped_up=True
        )
    with pytest.raises(ValidationFailedError, match="sod_violation") as blocked:
        ApprovalBook(store).decide(
            _actor(tenant, admin, "tenant_admin"), approval_id, body, stepped_up=True
        )
    assert blocked.value.status == 422
    assert store.approvals[approval_id]["status"] == "pending"
    ApprovalBook(store).decide(
        _actor(tenant, approver, "approver"), approval_id, body, stepped_up=True
    )
    assert store.approvals[approval_id]["status"] == "approved"
    version_id = _http_version(store)
    arguments = {"method": "POST", "url": "https://example.com/hooks", "json": {"ok": True}}
    finished = ToolPipeline(store).execute(
        {
            "synthetic": True,
            "tenant_id": tenant,
            "user_id": member,
            "agent_id": agent_id,
            "tool_version_id": version_id,
            "arguments": arguments,
            "args_hash": str(row["args_hash"]),
            "approval_id": approval_id,
            "model_call_id": "seeded-resume",
        }
    )
    assert finished["status"] == "succeeded"
    assert "HTTP 200" in str(finished["result_preview"])
    assert store.policies[first]["name"] == POLICY_NAME
    assert store.policies[first]["status"] == "active"


def test_fetch_retries_transient_failures_and_keeps_the_allowlist() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"egress_allowlist": ["example.com"]}
    sleeps: list[float] = []
    store.fetch_retry_sleep = sleeps.append  # type: ignore[attr-defined]
    calls = {"n": 0}

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, kwargs
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("refused")
        if calls["n"] == 2:
            return httpx.Response(503, text="busy")
        html = "<html><head><title>Notes</title></head><body><p>Body</p></body></html>"
        assert url.startswith("https://example.com/")
        return httpx.Response(200, text=html)

    store.http_send = send  # type: ignore[attr-defined]
    result = dispatch_general(
        store, "fetch", {"_tenant_id": tenant, "url": "https://example.com/notes"}
    )
    assert result["is_error"] is False
    assert "Notes" in str(result["text"])
    assert calls["n"] == 3
    assert sleeps == [0.25, 0.75]
    denied_calls = {"n": 0}

    def deny(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url, kwargs
        denied_calls["n"] += 1
        return httpx.Response(200, text="no")

    store.http_send = deny  # type: ignore[attr-defined]
    denied = dispatch_general(
        store, "fetch", {"_tenant_id": tenant, "url": "https://evil.example/phish"}
    )
    assert denied["code"] == "egress_denied"
    assert denied_calls["n"] == 0


def test_fetch_reports_a_timeout_after_the_retries_are_used() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"egress_allowlist": ["example.com"]}
    store.fetch_retry_sleep = lambda _delay: None  # type: ignore[attr-defined]
    calls = {"n": 0}

    def send(method: str, url: str, **kwargs: object) -> httpx.Response:
        del method, url, kwargs
        calls["n"] += 1
        raise httpx.ConnectTimeout("slow")

    store.http_send = send  # type: ignore[attr-defined]
    result = dispatch_general(
        store, "fetch", {"_tenant_id": tenant, "url": "https://example.com/slow"}
    )
    assert result["code"] == "upstream_error"
    assert calls["n"] == 3
    text = str(result["text"])
    assert "example.com" in text
    assert "timed out" in text
    assert "3" in text
    assert result["structured"]["presentation"]["attempts"] == 3
    assert "slow" not in text


def test_search_uses_the_named_secret_and_hides_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_SEARCH_PROVIDER", "tavily")
    monkeypatch.setenv("AR_SEARCH_API_KEY", "env-key-value")
    store = ChatService()
    tenant = demo_id("tenant")
    remember_named_secret(store, tenant, "search-live", "secret-key-value")
    store.tenant_settings[tenant] = {"search": {"provider": "brave", "secretName": "search-live"}}
    seen: dict[str, str] = {}

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs.get("headers")
        token = ""
        if isinstance(headers, dict):
            token = str(headers.get("X-Subscription-Token") or "")
        seen["url"] = url
        seen["token"] = token
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "title": "Row secret-key-value",
                            "url": "https://example.com/hit",
                            "snippet": "see secret-key-value",
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr("ar_domain.tools.searching.httpx.get", fake_get)
    result = dispatch_general(store, "search", {"_tenant_id": tenant, "query": "widgets"})
    assert seen["url"].startswith("https://api.search.brave.com/")
    assert seen["token"] == "secret-key-value"  # noqa: S105
    text = str(result["text"])
    assert result["is_error"] is False
    assert "secret-key-value" not in text
    assert "env-key-value" not in text
    assert "[redacted]" in text


def test_search_falls_back_to_the_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AR_SEARCH_API_KEY", "env-key-value")
    store = ChatService()
    tenant = demo_id("tenant")
    store.tenant_settings[tenant] = {"search": {"provider": "tavily", "secret_name": "missing"}}
    seen: dict[str, str] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        body = kwargs.get("json")
        key = ""
        if isinstance(body, dict):
            key = str(body.get("api_key") or "")
        seen["url"] = url
        seen["key"] = key
        return httpx.Response(401, json={"error": "bad env-key-value"})

    monkeypatch.setattr("ar_domain.tools.searching.httpx.post", fake_post)
    result = dispatch_general(store, "search", {"_tenant_id": tenant, "query": "widgets"})
    assert seen["url"] == "https://api.tavily.com/search"
    assert seen["key"] == "env-key-value"
    assert result["code"] == "search_rejected"
    assert "env-key-value" not in str(result["text"])


def test_search_without_a_key_does_not_call_a_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AR_SEARCH_API_KEY", raising=False)
    monkeypatch.setenv("AR_SEARCH_PROVIDER", "brave")
    store = ChatService()
    called = {"n": 0}

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        del url, kwargs
        called["n"] += 1
        return httpx.Response(200, json={"web": {"results": []}})

    monkeypatch.setattr("ar_domain.tools.searching.httpx.get", fake_get)
    missing = dispatch_general(store, "search", {"query": "open data"})
    assert missing["code"] == "search_unconfigured"
    assert "not_live" in str(missing["text"])
    assert called["n"] == 0
    with pytest.raises(SearchUnavailableError, match="invented"):
        provider_for(ChatService(), None)


def test_live_search_skips_until_a_provider_key_is_set() -> None:
    provider = os.environ.get("AR_SEARCH_PROVIDER", "").strip().lower()
    key = os.environ.get("AR_SEARCH_API_KEY", "").strip()
    if provider not in {"brave", "tavily"} or not key:
        pytest.skip("not_live: AR_SEARCH_PROVIDER and AR_SEARCH_API_KEY are not set")
    store = ChatService()
    result = dispatch_general(store, "search", {"query": "example domain"})
    assert result["code"] != "search_unconfigured"
