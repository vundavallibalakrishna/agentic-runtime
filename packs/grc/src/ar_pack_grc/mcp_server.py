"""Tools for the `grc` MCP server. Read tools are R0/R1. Writes are W1 or W2."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import ArError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.records.memory import bucket
from ar_domain.tools.handlers import register_endpoint
from ar_pack_grc.access import pack_enabled, present, same_tenant
from ar_pack_grc.evidence_links import create_link
from ar_pack_grc.findings import create_finding
from ar_pack_grc.frameworks import get_control, list_controls
from ar_pack_grc.mappings import suggest
from ar_pack_grc.tests import record_result

if TYPE_CHECKING:
    from typing import Any

READ_TOOLS = (
    "controls.search",
    "controls.get",
    "mapping.suggest",
    "questionnaire.search_answers",
    "vendors.get",
    "policies.search",
    "obligations.search",
)
WRITE_TOOLS = (
    "evidence.attach",
    "tests.record_result",
    "findings.create",
)
# `tools.name` cannot contain a dot (`ck_tools_name`). Qualified names keep the spec form.
_STORED = {name.replace(".", "_"): name for name in (*READ_TOOLS, *WRITE_TOOLS)}


def register() -> None:
    register_endpoint("builtin://grc", handle)


def tool_definitions() -> list[dict[str, object]]:
    specs = (
        ("controls_search", "Search controls", "R0", {"q": _string(), "framework_key": _string()}),
        ("controls_get", "Get one control", "R0", {"control_id": _string()}),
        (
            "mapping_suggest",
            "Suggest control mappings",
            "R1",
            {"from_framework_id": _string(), "to_framework_id": _string()},
        ),
        ("questionnaire_search_answers", "Search approved answers", "R0", {"q": _string()}),
        ("vendors_get", "Get a vendor", "R0", {"vendor_id": _string()}),
        ("policies_search", "Search published policies", "R0", {"q": _string()}),
        (
            "obligations_search",
            "Search obligations",
            "R0",
            {"q": _string(), "regulator": _string()},
        ),
        (
            "evidence_attach",
            "Attach evidence to a control",
            "W1",
            {
                "control_id": _string(),
                "evidence_item_id": _string(),
                "freshness_days": {"type": "integer"},
            },
        ),
        (
            "tests_record_result",
            "Record a control test result",
            "W1",
            {
                "test_id": _string(),
                "outcome": _string(),
                "summary": _string(),
                "evidence_item_ids": {"type": "array"},
            },
        ),
        (
            "findings_create",
            "Open a finding",
            "W2",
            {
                "title": _string(),
                "severity": _string(),
                "control_id": _string(),
                "evidence_item_id": _string(),
            },
        ),
    )
    tools: list[dict[str, object]] = []
    for name, title, risk, properties in specs:
        schema: dict[str, object] = {"type": "object", "properties": properties}
        tools.append(
            {
                "name": name,
                "title": title,
                "description": title,
                "input_schema": schema,
                "risk_class": risk,
                "annotations": {},
            }
        )
    return tools


def handle(store: Any, name: str, arguments: dict[str, object], token: str) -> dict[str, object]:
    del token
    tenant_id = _uuid(arguments.get("_tenant_id"))
    user_id = _uuid(arguments.get("_user_id"))
    if tenant_id is None or user_id is None or not pack_enabled(store, tenant_id):
        return _error("tool_server_unavailable", "GRC pack is not enabled")
    actor = Actor(
        tenant_id=tenant_id, user_id=user_id, permissions=_tool_permissions(), kind="user"
    )
    try:
        return _dispatch(store, actor, _STORED.get(name, name), arguments)
    except ArError as exc:
        code = "not_found" if exc.status == 404 else "validation_failed"
        return _error(code, exc.detail)


def _dispatch(  # noqa: PLR0911
    store: Any, actor: Actor, name: str, arguments: dict[str, object]
) -> dict[str, object]:
    if name == "controls.search":
        return _ok(list_controls(store, actor, _public_args(arguments)))
    if name == "controls.get":
        control_id = _uuid(arguments.get("control_id"))
        if control_id is None:
            return _error("validation_failed", "control_id is required")
        return _ok(get_control(store, actor, control_id))
    if name == "mapping.suggest":
        return _ok(suggest(store, actor, _public_args(arguments), agent=True))
    if name == "questionnaire.search_answers":
        return _ok({"items": _answers(store, actor, str(arguments.get("q") or ""))})
    if name == "vendors.get":
        return _vendor(store, actor, arguments.get("vendor_id"))
    if name == "policies.search":
        return _ok({"items": _policies(store, actor, str(arguments.get("q") or ""))})
    if name == "obligations.search":
        return _ok(
            {
                "items": _obligations(
                    store,
                    actor,
                    str(arguments.get("q") or ""),
                    str(arguments.get("regulator") or ""),
                )
            }
        )
    if name == "evidence.attach":
        return _ok(create_link(store, actor, _public_args(arguments)))
    if name == "tests.record_result":
        return _ok(record_result(store, actor, _public_args(arguments)))
    if name == "findings.create":
        return _ok(create_finding(store, actor, _public_args(arguments)))
    return _error("unknown_tool", f"unknown tool {name}")


def put_vendor(store: Any, actor: Actor, name: str, *, tier: str = "medium") -> dict[str, Any]:
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "name": name,
        "tier": tier,
        "owner_user_id": actor.user_id,
        "created_at": utcnow(),
    }
    bucket(store, "grc_vendors")[item_id] = row
    return row


def put_policy(
    store: Any, actor: Actor, key: str, title: str, *, published: bool
) -> dict[str, Any]:
    policy_id = new_id()
    bucket(store, "grc_policies")[policy_id] = {
        "id": policy_id,
        "tenant_id": actor.tenant_id,
        "key": key,
        "title": title,
        "owner_user_id": actor.user_id,
    }
    version_id = new_id()
    bucket(store, "grc_policy_versions")[version_id] = {
        "id": version_id,
        "tenant_id": actor.tenant_id,
        "policy_id": policy_id,
        "version": 1,
        "body_md": title,
        "content_hash": key,
        "state": "published" if published else "draft",
    }
    return bucket(store, "grc_policies")[policy_id]


def put_answer(
    store: Any, actor: Actor, question: str, *, status: str, expires_at: object = None
) -> dict[str, Any]:
    item_id = new_id()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "question": question,
        "answer_md": question,
        "status": status,
        "expires_at": expires_at,
    }
    bucket(store, "grc_answers")[item_id] = row
    return row


def _answers(store: Any, actor: Actor, query: str) -> list[dict[str, Any]]:
    now = utcnow()
    found = []
    for row in bucket(store, "grc_answers").values():
        if not same_tenant(row, actor.tenant_id) or row.get("status") != "approved":
            continue
        expires = row.get("expires_at")
        if isinstance(expires, type(now)) and expires <= now:
            continue
        if query and query.lower() not in str(row.get("question")).lower():
            continue
        found.append(present(row))
    return found


def _vendor(store: Any, actor: Actor, vendor_id: object) -> dict[str, object]:
    item_id = _uuid(vendor_id)
    row = bucket(store, "grc_vendors").get(item_id) if item_id else None
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        return _error("not_found", "vendor was not found")
    assessments = [
        present(item)
        for item in bucket(store, "grc_vendor_assessments").values()
        if same_tenant(item, actor.tenant_id) and item.get("vendor_id") == row["id"]
    ]
    body = present(row)
    body["assessments"] = assessments
    return _ok(body)


def _policies(store: Any, actor: Actor, query: str) -> list[dict[str, Any]]:
    published = {
        row["policy_id"]
        for row in bucket(store, "grc_policy_versions").values()
        if same_tenant(row, actor.tenant_id) and row.get("state") == "published"
    }
    found = []
    for row in bucket(store, "grc_policies").values():
        if not same_tenant(row, actor.tenant_id) or row["id"] not in published:
            continue
        if query and query.lower() not in str(row.get("title")).lower():
            continue
        found.append(present(row))
    return found


def _obligations(store: Any, actor: Actor, query: str, regulator: str) -> list[dict[str, Any]]:
    found = []
    for row in bucket(store, "grc_obligations").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if regulator and str(row.get("regulator")) != regulator:
            continue
        text = f"{row.get('citation')} {row.get('statement')}".lower()
        if query and query.lower() not in text:
            continue
        found.append(present(row))
    return found


def _public_args(arguments: dict[str, object]) -> dict[str, Any]:
    return {key: value for key, value in arguments.items() if not str(key).startswith("_")}


def _read_permissions() -> frozenset[str]:
    return frozenset(
        {
            "grc.controls:read",
            "grc.frameworks:read",
            "grc.questionnaires:read",
            "grc.vendors:read",
            "grc.policies:read",
            "grc.obligations:read",
            "grc.entities:read",
        }
    )


def _tool_permissions() -> frozenset[str]:
    return _read_permissions() | frozenset(
        {
            "grc.controls:manage",
            "grc.evidence:link",
            "evidence:read",
            "evidence:capture",
            "grc.tests:read",
            "grc.tests:run",
            "grc.findings:read",
            "grc.findings:manage",
        }
    )


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _string() -> dict[str, str]:
    return {"type": "string"}


def _ok(body: dict[str, Any]) -> dict[str, object]:
    return {"text": "ok", "structured": body, "is_error": False}


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
