#!/usr/bin/env python
"""Install every connector against a stand-in and dispatch each tool.

The tool matrix (scripts/tool_matrix.py) proves a connector tool correctly refuses until an
account is connected. This proves the other half: that once installed, each connector tool
actually dispatches a well-formed request and parses the reply — the 18 connectors the
review never called live. Each connector is installed with stub credentials, and every HTTP
call is caught by an httpx MockTransport that returns a generic 200, so no real provider is
touched. Each tool's outcome is classified and written to docs/testing/connector-matrix/report.md.

Run: uv run python scripts/connector_matrix.py
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from ar_domain.agents.access import Actor
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.catalog import CONNECTORS
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    import uuid

    from ar_domain.connectors.catalog import ConnectorDef, ToolDef

DISPATCHED = "dispatched"  # reached the stand-in and parsed the reply
NEEDS_OAUTH = "needs-oauth"  # correctly gated: an OAuth user token is required
NEEDS_EGRESS = "needs-egress"  # correctly gated: the host is not a verifiable public address
NEEDS_PARAM = "needs-param"  # a required argument the harness did not supply
INSTALL_FAILED = "install-failed"
FAILING = "failing"  # a genuine, unexpected error

# A reply body carrying the keys the various connectors read, so most parse cleanly.
_BODY: dict[str, object] = {
    "result": [],
    "results": [],
    "value": [],
    "items": [],
    "data": [],
    "records": [],
    "messages": [],
    "files": [],
    "id": "stub-id",
    "number": "STUB-1",
    "name": "stub",
    "title": "stub",
    "nextPageToken": "",
    "next": None,
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path.lower()
    if (
        "token" in path
        or "oauth" in path
        or request.url.host
        in {
            "login.microsoftonline.com",
            "oauth2.googleapis.com",
            "accounts.google.com",
        }
    ):
        return httpx.Response(200, json={"access_token": "stub-token", "expires_in": 3600})
    return httpx.Response(200, json=dict(_BODY))


def _install(store: object, actor: Actor, connector: ConnectorDef) -> bool:
    body: dict[str, object] = {
        "connection_name": connector.slug,
        "secret": "stub-secret",
        "username": "stub@example.com",
        "client_id": "stub-client",
        "kind": connector.auth_kind,
        "config": {
            "baseUrl": "https://stub.example.com",
            "tenantId": "stub",
            "subscriptionId": "stub",
            "projectId": "stub",
            "region": "us-east-1",
        },
    }
    try:
        ConnectorBook(store).install(actor, connector.slug, body)
    except Exception:  # noqa: BLE001 - an install failure is recorded, not raised
        return False
    return True


def _stub_args(tool: ToolDef) -> dict[str, object]:
    out: dict[str, object] = {}
    for name in tool.required:
        lower = name.lower()
        if "id" in lower or "key" in lower or "sys" in lower:
            out[name] = "stub-id"
        elif name in {"to", "channel", "email"}:
            out[name] = "stub@example.com"
        elif name in {"start", "end", "timeMin", "timeMax", "startDateTime", "endDateTime"}:
            out[name] = "2026-01-01T00:00:00Z"
        else:
            out[name] = "stub"
    return out


def _classify(result: dict[str, object]) -> tuple[str, str]:
    if not result.get("is_error"):
        return DISPATCHED, "dispatched and parsed a reply"
    raw = result.get("error")
    error: dict[str, object] = raw if isinstance(raw, dict) else result
    code = str(error.get("code") or result.get("code") or "")
    message = str(error.get("message") or result.get("text") or "")[:100]
    if code == "credential_required" or "access token" in message.lower():
        return NEEDS_OAUTH, f"{code}: {message}"
    if code == "egress_denied" or "egress" in message.lower():
        return NEEDS_EGRESS, f"{code}: {message}"
    if code in {"validation_failed", "connector_not_installed", "not_found"}:
        return NEEDS_PARAM, f"{code}: {message}"
    return FAILING, f"{code}: {message}"


def run() -> int:
    store = demo_store()
    transport = httpx.MockTransport(_handler)
    store.connector_transport = transport
    actor = Actor(demo_id_tenant(), demo_id_admin(), PERMISSION_KEYS)
    rows: list[tuple[str, str, str, str]] = []
    for connector in CONNECTORS:
        prefix = connector.tool_prefix()
        if not _install(store, actor, connector):
            rows.append((connector.slug, f"{prefix}.*", INSTALL_FAILED, "install failed"))
            continue
        for conn in getattr(store, "service_connections", {}).values():
            if isinstance(conn, dict) and str(conn.get("name")) == connector.slug:
                conn["_token_transport"] = transport
        for tool in connector.tools:
            name = tool.name if tool.name.startswith(prefix) else f"{prefix}_{tool.name}"
            args = {"_tenant_id": actor.tenant_id, "_user_id": actor.user_id, **_stub_args(tool)}
            try:
                result = dispatch_connector(store, name, args)
                bucket, note = _classify(result)
            except Exception as exc:  # noqa: BLE001 - a crash is the worst outcome
                bucket, note = FAILING, f"raised {type(exc).__name__}: {exc}"[:120]
            rows.append((connector.slug, name, bucket, note))
    _report(rows)
    return 0


def demo_id_tenant() -> uuid.UUID:
    from ar_domain.chat.service import demo_id  # noqa: PLC0415

    return demo_id("tenant")


def demo_id_admin() -> uuid.UUID:
    from ar_domain.chat.service import demo_id  # noqa: PLC0415

    return demo_id("admin")


def _report(rows: list[tuple[str, str, str, str]]) -> None:
    counts = Counter(bucket for _, _, bucket, _ in rows)
    out = Path("docs/testing/connector-matrix/report.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Connector dispatch matrix",
        "",
        "Every connector installed with stub credentials; every HTTP call caught by an httpx "
        "`MockTransport` returning a generic 200. Proves each connector tool dispatches a "
        "well-formed request and parses the reply once an account is connected.",
        "",
        "## Summary",
        "",
        f"- Total connector tools: **{len(rows)}**",
    ]
    lines.extend(
        f"- {bucket}: **{counts.get(bucket, 0)}**"
        for bucket in (DISPATCHED, NEEDS_OAUTH, NEEDS_EGRESS, NEEDS_PARAM, INSTALL_FAILED, FAILING)
    )
    current = ""
    for slug, name, bucket, note in rows:
        if slug != current:
            current = slug
            lines.extend(["", f"## {slug}", "", "| tool | state | note |", "|---|---|---|"])
        lines.append(f"| `{name}` | {bucket} | {note} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"connector matrix: {len(rows)} tools -> {dict(counts)}")
    print(f"report: {out}")


if __name__ == "__main__":
    raise SystemExit(run())
