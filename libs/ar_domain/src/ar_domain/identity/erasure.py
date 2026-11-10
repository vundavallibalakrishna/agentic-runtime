"""Erase one person's rows, skipping any row an active hold still covers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_domain.records.access import audit, require
from ar_domain.records.locks import is_held
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor


def erase_user(store: Any, actor: Actor, user_id: uuid.UUID) -> dict[str, object]:
    require(actor, "users:manage")
    held: list[str] = []
    removed = 0
    for record_class, source in (
        ("conversation", store.conversations),
        ("file", store.files),
        ("memory_fact", store.memory_facts),
    ):
        for record_id, row in list(source.items()):
            if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
                continue
            owner = row.get("user_id") or row.get("owner_user_id") or row.get("uploaded_by")
            if owner != user_id:
                continue
            if is_held(store, record_class, record_id):
                held.append(str(record_id))
                continue
            source.pop(record_id, None)
            if record_class == "conversation":
                _drop_children(store, record_id)
            if record_class == "file":
                store.blobs.pop(record_id, None)
            removed += 1
    _drop_user_edges(store, actor.tenant_id, user_id, held)
    detail = {"user_id": str(user_id), "removed": removed, "held_record_ids": held}
    audit(store, actor, "erasure.completed", "user", user_id, detail)
    return detail


def _drop_children(store: Any, conversation_id: object) -> None:
    for message_id, message in list(store.messages.items()):
        if isinstance(message, dict) and message.get("conversation_id") == conversation_id:
            store.messages.pop(message_id, None)
    for run_id, run in list(store.runs.items()):
        if isinstance(run, dict) and run.get("conversation_id") == conversation_id:
            store.runs.pop(run_id, None)


def _drop_user_edges(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, held: list[str]) -> None:
    grants = getattr(store, "credential_grants", {})
    if isinstance(grants, dict):
        for grant_id, row in list(grants.items()):
            if isinstance(row, dict) and row.get("user_id") == user_id:
                grants.pop(grant_id, None)
    identities = getattr(store, "channel_identities", {})
    if isinstance(identities, dict):
        for identity_id, row in list(identities.items()):
            if (
                isinstance(row, dict)
                and row.get("user_id") == user_id
                and row.get("tenant_id") == tenant_id
            ):
                identities.pop(identity_id, None)
    points = bucket(store, "retrieval_points")
    for point_id, row in list(points.items()):
        if isinstance(row, dict) and row.get("user_id") == user_id:
            if row.get("held"):
                held.append(str(point_id))
                continue
            points.pop(point_id, None)
