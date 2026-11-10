"""Records tools. Registered only when the pack is mounted."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.tools.seed_tools import register_builtin_server

if TYPE_CHECKING:
    from typing import Any


def tool_specs() -> list[dict[str, object]]:
    body: dict[str, object] = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Text to seal when the item is text rather than a stored file. "
                "Give this or bytes_file_id.",
            },
            "bytes_file_id": {
                "type": "string",
                "description": "The id of a file already in this conversation to seal. "
                "Give this or text.",
            },
            "media_type": {
                "type": "string",
                "description": "The MIME type, for example text/plain or application/pdf.",
            },
            "source_system": {
                "type": "string",
                "description": "A short name for where the item came from.",
            },
            "collection_method": {
                "type": "string",
                "description": "How the item was obtained, for example download or screenshot.",
            },
            "evidence_item_id": {
                "type": "string",
                "description": "The id of an existing item: required by get and verify.",
            },
        },
    }
    return [
        _tool(
            "capture",
            "Capture a record",
            "Seal text or a file's bytes and return its id and manifest hash.",
            body,
            "R1",
        ),
        _tool(
            "get",
            "Get a record",
            "Read the metadata of one sealed item by id. Does not return the bytes.",
            body,
            "R0",
        ),
        _tool(
            "verify",
            "Verify a record",
            "Recompute a sealed item's manifest hash and report whether it still matches.",
            body,
            "R0",
        ),
    ]


def register_tools(store: Any, *, tenant_id: uuid.UUID | None, owner: uuid.UUID | None) -> None:
    register_builtin_server(
        store,
        tenant_id=tenant_id,
        owner=owner,
        slug="records",
        name="Records",
        description="Seal, read and verify records.",
        endpoint="builtin://records",
        tools=tool_specs(),
    )


def dispatch_records(
    store: Any, name: str, arguments: dict[str, object], token: str
) -> dict[str, object]:
    del token
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from records_pack.vault import EvidenceBook  # noqa: PLC0415

    try:
        tenant_id = uuid.UUID(str(arguments.get("_tenant_id")))
        user_id = uuid.UUID(str(arguments.get("_user_id")))
    except ValueError:
        return _error("validation_failed", "records tools need a tenant")
    actor = Actor(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=frozenset(PACK_PERMISSIONS),
    )
    book = EvidenceBook(store)
    if name == "capture":
        text = str(arguments.get("text") or "")
        file_id = arguments.get("bytes_file_id") or arguments.get("file_id")
        data = text.encode()
        if file_id:
            blob = store.blobs.get(uuid.UUID(str(file_id)))
            data = blob if isinstance(blob, bytes) else data
        if str(arguments.get("collection_method")) == "browser_screenshot" and not file_id:
            return _error("validation_failed", "browser screenshots are captured from a file")
        captured = book.capture(actor, arguments, data)
        return {
            "text": str(captured.get("content_sha256")),
            "structured": {
                "evidence_item_id": str(captured.get("id")),
                "content_sha256": captured.get("content_sha256"),
            },
            "is_error": False,
        }
    if name == "get":
        item = book.get(actor, uuid.UUID(str(arguments.get("evidence_item_id"))))
        return {"text": str(item.get("content_sha256")), "structured": item, "is_error": False}
    if name == "verify":
        report = book.verify(actor, uuid.UUID(str(arguments.get("evidence_item_id"))))
        return {"text": str(report.get("valid")), "structured": report, "is_error": False}
    return _error("unknown_tool", f"unknown tool {name}")


PACK_PERMISSIONS = (
    "evidence:read",
    "evidence:capture",
    "evidence:export",
    "holds:manage",
    "retention:manage",
    "ai_governance:read",
    "ai_governance:manage",
    "guests:invite",
    "guests:manage",
    "binders:export",
    "run_records:read",
    "run_records:replay",
)


def _tool(
    name: str, title: str, description: str, schema: dict[str, object], risk: str
) -> dict[str, object]:
    return {
        "name": name,
        "title": title,
        "description": description,
        "input_schema": schema,
        "risk_class": risk,
        "annotations": {},
    }


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
