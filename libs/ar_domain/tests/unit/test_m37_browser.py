"""Controlled browser: local fixture, approval, and session isolation.

Spec: docs/03-specs/12-sandbox-manager.md. Chromium is optional (OQ-87).
"""

from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import httpx

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.sandboxes.browser import chromium_canary, navigation_class
from ar_domain.sandboxes.runtime import run_tool
from ar_domain.sandboxes.service import SandboxBook
from ar_domain.tools.logic import call_args_hash
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store

_PAGE = """<!DOCTYPE html>
<html><head><title>Fixture desk</title></head>
<body>
<h1>Fixture desk</h1>
<p>Ticket queue for the local site.</p>
<a href="/next">Open the next page</a>
<form action="/submit" method="post">
<input name="note" type="text">
<button type="submit">Send</button>
</form>
</body></html>
"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        cookie = self.headers.get("Cookie") or ""
        if self.path.startswith("/next"):
            shown = cookie or "none"
            body = (
                "<html><head><title>Next</title></head><body>"
                f"<h1>Second page</h1><p>cookie {shown}</p></body></html>"
            )
        else:
            body = _PAGE
        self._send(body, cookie=None)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(length).decode("utf-8", errors="replace")
        note = parse_qs(raw).get("note", [""])[0]
        body = (
            "<html><head><title>Saved</title></head><body>"
            f"<h1>Saved note</h1><p>{note}</p></body></html>"
        )
        self._send(body, cookie="desk=armed; Path=/")

    def _send(self, body: str, *, cookie: str | None) -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        del fmt, args


def _site() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


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


def test_fixture_case_reads_types_and_submits() -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    server, base = _site()
    conversation = uuid.uuid4()
    run = uuid.uuid4()
    store.events[run] = []
    store.runs[run] = {
        "id": run,
        "conversation_id": conversation,
        "tenant_id": tenant,
    }
    try:
        opened = _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            url=f"{base}/",
        )
        assert opened["is_error"] is False
        assert "Fixture desk" in str(opened["text"])
        assert "[ref=e" in str(opened["text"])
        assert opened["structured"]["untrusted"] is True
        assert opened["structured"]["engine"] == "fixture"
        snapshot = _call(
            store,
            "snapshot",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
        )
        assert "Ticket queue" in str(snapshot["text"])
        clicked = _call(
            store,
            "click",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            ref="e3",
        )
        assert "Second page" in str(clicked["text"])
        assert "cookie none" in str(clicked["text"])
        _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            url=f"{base}/",
        )
        typed = _call(
            store,
            "type",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            ref="e4",
            text="hello",
        )
        assert typed["is_error"] is False
        submitted = _call(
            store,
            "submit_form",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            ref="e5",
            _browser_cleared=True,
        )
        assert "Saved note" in str(submitted["text"])
        assert "hello" in str(submitted["text"])
        again = _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            url=f"{base}/next",
        )
        assert "desk=armed" in str(again["text"])
        pressed = _call(
            store,
            "press",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            key="Enter",
        )
        assert pressed["is_error"] is False
        scrolled = _call(
            store,
            "scroll",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            direction="down",
            amount=1,
        )
        assert scrolled["structured"]["scroll"] == 1
        shot = _call(
            store,
            "screenshot",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=run,
            _tool_call_id=str(uuid.uuid4()),
        )
        assert shot["is_error"] is False
        file_id = uuid.UUID(str(shot["structured"]["file_id"]))
        assert store.blobs[file_id].startswith(b"\x89PNG")
        assert any(event["type"] == "browser.screenshot" for event in store.events[run])
        sandbox = next(
            row for row in store.sandboxes.values() if row.get("conversation_id") == conversation
        )
        view = SandboxBook(store)._sandbox_out(sandbox)
        assert "browser" not in view
        assert "browser_sessions" not in view
        assert "desk=armed" not in str(view)
        probe = chromium_canary(f"{base}/")
        assert probe["status"] in {"live", "not_live"}
        if probe["status"] == "live":
            assert "Fixture desk" in probe["excerpt"]
        else:
            assert probe["reason"]
    finally:
        server.shutdown()


def test_sessions_do_not_share_cookies() -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    server, base = _site()
    conversation = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    other_tenant = uuid.uuid4()
    other_conversation = uuid.uuid4()
    try:
        _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=first,
            url=f"{base}/",
        )
        _call(
            store,
            "type",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=first,
            ref="e4",
            text="hello",
        )
        saved = _call(
            store,
            "submit_form",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=first,
            ref="e5",
            _browser_cleared=True,
        )
        assert "Saved note" in str(saved["text"])
        other_run = _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=conversation,
            run=second,
            url=f"{base}/next",
        )
        assert "cookie none" in str(other_run["text"])
        assert "desk=armed" not in str(other_run["text"])
        other_conversation_page = _call(
            store,
            "navigate",
            tenant=tenant,
            user=user,
            agent=agent,
            conversation=other_conversation,
            run=first,
            url=f"{base}/next",
        )
        assert "cookie none" in str(other_conversation_page["text"])
        foreign = _call(
            store,
            "navigate",
            tenant=other_tenant,
            user=user,
            agent=agent,
            conversation=uuid.uuid4(),
            run=uuid.uuid4(),
            url=f"{base}/next",
        )
        assert foreign["is_error"] is False
        assert "desk=armed" not in str(foreign["text"])
        jars = []
        for row in store.sandboxes.values():
            sessions = row.get("browser_sessions")
            if not isinstance(sessions, dict):
                continue
            for context in sessions.values():
                if isinstance(context, dict):
                    jars.append(context.get("cookies"))
                    assert str(context.get("tenant_id")) == str(row.get("tenant_id"))
        assert len(jars) >= 2
        assert jars[0] is not jars[1]
    finally:
        server.shutdown()


def test_off_list_navigation_waits_and_private_hosts_stay_denied() -> None:
    store = demo_store()
    tenant, user, agent = _arm(store)
    version_id = next(
        row["published_version_id"] for row in store.agents.values() if row.get("id") == agent
    )
    tool_id = next(
        row["id"]
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "browser.navigate"
    )
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        html = (
            "<html><head><title>Off list</title></head><body><h1>Off list desk</h1></body></html>"
        )
        return httpx.Response(200, text=html)

    store.browser_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    store.browser_resolve = lambda host: ["93.184.216.34"]  # type: ignore[attr-defined]
    arguments = {"url": "https://off-list.example/desk"}
    digest = call_args_hash(str(tool_id), arguments)
    held = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": user,
            "agent_id": agent,
            "agent_version_id": version_id,
            "tool_version_id": tool_id,
            "arguments": arguments,
            "args_hash": digest,
            "run_id": uuid.uuid4(),
        }
    )
    assert held["status"] == "awaiting_approval"
    assert held["risk_class"] == "W2"
    assert seen == []
    approval_id = uuid.UUID(str(held["approval_id"]))
    store.approvals[approval_id]["status"] = "approved"
    opened = ToolPipeline(store).execute(
        {
            "tenant_id": tenant,
            "user_id": user,
            "agent_id": agent,
            "agent_version_id": version_id,
            "tool_version_id": tool_id,
            "arguments": arguments,
            "args_hash": digest,
            "approval_id": approval_id,
            "run_id": uuid.uuid4(),
        }
    )
    assert opened["status"] == "succeeded"
    assert "Off list desk" in str(opened["result_preview"])
    assert seen == ["https://off-list.example/desk"]
    blocked = run_tool(
        store,
        "navigate",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "_agent_id": agent,
            "_agent_version_id": version_id,
            "_conversation_id": uuid.uuid4(),
            "_browser_cleared": True,
            "url": "http://169.254.169.254/latest/meta-data",
        },
    )
    assert blocked["code"] == "egress_denied"
    assert (
        navigation_class(
            store,
            {"tenant_id": tenant, "agent_id": agent, "agent_version_id": version_id},
            "http://169.254.169.254/",
        )
        == "deny"
    )
    assert (
        navigation_class(
            store,
            {"tenant_id": tenant, "agent_id": agent, "agent_version_id": version_id},
            "https://off-list.example/desk",
        )
        == "approve"
    )
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
    assert seen == ["https://off-list.example/desk"]
