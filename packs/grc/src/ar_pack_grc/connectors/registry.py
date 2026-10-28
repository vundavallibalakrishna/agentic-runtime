"""Register P1 connector MCP servers and run one tool against a fixture or a test double."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

from ar_domain.agents.access import Actor
from ar_domain.records.memory import bucket
from ar_domain.tools.handlers import register_endpoint
from ar_domain.tools.seed_tools import register_builtin_server
from ar_pack_grc.access import pack_enabled, same_tenant
from ar_pack_grc.connectors import (
    aws,
    azure,
    entra,
    gcp,
    github,
    gitlab,
    google,
    jira,
    okta,
    servicenow,
)
from ar_pack_grc.connectors.kit import READ_METHODS, ConnectorKit, MemoryTransport, Tool
from ar_pack_grc.findings import sync_external_ref

if TYPE_CHECKING:
    from ar_pack_grc.connectors.kit import HttpCall

ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Server:
    slug: str
    title: str
    systems: str
    tools: tuple[Tool, ...]


SERVERS: tuple[Server, ...] = (
    Server(aws.SLUG, aws.TITLE, aws.SYSTEMS, aws.TOOLS),
    Server(azure.SLUG, azure.TITLE, azure.SYSTEMS, azure.TOOLS),
    Server(gcp.SLUG, gcp.TITLE, gcp.SYSTEMS, gcp.TOOLS),
    Server(okta.SLUG, okta.TITLE, okta.SYSTEMS, okta.TOOLS),
    Server(entra.SLUG, entra.TITLE, entra.SYSTEMS, entra.TOOLS),
    Server(google.SLUG, google.TITLE, google.SYSTEMS, google.TOOLS),
    Server(github.SLUG, github.TITLE, github.SYSTEMS, github.TOOLS),
    Server(gitlab.SLUG, gitlab.TITLE, gitlab.SYSTEMS, gitlab.TOOLS),
    Server(jira.SLUG, jira.TITLE, jira.SYSTEMS, jira.TOOLS),
    Server(servicenow.SLUG, servicenow.TITLE, servicenow.SYSTEMS, servicenow.TOOLS),
)

_PERMISSIONS = frozenset(
    {
        "grc.controls:read",
        "grc.evidence:link",
        "evidence:read",
        "evidence:capture",
        "grc.findings:manage",
        "grc.findings:read",
        "grc.tests:run",
    }
)


def register_servers() -> None:
    for spec in SERVERS:
        register_endpoint(f"builtin://{spec.slug}", _bound(spec))


def install_servers(store: Any, owner: Any) -> None:
    """Catalogue rows for every P1 server. Credentials stay on the connection, not in the tool."""
    register_servers()
    for spec in SERVERS:
        register_builtin_server(
            store,
            tenant_id=None,
            owner=owner,
            slug=spec.slug,
            name=spec.title,
            description=f"Read-only evidence from {spec.systems}.",
            endpoint=f"builtin://{spec.slug}",
            tools=[_definition(tool) for tool in spec.tools],
        )


def servers_public() -> list[dict[str, object]]:
    return [
        {
            "slug": spec.slug,
            "title": spec.title,
            "systems": spec.systems,
            "tools": [
                {"name": tool.name, "risk": tool.risk, "method": tool.method} for tool in spec.tools
            ],
        }
        for spec in SERVERS
    ]


def _bound(spec: Server) -> Any:
    def handle(
        store: Any, name: str, arguments: dict[str, object], token: str
    ) -> dict[str, object]:
        del token
        return invoke(store, spec, name, arguments)

    return handle


def invoke(store: Any, spec: Server, name: str, arguments: dict[str, object]) -> dict[str, object]:
    actor = _actor(arguments)
    if actor is None or not pack_enabled(store, actor.tenant_id):
        return _error("tool_server_unavailable", "GRC pack is not enabled")
    tool = next((item for item in spec.tools if item.name == name), None)
    if tool is None:
        return _error("unknown_tool", f"unknown tool {name}")
    transport = _transport(store, spec.slug, tool.name)
    kit = ConnectorKit(
        store,
        actor,
        spec.slug,
        transport,
        provenance={"credential": _credential_mode(store, spec.slug)},
    )
    if tool.method in READ_METHODS:
        kept = kit.collect(tool)
        _remember(store, transport.calls)
        return _ok({"items": kept, "source_system": spec.slug, "captured": len(kept)})
    body = kit.submit(tool)["body"]
    _remember(store, transport.calls)
    external = _external_id(body)
    issue = sync_external_ref(store, actor, arguments, external, spec.slug)
    return _ok({"external_ref": external, "issue": issue, "source_system": spec.slug})


def _definition(tool: Tool) -> dict[str, object]:
    return {
        "name": tool.name,
        "title": tool.title,
        "description": tool.title,
        "input_schema": {
            "type": "object",
            "properties": {
                "cursor": {"type": "string"},
                "issue_id": {"type": "string"},
                "finding_id": {"type": "string"},
                "title": {"type": "string"},
            },
        },
        "risk_class": tool.risk,
        "annotations": {"readOnlyHint": tool.method in READ_METHODS},
    }


def _transport(store: Any, slug: str, tool: str) -> MemoryTransport:
    override = getattr(store, "grc_transports", None)
    if isinstance(override, dict):
        chosen = override.get(slug)
        if isinstance(chosen, dict):
            found = chosen.get(tool)
            if isinstance(found, MemoryTransport):
                return found
        if isinstance(chosen, MemoryTransport):
            return chosen
    path = ROOT / "tests" / "fixtures" / slug / "http.json"
    document = orjson.loads(path.read_bytes())
    spec = document.get(tool) if isinstance(document, dict) else None
    pages = spec.get("pages") if isinstance(spec, dict) else None
    if not isinstance(pages, list):
        return MemoryTransport([])
    return MemoryTransport([page for page in pages if isinstance(page, dict)])


def _credential_mode(store: Any, slug: str) -> str:
    links = getattr(store, "grc_connections", None)
    if isinstance(links, dict) and slug in links:
        return "secret_ref"
    return "unconfigured"


def _remember(store: Any, calls: list[HttpCall]) -> None:
    log = getattr(store, "grc_http_log", None)
    if not isinstance(log, list):
        log = []
        store.grc_http_log = log
    log.extend(calls)


def _external_id(body: dict[str, Any]) -> str:
    for key in ("key", "sys_id", "id"):
        value = body.get(key)
        if value is not None and str(value):
            return str(value)
    return ""


def _actor(arguments: dict[str, object]) -> Actor | None:
    tenant = _uuid(arguments.get("_tenant_id"))
    user = _uuid(arguments.get("_user_id"))
    if tenant is None or user is None:
        return None
    return Actor(tenant_id=tenant, user_id=user, permissions=_PERMISSIONS, kind="user")


def _uuid(value: object) -> Any:
    import uuid  # noqa: PLC0415

    if isinstance(value, uuid.UUID):
        return value
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _ok(body: dict[str, Any]) -> dict[str, object]:
    return {"text": "ok", "structured": body, "is_error": False}


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}


def evidence_rows(store: Any, actor: Actor, source_system: str = "") -> list[dict[str, Any]]:
    found = []
    for row in bucket(store, "evidence").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if source_system and str(row.get("source_system") or "") != source_system:
            continue
        found.append(row)
    return found
