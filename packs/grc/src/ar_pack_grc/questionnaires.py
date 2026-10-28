"""Answer library, grounded drafts and the export guard."""

from __future__ import annotations

import hashlib
import uuid
from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.knowledge.grounding import apply_grounding
from ar_domain.records.access import require
from ar_pack_grc.access import one, page, present, record, same_tenant, snake_body
from ar_pack_grc.access import rows as bucket_rows
from ar_pack_grc.reviews import open_review, signed_for
from ar_pack_grc.values import required_text, string_list, when

if TYPE_CHECKING:
    from datetime import datetime

    from ar_domain.agents.access import Actor

_REMOVED = "This answer was removed because it was not grounded"


def list_answers(store: Any, actor: Actor, query: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.questionnaires:read")
    sync_approvals(store, actor)
    body = snake_body(query)
    text = str(body.get("q") or "")
    include_expired = str(body.get("include_expired") or "").lower() == "true"
    items = [
        present(row)
        for row in _matching(
            store, actor, text, include_expired=include_expired, approved_only=False
        )
    ]
    jobs = [
        present(row)
        for row in bucket_rows(store, "grc_questionnaire_jobs").values()
        if same_tenant(row, actor.tenant_id)
    ]
    found = page(items)
    found["jobs"] = jobs
    return found


def create_answer(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.questionnaires:manage")
    body = snake_body(payload)
    row = _insert(
        store,
        actor,
        question=required_text(body.get("question"), "question"),
        answer_md=str(body.get("answer_md") or ""),
        status="draft",
        expires_at=when(body.get("expires_at")),
        citations=string_list(body.get("citations")),
        owner_user_id=body.get("owner_user_id") or actor.user_id,
    )
    return present(row)


def patch_answer(
    store: Any, actor: Actor, answer_id: uuid.UUID, payload: dict[str, Any]
) -> dict[str, Any]:
    require(actor, "grc.questionnaires:manage")
    row = one(store, "grc_answers", actor, answer_id)
    body = snake_body(payload)
    if "answer_md" in body:
        row["answer_md"] = str(body.get("answer_md") or "")
    if "expires_at" in body:
        row["expires_at"] = when(body.get("expires_at"))
    if "question" in body:
        row["question"] = required_text(body.get("question"), "question")
    if "citations" in body:
        row["citations"] = string_list(body.get("citations"))
    if "status" in body:
        _set_status(store, actor, row, str(body.get("status") or ""))
    row["updated_at"] = utcnow()
    return present(row)


def search_answers(store: Any, actor: Actor, query: str) -> list[dict[str, Any]]:
    """Approved answers only. An expired row never matches."""
    require(actor, "grc.questionnaires:read")
    return [present(row) for row in _matching(store, actor, query, include_expired=False)]


def draft_text(store: Any, actor: Actor, question: str) -> dict[str, Any]:
    """Strict draft. A factual sentence without a citation is dropped."""
    sources = _matching(store, actor, question, include_expired=False)
    grounded = ground(question, sources)
    grounded["question"] = question
    return grounded


def draft_job(store: Any, actor: Actor, payload: dict[str, Any]) -> dict[str, Any]:
    require(actor, "grc.questionnaires:manage")
    body = snake_body(payload)
    file_id = _file_id(body.get("file_id"))
    raw = store.blobs.get(file_id, b"")
    if not isinstance(raw, bytes) or not raw:
        raise NotFoundError()
    questions = [
        line.strip() for line in raw.decode("utf-8", "replace").splitlines() if line.strip()
    ]
    if not questions:
        raise ValidationFailedError("the file has no questions")
    job_id = new_id()
    answers = []
    for question in questions:
        drafted = draft_text(store, actor, question)
        saved = _insert(
            store,
            actor,
            question=question,
            answer_md=str(drafted.get("answer_md") or ""),
            status="draft",
            expires_at=None,
            citations=[str(item.get("answer_id")) for item in drafted.get("citations") or []],
            owner_user_id=actor.user_id,
        )
        answers.append({"answer_id": saved["id"], "question": question})
    bucket_rows(store, "grc_questionnaire_jobs")[job_id] = {
        "id": job_id,
        "tenant_id": actor.tenant_id,
        "file_id": file_id,
        "run_id": job_id,
        "answers": answers,
        "created_at": utcnow(),
    }
    return {"run_id": str(job_id), "job_id": str(job_id)}


def export_job(store: Any, actor: Actor, job_id: uuid.UUID) -> dict[str, Any]:
    require(actor, "grc.questionnaires:manage")
    sync_approvals(store, actor)
    job = one(store, "grc_questionnaire_jobs", actor, job_id)
    lines = ["question,answer,status"]
    for item in job.get("answers") or []:
        if not isinstance(item, dict):
            continue
        answer = one(store, "grc_answers", actor, uuid.UUID(str(item["answer_id"])))
        if answer.get("status") != "approved":
            raise ConflictError("review_required")
        lines.append(
            ",".join(
                [
                    _cell(str(answer.get("question") or "")),
                    _cell(str(answer.get("answer_md") or "")),
                    "approved",
                ]
            )
        )
    return {"format": "csv", "filename": "questionnaire.csv", "body": "\n".join(lines)}


def open_reviews(store: Any, actor: Actor, answer_ids: list[uuid.UUID]) -> list[dict[str, Any]]:
    """One core review item per answer. Bulk decide stays on the core queue."""
    opened = []
    for answer_id in answer_ids:
        row = one(store, "grc_answers", actor, answer_id)
        content = str(row.get("answer_md") or row.get("question") or "answer")
        item = open_review(
            store,
            actor,
            slug="grc-answers",
            subject_id=answer_id,
            content=content,
            statement=f"I approve this answer ({row.get('question')}).",
        )
        row["review_item_id"] = item.get("id")
        opened.append(item)
    return opened


def sync_approvals(store: Any, actor: Actor) -> int:
    """A signed review approves the answer and audits once."""
    changed = 0
    for row in bucket_rows(store, "grc_answers").values():
        if not same_tenant(row, actor.tenant_id) or row.get("status") == "approved":
            continue
        content = str(row.get("answer_md") or row.get("question") or "answer")
        digest = hashlib.sha256(content.encode()).hexdigest()
        if signed_for(store, row["id"], digest) is None:
            continue
        row["status"] = "approved"
        row["updated_at"] = utcnow()
        record(store, actor, "grc.answer.approved", row["id"], {"question": row.get("question")})
        changed += 1
    return changed


def ground(question: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep a sentence only when it carries a citation the library supplied."""
    del question
    pieces: list[str] = []
    indexes: set[int] = set()
    citations: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        marks = source.get("citations") or []
        text = str(source.get("answer_md") or "").strip()
        if not text or (not marks and "[" not in text):
            continue
        cited = _with_marks(text, index)
        pieces.append(cited)
        indexes.add(index)
        citations.append({"index": index, "answer_id": str(source.get("id") or "")})
    if not pieces:
        return {"answer_md": "", "citations": [], "grounded": False}
    visible, _report = apply_grounding(" ".join(pieces), indexes, mode="strict")
    if visible.startswith(_REMOVED):
        visible = ""
    return {
        "answer_md": visible,
        "citations": citations if visible else [],
        "grounded": bool(visible),
    }


def _with_marks(text: str, index: int) -> str:
    if f"[{index}]" in text:
        return text
    sentences = [
        part.strip() for part in text.replace("!", ".").replace("?", ".").split(".") if part.strip()
    ]
    if not sentences:
        return f"{text} [{index}]"
    return " ".join(f"{part} [{index}]." for part in sentences)


def _matching(
    store: Any,
    actor: Actor,
    query: str,
    *,
    include_expired: bool,
    approved_only: bool = True,
) -> list[dict[str, Any]]:
    now = utcnow()
    found = []
    for row in bucket_rows(store, "grc_answers").values():
        if not same_tenant(row, actor.tenant_id):
            continue
        if approved_only and row.get("status") != "approved":
            continue
        if _expired(row.get("expires_at"), now) and not include_expired:
            continue
        if query and query.lower() not in str(row.get("question") or "").lower():
            continue
        found.append(row)
    return found


def _expired(expires: object, now: datetime) -> bool:
    parsed = when(expires) if expires else None
    return parsed is not None and parsed <= now


def _insert(
    store: Any,
    actor: Actor,
    *,
    question: str,
    answer_md: str,
    status: str,
    expires_at: datetime | None,
    citations: list[str],
    owner_user_id: object,
) -> dict[str, Any]:
    item_id = new_id()
    now = utcnow()
    row = {
        "id": item_id,
        "tenant_id": actor.tenant_id,
        "question": question,
        "answer_md": answer_md,
        "status": status,
        "owner_user_id": owner_user_id,
        "expires_at": expires_at,
        "citations": citations,
        "created_at": now,
        "updated_at": now,
    }
    bucket_rows(store, "grc_answers")[item_id] = row
    return row


def _set_status(store: Any, actor: Actor, row: dict[str, Any], status: str) -> None:
    if status not in {"draft", "approved", "expired"}:
        raise ValidationFailedError("status is invalid")
    if status == "approved" and row.get("status") != "approved":
        record(store, actor, "grc.answer.approved", row["id"], {"question": row.get("question")})
    row["status"] = status


def _file_id(value: object) -> uuid.UUID:
    parsed = value if isinstance(value, uuid.UUID) else None
    if parsed is None:
        try:
            parsed = uuid.UUID(str(value))
        except ValueError as exc:
            raise NotFoundError() from exc
    return parsed


def _cell(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
