"""Tools registered only while the pack is enabled."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_domain.tools.seed_tools import register_builtin_server

PACK_PERMISSIONS = (
    "grc.catalogues:manage",
    "grc.evidence:link",
    "grc.risks:manage",
    "grc.findings:manage",
)


def register_tools(store: Any, *, tenant_id: uuid.UUID | None, owner: uuid.UUID | None) -> None:
    register_builtin_server(
        store,
        tenant_id=tenant_id,
        owner=owner,
        slug="grc",
        name="GRC",
        description="Imported catalogues, evidence links, risks and findings.",
        endpoint="builtin://grc",
        tools=[
            _tool(
                "import_catalogue",
                "Import a catalogue",
                "Import a CSV catalogue. Columns are key, title and statement. "
                "The statement is the customer's own words.",
                "W1",
            ),
            _tool(
                "judge_catalogue",
                "Judge a catalogue",
                "Judge each imported statement against passages using the document judge.",
                "R0",
            ),
            _tool(
                "link_evidence",
                "Link evidence",
                "Link a catalogue item to a sealed record id from the records pack.",
                "W1",
            ),
            _tool("add_risk", "Add a risk", "Record a risk with a score from 0 to 100.", "W1"),
            _tool("add_finding", "Add a finding", "Record a finding.", "W1"),
        ],
    )


def dispatch_grc(  # noqa: PLR0911
    store: Any, name: str, arguments: dict[str, object], token: str
) -> dict[str, object]:
    del token
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from grc_pack.book import CatalogueBook  # noqa: PLC0415

    try:
        tenant_id = uuid.UUID(str(arguments.get("_tenant_id")))
        user_id = uuid.UUID(str(arguments.get("_user_id")))
    except ValueError:
        return _error("validation_failed", "grc tools need a tenant")
    raw = arguments.get("_permissions")
    permissions = frozenset(str(item) for item in raw) if isinstance(raw, list) else frozenset()
    actor = Actor(tenant_id, user_id, permissions)
    book = CatalogueBook(store)
    try:
        if name == "import_catalogue":
            saved = book.import_csv(
                actor, str(arguments.get("name") or ""), str(arguments.get("csv") or "")
            )
            return {"text": str(saved["id"]), "structured": saved, "is_error": False}
        if name == "judge_catalogue":
            passages = arguments.get("passages")
            rows = book.judge(
                actor,
                uuid.UUID(str(arguments.get("catalogue_id"))),
                [row for row in passages if isinstance(row, dict)]
                if isinstance(passages, list)
                else [],
            )
            return {"text": str(len(rows)), "structured": {"judgements": rows}, "is_error": False}
        if name == "link_evidence":
            linked = book.link_evidence(
                actor,
                uuid.UUID(str(arguments.get("item_id"))),
                uuid.UUID(str(arguments.get("evidence_id"))),
                str(arguments.get("note") or ""),
            )
            return {"text": str(linked["id"]), "structured": linked, "is_error": False}
        if name == "add_risk":
            raw_score = arguments.get("score") or 0
            saved = book.add_risk(actor, str(arguments.get("title") or ""), int(str(raw_score)))
            return {"text": str(saved["id"]), "structured": saved, "is_error": False}
        if name == "add_finding":
            saved = book.add_finding(
                actor,
                str(arguments.get("title") or ""),
                str(arguments.get("item_key") or ""),
            )
            return {"text": str(saved["id"]), "structured": saved, "is_error": False}
    except (ValueError, TypeError) as exc:
        return _error("validation_failed", str(exc))
    except Exception as exc:  # noqa: BLE001 - pack tools return a tool error
        code = getattr(exc, "code", None)
        detail = getattr(exc, "detail", None) or str(exc)
        return _error(str(getattr(code, "value", code) or "validation_failed"), str(detail))
    return _error("unknown_tool", f"unknown tool {name}")


_SCHEMAS: dict[str, dict[str, object]] = {
    "import_catalogue": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "csv": {"type": "string"}},
        "required": ["name", "csv"],
        "additionalProperties": False,
    },
    "judge_catalogue": {
        "type": "object",
        "properties": {
            "catalogue_id": {"type": "string"},
            "passages": {"type": "array"},
        },
        "required": ["catalogue_id"],
        "additionalProperties": False,
    },
    "link_evidence": {
        "type": "object",
        "properties": {
            "item_id": {"type": "string"},
            "evidence_id": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["item_id", "evidence_id"],
        "additionalProperties": False,
    },
    "add_risk": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "score": {"type": "integer"},
            "status": {"type": "string"},
        },
        "required": ["title", "score"],
        "additionalProperties": False,
    },
    "add_finding": {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "item_key": {"type": "string"},
            "status": {"type": "string"},
        },
        "required": ["title"],
        "additionalProperties": False,
    },
}


def _tool(name: str, title: str, description: str, risk: str) -> dict[str, object]:
    return {
        "name": name,
        "title": title,
        "description": description,
        "input_schema": _SCHEMAS[name],
        "risk_class": risk,
        "annotations": {},
    }


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
