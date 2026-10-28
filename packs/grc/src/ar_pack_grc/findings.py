"""Findings and remediation issues. Closure needs a verified evidence item."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.vault import EvidenceBook
from ar_pack_grc.access import one, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SEVERITY = frozenset({"low", "medium", "high", "critical"})
_CLOSURE = "closure_evidence_required"


def list_findings(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.findings:read")
    body = snake_body(query)
    status = str(body.get("status") or "")
    severity = str(body.get("severity") or "")
    control_id = str(body.get("control_id") or "")
    items = []
    for row in bucket_rows(store, "grc_findings").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if status and str(row.get("status")) != status:
            continue
        if severity and str(row.get("severity")) != severity:
            continue
        if control_id and str(row.get("control_id")) != control_id:
            continue
        items.append(_finding_view(store, row))
    items.sort(key=lambda item: str(item.get("created_at") or ""))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_finding(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.findings:manage")
    body = snake_body(payload)
    title = str(body.get("title") or "").strip()
    severity = str(body.get("severity") or "")
    if not title or severity not in _SEVERITY:
        raise ValidationFailedError("title and severity are required")
    control_id = _optional_uuid(body.get("control_id"))
    if control_id is not None:
        one(store, "grc_controls", actor, control_id)
    evidence_id = _optional_uuid(body.get("evidence_item_id"))
    if evidence_id is not None:
        _known_evidence(store, actor, evidence_id)
    existing = _open_match(store, actor, title, control_id)
    if existing is not None:
        return _finding_view(store, existing)
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "control_id": control_id,
        "evidence_item_id": evidence_id,
        "title": title,
        "severity": severity,
        "status": "open",
        "owner_user_id": _optional_uuid(body.get("owner_user_id")),
        "due_at": body.get("due_at"),
        "closure_evidence_item_id": None,
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_findings")[item_id] = row
    record(store, actor, "grc.finding.created", item_id, {"severity": severity, "title": title})
    return _finding_view(store, row)


def get_finding(store: Any, actor: Actor, finding_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.findings:read")
    return _finding_view(store, one(store, "grc_findings", actor, finding_id))


def patch_finding(
    store: Any, actor: Actor, finding_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.findings:manage")
    row = one(store, "grc_findings", actor, finding_id)
    body = snake_body(payload)
    if "severity" in body:
        severity = str(body.get("severity") or "")
        if severity not in _SEVERITY:
            raise ValidationFailedError("severity is invalid")
        row["severity"] = severity
    if "owner_user_id" in body:
        row["owner_user_id"] = _optional_uuid(body.get("owner_user_id"))
    if "due_at" in body:
        row["due_at"] = body.get("due_at")
    row["updated_at"] = utcnow()
    return _finding_view(store, row)


def close_finding(
    store: Any, actor: Actor, finding_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.findings:manage")
    row = one(store, "grc_findings", actor, finding_id)
    if row.get("status") == "closed":
        return _finding_view(store, row)
    body = snake_body(payload)
    evidence_id = _optional_uuid(body.get("evidence_item_id"))
    if evidence_id is None or not _verified(store, actor, evidence_id):
        raise ConflictError(_CLOSURE)
    row["status"] = "closed"
    row["closure_evidence_item_id"] = evidence_id
    row["updated_at"] = utcnow()
    record(
        store,
        actor,
        "grc.finding.closed",
        finding_id,
        {"evidence_item_id": str(evidence_id)},
    )
    return _finding_view(store, row)


def list_issues(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.findings:read")
    body = snake_body(query)
    status = str(body.get("status") or "")
    due_before = str(body.get("due_before") or "")
    items = []
    for row in bucket_rows(store, "grc_issues").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if status and str(row.get("status")) != status:
            continue
        due = str(row.get("due_at") or "")
        if due_before and due and due >= due_before:
            continue
        items.append(present(row))
    return {"items": items, "next_cursor": None, "has_more": False}


def create_issue(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.findings:manage")
    body = snake_body(payload)
    title = str(body.get("title") or "").strip()
    if not title:
        raise ValidationFailedError("title is required")
    finding_id = _optional_uuid(body.get("finding_id"))
    if finding_id is not None:
        one(store, "grc_findings", actor, finding_id)
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "finding_id": finding_id,
        "title": title,
        "status": "open",
        "owner_user_id": _optional_uuid(body.get("owner_user_id")) or actor.user_id,
        "due_at": body.get("due_at"),
        "external_ref": _ref(body.get("external_ref")),
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_issues")[item_id] = row
    return present(row)


def patch_issue(
    store: Any, actor: Actor, issue_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.findings:manage")
    row = one(store, "grc_issues", actor, issue_id)
    body = snake_body(payload)
    if "status" in body:
        status = str(body.get("status") or "")
        if status not in {"open", "done"}:
            raise ValidationFailedError("status is invalid")
        row["status"] = status
    if "owner_user_id" in body:
        row["owner_user_id"] = _optional_uuid(body.get("owner_user_id"))
    if "due_at" in body:
        row["due_at"] = body.get("due_at")
    if "external_ref" in body:
        row["external_ref"] = _ref(body.get("external_ref"))
    row["updated_at"] = utcnow()
    return present(row)


def sync_external_ref(
    store: Any,
    actor: Actor,
    arguments: dict[str, object],
    external_ref: str,
    source: str,
) -> dict[str, Any]:
    """Store the external id after a W2 write has succeeded."""
    if not external_ref:
        return {}
    ref = f"{source}:{external_ref}" if ":" not in external_ref else external_ref
    issue_id = _optional_uuid(arguments.get("issue_id"))
    if issue_id is not None:
        try:
            row = one(store, "grc_issues", actor, issue_id)
        except NotFoundError:
            row = {}
        if row:
            row["external_ref"] = ref
            row["updated_at"] = utcnow()
            return present(row)
    title = str(arguments.get("title") or external_ref)
    return create_issue(
        store,
        actor,
        {
            "finding_id": arguments.get("finding_id"),
            "title": title,
            "external_ref": ref,
        },
    )


def _verified(store: Any, actor: Actor, evidence_id: uuid.UUID) -> bool:
    if not actor.has("evidence:read"):
        return False
    try:
        report = EvidenceBook(store).verify(actor, evidence_id)
    except NotFoundError:
        return False
    return bool(report.get("valid"))


def _known_evidence(store: Any, actor: Actor, evidence_id: uuid.UUID) -> None:
    row = bucket_rows(store, "evidence").get(evidence_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()


def _open_match(
    store: Any, actor: Actor, title: str, control_id: uuid.UUID | None
) -> dict[str, Any] | None:
    for row in bucket_rows(store, "grc_findings").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if row.get("status") != "open" or row.get("title") != title:
            continue
        if control_id is not None and row.get("control_id") != control_id:
            continue
        return row
    return None


def _finding_view(store: Any, row: dict[str, Any]) -> dict[str, Any]:
    item = present(row)
    item["issue_ids"] = [
        str(issue["id"])
        for issue in bucket_rows(store, "grc_issues").values()
        if issue.get("finding_id") == row.get("id")
    ]
    return item


def _ref(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None
