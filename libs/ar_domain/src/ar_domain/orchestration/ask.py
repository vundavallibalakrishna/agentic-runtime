"""A run pauses for a person, then resumes with the answer."""

from __future__ import annotations

import uuid
from typing import Any  # noqa: TC003

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow

_QUESTION = "question"
_APPROVAL = "approval"


def ask_person(
    store: Any,
    run: dict[str, object],
    assistant: dict[str, object],
    arguments: dict[str, object],
    call_id: str,
) -> dict[str, object] | None:
    """Pause the run. Return an error preview when the request is not allowed."""
    question = str(arguments.get("question") or "").strip()
    if not question:
        return _bad("A question is required.")
    kind = str(arguments.get("kind") or _QUESTION)
    if kind not in {_QUESTION, _APPROVAL}:
        return _bad("kind must be question or approval.")
    options = _options(arguments.get("options"))
    requested = _uuid(run.get("user_id"))
    assignee = _uuid(arguments.get("assignee_user_id")) or requested
    if requested is None or assignee is None:
        return _bad("This run has no person to ask.")
    if kind == _APPROVAL and assignee == requested:
        _audit(store, run, "human_question.denied", "failure")
        return _bad("You cannot ask the requester to approve their own request.")
    row_id = new_id()
    now = utcnow()
    questions = _bucket(store)
    questions[row_id] = {
        "id": row_id,
        "tenant_id": run.get("tenant_id"),
        "run_id": run.get("id"),
        "requested_by_user_id": requested,
        "assignee_user_id": assignee,
        "kind": kind,
        "question": question,
        "options": options,
        "answer": None,
        "status": "pending",
        "call_id": call_id,
        "created_at": now,
        "answered_at": None,
        "updated_at": now,
    }
    run["status"] = "waiting_input"
    run["pending_question_id"] = row_id
    text = question if not options else f"{question} ({', '.join(options)})"
    assistant["text"] = text
    assistant["content"] = [{"type": "text", "text": text}]
    assistant["status"] = "streaming"
    _emit(
        store,
        run,
        "input.required",
        {
            "question_id": str(row_id),
            "question": question,
            "options": options,
            "kind": kind,
            "prompt": text,
        },
    )
    _notify(store, run, row_id, assignee, question)
    _audit(store, run, "human_question.asked", "success")
    return None


def accept_human_answer(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, run: dict[str, object], text: str
) -> None:
    """Record the answer. The requester cannot approve their own request."""
    question_id = run.get("pending_question_id")
    row = _bucket(store).get(question_id)
    if (
        not isinstance(row, dict)
        or row.get("tenant_id") != tenant_id
        or row.get("run_id") != run.get("id")
    ):
        raise NotFoundError()
    if row.get("status") != "pending":
        raise ValidationFailedError("this question is no longer waiting")
    if row.get("assignee_user_id") != user_id:
        if row.get("tenant_id") != tenant_id:
            raise NotFoundError()
        raise NotFoundError()
    if row.get("kind") == _APPROVAL and row.get("requested_by_user_id") == user_id:
        _audit(store, run, "human_question.denied", "failure")
        raise ValidationFailedError("you cannot approve your own request")
    answer = text.strip()
    options = row.get("options")
    if isinstance(options, list) and options and answer not in {str(item) for item in options}:
        raise ValidationFailedError("answer must be one of the options")
    if not answer:
        raise ValidationFailedError("an answer is required")
    row["answer"] = answer
    row["status"] = "answered"
    row["answered_at"] = utcnow()
    row["updated_at"] = utcnow()
    run["resume_answer"] = answer
    run["resume"] = True
    run["status"] = "running"
    run["pending_question_id"] = None
    _emit(store, run, "input.resolved", {"question_id": str(row["id"]), "answer": answer})
    _audit(store, run, "human_question.answered", "success")


def list_questions(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[dict[str, object]]:
    rows = [
        _public(row)
        for row in _bucket(store).values()
        if row.get("tenant_id") == tenant_id
        and row.get("assignee_user_id") == user_id
        and row.get("status") == "pending"
    ]
    rows.sort(key=lambda item: str(item.get("created_at")))
    return rows


def question_for_actor(
    store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID, question_id: uuid.UUID
) -> dict[str, object]:
    row = _bucket(store).get(question_id)
    if not isinstance(row, dict) or row.get("tenant_id") != tenant_id:
        raise NotFoundError()
    if row.get("assignee_user_id") != user_id:
        raise NotFoundError()
    return row


def _public(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row.get("id"),
        "run_id": row.get("run_id"),
        "kind": row.get("kind"),
        "question": row.get("question"),
        "options": row.get("options") or [],
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }


def _bucket(store: Any) -> dict[object, dict[str, object]]:
    current = getattr(store, "human_questions", None)
    if not isinstance(current, dict):
        current = {}
        store.human_questions = current
    return current


def _options(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value:
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def _bad(message: str) -> dict[str, object]:
    return {"failed": True, "text": message}


def _emit(store: Any, run: dict[str, object], event_type: str, data: dict[str, object]) -> None:
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(run, event_type, data)


def _notify(
    store: Any, run: dict[str, object], question_id: uuid.UUID, user_id: uuid.UUID, question: str
) -> None:
    notes = getattr(store, "notifications", None)
    if not isinstance(notes, list):
        return
    notes.append(
        {
            "id": str(new_id()),
            "tenant_id": str(run.get("tenant_id")),
            "user_id": str(user_id),
            "kind": "human_question",
            "title": "A run is waiting for you",
            "body": question[:240],
            "link": "/inbox",
            "question_id": str(question_id),
            "read": False,
        }
    )


def _audit(store: Any, run: dict[str, object], action: str, outcome: str) -> None:
    audit = getattr(store, "audit_log", None)
    if not isinstance(audit, list):
        return
    audit.append(
        {
            "tenant_id": str(run.get("tenant_id")),
            "actor_id": str(run.get("user_id")),
            "action": action,
            "target_type": "run",
            "target_id": str(run.get("id")),
            "detail": {},
            "outcome": outcome,
            "at": utcnow().isoformat(),
        }
    )
