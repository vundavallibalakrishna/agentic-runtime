"""Record how far a long job got, and mark it interrupted after a restart."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    from typing import Any

_TERMINAL = {"completed", "interrupted", "failed"}
_INTERRUPTED = "The API restarted while this job was running."


def note_job(
    store: Any,
    arguments: dict[str, object],
    *,
    kind: str,
    tool_name: str,
    label: str,
    completed: int,
    total: int,
    status: str,
    detail: str = "",
) -> dict[str, object] | None:
    """Insert or update the job for this run and tool."""
    tenant_id = _uuid(arguments.get("_tenant_id"))
    if tenant_id is None or status not in {"running", *_TERMINAL}:
        return None
    run_id = _uuid(arguments.get("_run_id"))
    conversation_id = _uuid(arguments.get("_conversation_id"))
    book = getattr(store, "job_progress", None)
    if not isinstance(book, dict):
        book = {}
        store.job_progress = book
    current = _find(book, run_id, tool_name, kind)
    previous = str(current.get("status") or "") if current else ""
    now = utcnow()
    if current is None:
        job_id = new_id()
        current = {
            "id": job_id,
            "tenant_id": tenant_id,
            "run_id": run_id,
            "conversation_id": conversation_id,
            "tool_name": tool_name,
            "kind": kind,
            "label": label[:200],
            "completed": completed,
            "total": total,
            "status": status,
            "detail": detail[:500],
            "created_at": now,
            "updated_at": now,
        }
        book[job_id] = current
    else:
        current["label"] = label[:200]
        current["completed"] = completed
        current["total"] = total
        current["status"] = status
        current["detail"] = detail[:500]
        current["updated_at"] = now
        if conversation_id is not None:
            current["conversation_id"] = conversation_id
    if status in _TERMINAL and previous != status:
        remember(
            store,
            tenant_id=tenant_id,
            actor_id=str(arguments.get("_user_id") or "system"),
            action="job.progressed",
            target_type="run",
            target_id=run_id or current["id"],
            detail={
                "job_id": str(current["id"]),
                "kind": kind,
                "status": status,
                "completed": completed,
                "total": total,
            },
        )
    _stamp_run(store, run_id, current)
    return current


def mark_jobs_interrupted(store: Any) -> list[str]:
    """A restart stops a job that was still marked running."""
    book = getattr(store, "job_progress", None)
    if not isinstance(book, dict):
        return []
    changed: list[str] = []
    for row in list(book.values()):
        if not isinstance(row, dict) or str(row.get("status")) != "running":
            continue
        row["status"] = "interrupted"
        row["detail"] = _INTERRUPTED
        row["updated_at"] = utcnow()
        changed.append(str(row.get("id")))
        remember(
            store,
            tenant_id=row.get("tenant_id"),
            actor_id="system",
            action="job.progressed",
            target_type="run",
            target_id=row.get("run_id") or row.get("id"),
            detail={
                "job_id": str(row.get("id")),
                "kind": str(row.get("kind") or ""),
                "status": "interrupted",
                "completed": row.get("completed") or 0,
                "total": row.get("total") or 0,
            },
        )
    return changed


def jobs_for(store: Any, conversation_id: uuid.UUID) -> list[dict[str, object]]:
    book = getattr(store, "job_progress", None)
    if not isinstance(book, dict):
        return []
    rows = [
        _public(row)
        for row in book.values()
        if isinstance(row, dict) and row.get("conversation_id") == conversation_id
    ]
    rows.sort(key=lambda item: str(item.get("updated_at")))
    return rows


def progress_view(row: dict[str, object]) -> dict[str, object]:
    return {
        "completed": _count(row.get("completed")),
        "total": _count(row.get("total")),
        "label": str(row.get("label") or ""),
        "status": str(row.get("status") or ""),
        "detail": str(row.get("detail") or ""),
    }


def attach_progress(result: dict[str, object], row: dict[str, object] | None) -> dict[str, object]:
    if row is None:
        return result
    structured = result.get("structured")
    if not isinstance(structured, dict):
        return result
    presentation = structured.get("presentation")
    if not isinstance(presentation, dict):
        presentation = {}
        structured["presentation"] = presentation
    presentation["progress"] = progress_view(row)
    return result


def _find(
    book: dict[object, object], run_id: uuid.UUID | None, tool_name: str, kind: str
) -> dict[str, object] | None:
    for row in book.values():
        if not isinstance(row, dict):
            continue
        same_run = row.get("run_id") == run_id
        same_tool = row.get("tool_name") == tool_name and row.get("kind") == kind
        if same_run and same_tool:
            return row
    return None


def _stamp_run(store: Any, run_id: uuid.UUID | None, row: dict[str, object]) -> None:
    runs = getattr(store, "runs", None)
    if not isinstance(run_id, uuid.UUID) or not isinstance(runs, dict):
        return
    run = runs.get(run_id)
    if not isinstance(run, dict):
        return
    checkpoint = run.get("checkpoint")
    base = dict(checkpoint) if isinstance(checkpoint, dict) else {}
    base["job"] = _public(row)
    run["checkpoint"] = base


def _public(row: dict[str, object]) -> dict[str, object]:
    updated = row.get("updated_at")
    return {
        "id": str(row.get("id")),
        "run_id": None if row.get("run_id") is None else str(row.get("run_id")),
        "conversation_id": (
            None if row.get("conversation_id") is None else str(row.get("conversation_id"))
        ),
        "tool_name": str(row.get("tool_name") or ""),
        "kind": str(row.get("kind") or ""),
        "label": str(row.get("label") or ""),
        "completed": _count(row.get("completed")),
        "total": _count(row.get("total")),
        "status": str(row.get("status") or ""),
        "detail": str(row.get("detail") or ""),
        "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else str(updated or ""),
    }


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None
