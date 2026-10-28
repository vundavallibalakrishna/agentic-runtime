"""Incidents and breach clocks. Filing is recorded only after sign-off."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.access import require
from ar_domain.records.memory import bucket
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import audited, open_review, signed_for
from ar_pack_grc.values import choice, required_text, when

if TYPE_CHECKING:
    from datetime import datetime

    from ar_domain.agents.access import Actor

_REGIMES = frozenset({"cert_in", "dpdp", "gdpr"})
_HOURS = {"cert_in": 6, "dpdp": 72, "gdpr": 72}
_WORKFLOW = "GrcBreachClockWorkflow"
_QUEUE = "ar-grc"


def list_incidents(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.incidents:read")
    _sync_filings(store, actor)
    body = snake_body(query)
    status = str(body.get("status") or "")
    items = []
    for row in bucket_rows(store, "grc_incidents").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if status and str(row.get("status")) != status:
            continue
        items.append(_view(row))
    return page(items)


def create_incident(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.incidents:manage")
    body = snake_body(payload)
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "title": required_text(body.get("title"), "title"),
        "summary": str(body.get("summary") or ""),
        "status": "open",
        "detected_at": when(body.get("detected_at"), required=True),
        "clocks": [],
        "notifications": [],
        "draft_md": "",
        "legal_hold_id": _hold(store, actor, body.get("legal_hold_id")),
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_incidents")[item_id] = row
    record(store, actor, "grc.incident.opened", item_id, {"title": row["title"]})
    return _view(row)


def get_incident(store: Any, actor: Actor, incident_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.incidents:read")
    _sync_filings(store, actor)
    return _view(one(store, "grc_incidents", actor, incident_id))


def patch_incident(
    store: Any, actor: Actor, incident_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.incidents:manage")
    row = one(store, "grc_incidents", actor, incident_id)
    body = snake_body(payload)
    if "summary" in body:
        row["summary"] = str(body.get("summary") or "")
    if "status" in body:
        status = str(body.get("status") or "")
        if status not in {"open", "notified", "closed"}:
            raise ValidationFailedError("status is invalid")
        if status == "notified":
            raise ValidationFailedError("status is invalid")
        row["status"] = status
    row["updated_at"] = utcnow()
    return _view(row)


def start_clock(
    store: Any, actor: Actor, incident_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.incidents:manage")
    row = one(store, "grc_incidents", actor, incident_id)
    body = snake_body(payload)
    regime = choice(body.get("regime"), _REGIMES, "regime")
    clocks = row.get("clocks")
    if isinstance(clocks, list):
        for clock in clocks:
            if isinstance(clock, dict) and clock.get("regime") == regime:
                return present(clock)
    seconds = _HOURS[regime] * 3600
    started = utcnow()
    clock = {
        "id": new_id(),
        "regime": regime,
        "duration_seconds": seconds,
        "started_at": started,
        "deadline_at": _deadline(started, seconds),
        "workflow_id": f"grc-clock-{incident_id}-{regime}",
        "workflow": _WORKFLOW,
        "task_queue": _QUEUE,
    }
    if not isinstance(clocks, list):
        clocks = []
        row["clocks"] = clocks
    clocks.append(clock)
    _start_timer(store, str(clock["workflow_id"]), seconds)
    row["updated_at"] = utcnow()
    return present(clock)


def file_notification(
    store: Any, actor: Actor, incident_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    """Open the review. The notified audit waits until that item is signed."""
    require(actor, "grc.incidents:manage")
    row = one(store, "grc_incidents", actor, incident_id)
    body = snake_body(payload)
    regime = choice(body.get("regime"), _REGIMES, "regime")
    text = required_text(body.get("body_md"), "body_md")
    note_id = new_id()
    item = open_review(
        store,
        actor,
        slug="grc-incidents",
        subject_id=note_id,
        content=text,
        statement=f"I approve the {regime} notification.",
    )
    note = {
        "id": note_id,
        "regime": regime,
        "body_md": text,
        "status": "proposed",
        "review_item_id": item.get("id"),
        "content_hash": item.get("content_hash"),
        "filed_at": None,
    }
    notes = row.get("notifications")
    if not isinstance(notes, list):
        notes = []
        row["notifications"] = notes
    notes.append(note)
    row["updated_at"] = utcnow()
    return present(note)


def update_draft(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    """W2 tool. Drafts the notification and does not file it or start a clock."""
    require(actor, "grc.incidents:manage")
    body = snake_body(payload)
    row = one(store, "grc_incidents", actor, uuid.UUID(str(body.get("incident_id"))))
    row["draft_md"] = str(body.get("body_md") or "")
    row["updated_at"] = utcnow()
    return {"incident_id": str(row["id"]), "draft_md": row["draft_md"]}


def _sync_filings(store: Any, actor: Actor) -> None:
    for row in bucket_rows(store, "grc_incidents").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        notes = row.get("notifications")
        if not isinstance(notes, list):
            continue
        for note in notes:
            if not isinstance(note, dict) or note.get("status") == "filed":
                continue
            digest = str(note.get("content_hash") or "")
            note_id = note.get("id")
            if not isinstance(note_id, uuid.UUID) or signed_for(store, note_id, digest) is None:
                continue
            note["status"] = "filed"
            note["filed_at"] = utcnow()
            row["status"] = "notified"
            if not audited(store, "grc.incident.notified", note["id"]):
                record(
                    store,
                    actor,
                    "grc.incident.notified",
                    note["id"],
                    {"regime": note.get("regime"), "content_hash": digest},
                )


def _hold(store: Any, actor: Actor, value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        hold_id = uuid.UUID(str(value))
    except ValueError as exc:
        raise NotFoundError() from exc
    row = bucket(store, "holds").get(hold_id)
    if not isinstance(row, dict) or not same_tenant(row, actor.tenant_id):
        raise NotFoundError()
    return hold_id


def _start_timer(store: Any, workflow_id: str, seconds: int) -> None:
    pending = getattr(store, "grc_timers", None)
    if not isinstance(pending, list):
        pending = []
        store.grc_timers = pending
    payload = {
        "workflow": _WORKFLOW,
        "workflow_id": workflow_id,
        "task_queue": _QUEUE,
        "timer_seconds": seconds,
    }
    pending.append(payload)
    client = getattr(store, "temporal_client", None)
    start = getattr(client, "start_workflow", None)
    if callable(start):
        start(_WORKFLOW, {"timer_seconds": seconds}, id=workflow_id, task_queue=_QUEUE)


def _deadline(started: datetime, seconds: int) -> datetime:
    from datetime import timedelta  # noqa: PLC0415

    return started + timedelta(seconds=seconds)


def _view(row: dict[str, Any]) -> dict[str, Any]:
    return present(row)
