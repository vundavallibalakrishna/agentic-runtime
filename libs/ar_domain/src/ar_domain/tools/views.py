"""Public shapes for tool registry rows. Keys stay snake_case; the API camelises them."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def iso(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    return None if value is None else str(value)


def server_view(store: Any, row: dict[str, object]) -> dict[str, object]:
    version_id = row.get("current_version_id")
    current = None
    if isinstance(version_id, uuid.UUID):
        version = store.tool_server_versions.get(version_id)
        if isinstance(version, dict):
            current = {"id": str(version_id), "version": version.get("version")}
    owner_id = row.get("owner_user_id")
    return {
        "id": str(row["id"]),
        "slug": row["slug"],
        "name": row["name"],
        "description": row.get("description") or "",
        "kind": row["kind"],
        "scope": "platform" if row.get("tenant_id") is None else "tenant",
        "status": row["status"],
        "disabled": row.get("disabled_at") is not None,
        "last_error": row.get("last_error"),
        "owner": None if owner_id is None else {"id": str(owner_id)},
        "owner_team": None,
        "current_version": current,
        "tool_count": _count(store, row["id"]),
        "updated_at": iso(row.get("updated_at")),
    }


def version_view(store: Any, row: dict[str, object], *, tools: bool = False) -> dict[str, object]:
    body: dict[str, object] = {
        "id": str(row["id"]),
        "version": row["version"],
        "endpoint_url": row.get("endpoint_url"),
        "auth_mode": row.get("auth_mode"),
        "review_status": row.get("review_status"),
        "manifest_hash": row.get("manifest_hash"),
        "discovered_at": iso(row.get("discovered_at")),
        "reviewed_by": None if row.get("reviewed_by") is None else str(row.get("reviewed_by")),
        "reviewed_at": iso(row.get("reviewed_at")),
        "review_notes": row.get("review_notes") or "",
        "created_by": None if row.get("created_by") is None else str(row.get("created_by")),
        "created_at": iso(row.get("created_at")),
        "tool_count": _version_count(store, row["id"]),
        "discovery_error": row.get("discovery_error"),
    }
    if tools:
        body["tools"] = [
            tool_version_view(item)
            for item in store.tool_versions.values()
            if item.get("tool_server_version_id") == row["id"]
        ]
        body["manifest_diff"] = row.get("manifest_diff") or {}
    return body


def tool_version_view(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "tool_id": str(row["tool_id"]),
        "name": row.get("name"),
        "qualified_name": row.get("qualified_name"),
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "input_schema": row.get("input_schema") or {},
        "output_schema": row.get("output_schema"),
        "annotations": row.get("annotations") or {},
        "risk_class": row.get("risk_class"),
        "proposed_risk_class": row.get("proposed_risk_class"),
        "data_classification": row.get("data_classification"),
        "timeout_s": row.get("timeout_s"),
        "rate_limit_per_minute": row.get("rate_limit_per_minute"),
        "max_result_bytes": row.get("max_result_bytes"),
        "idempotent": row.get("idempotent"),
        "approval_preview": row.get("approval_preview") or {},
        "changed_since_previous": bool(row.get("changed_since_previous")),
    }


def tool_summary(
    store: Any, tool: dict[str, object], version: dict[str, object]
) -> dict[str, object]:
    server = store.tool_servers.get(tool.get("tool_server_id"))
    server_body = {"id": "", "slug": "", "name": ""}
    if isinstance(server, dict):
        server_body = {
            "id": str(server["id"]),
            "slug": str(server["slug"]),
            "name": str(server["name"]),
        }
    version_row = None
    if isinstance(server, dict):
        current = server.get("current_version_id")
        found = store.tool_server_versions.get(current)
        version_row = found if isinstance(found, dict) else None
    config = version_row.get("config") if isinstance(version_row, dict) else {}
    allow = config.get("allow_hosts") if isinstance(config, dict) else []
    calls_book = getattr(store, "tool_calls", {})
    calls = sum(
        1
        for row in calls_book.values()
        if isinstance(row, dict) and row.get("tool_id") == tool.get("id")
    )
    return {
        "tool_id": str(tool["id"]),
        "tool_version_id": str(version["id"]),
        "server_version_id": str(version.get("tool_server_version_id") or ""),
        "qualified_name": version.get("qualified_name"),
        "title": version.get("title") or "",
        "description": version.get("description") or "",
        "risk_class": version.get("risk_class"),
        "server": server_body,
        "source": _source(
            server if isinstance(server, dict) else {}, config if isinstance(config, dict) else {}
        ),
        "status": "disabled"
        if tool.get("disabled_at") is not None
        else str((server or {}).get("status") or ""),
        "disabled": tool.get("disabled_at") is not None,
        "last_error": tool.get("last_error") or (version_row or {}).get("discovery_error"),
        "calls": calls,
        "timeout_s": version.get("timeout_s"),
        "rate_limit_per_minute": version.get("rate_limit_per_minute"),
        "max_result_bytes": version.get("max_result_bytes"),
        "egress": allow if isinstance(allow, list) else [],
        "definition_version": None if version_row is None else version_row.get("version"),
    }


def call_view(row: dict[str, object]) -> dict[str, object]:
    """A stored tool call. Arguments are already redacted."""
    run_id = row.get("run_id")
    return {
        "id": str(row["id"]),
        "run_id": "" if run_id is None else str(run_id),
        "tool_id": "" if row.get("tool_id") is None else str(row.get("tool_id")),
        "qualified_name": row.get("qualified_name"),
        "status": row.get("status"),
        "risk_class": row.get("risk_class"),
        "arguments": row.get("arguments_redacted") or {},
        "result_preview": row.get("result_preview") or "",
        "error": row.get("error"),
        "latency_ms": row.get("latency_ms"),
        "created_at": iso(row.get("created_at")),
    }


def list_calls(
    store: Any,
    tenant_id: object,
    *,
    run_id: object = None,
    tool_id: object = None,
    status: str | None = None,
    q: str | None = None,
) -> list[dict[str, object]]:
    rows = []
    for row in store.tool_calls.values():
        if row.get("tenant_id") != tenant_id:
            continue
        if run_id is not None and row.get("run_id") != run_id:
            continue
        if tool_id is not None and row.get("tool_id") != tool_id:
            continue
        if status and row.get("status") != status:
            continue
        if q and q.lower() not in str(row.get("qualified_name") or "").lower():
            continue
        rows.append(call_view(row))
    return rows


def _source(server: dict[str, object], config: dict[str, object]) -> str:
    if server.get("tenant_id") is None or server.get("kind") == "builtin":
        return "builtin"
    if config.get("source") == "description":
        return "custom"
    kind = str(server.get("kind") or "")
    if kind == "remote_mcp":
        return "mcp"
    if kind == "openapi":
        return "openapi"
    return kind or "builtin"


def _count(store: Any, server_id: object) -> int:
    return sum(1 for row in store.tool_defs.values() if row.get("tool_server_id") == server_id)


def _version_count(store: Any, version_id: object) -> int:
    return sum(
        1 for row in store.tool_versions.values() if row.get("tool_server_version_id") == version_id
    )
