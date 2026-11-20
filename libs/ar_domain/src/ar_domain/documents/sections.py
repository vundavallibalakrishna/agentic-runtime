"""Section work for one agent run.

A section is one activity. The key is the run, the file and the anchor. A
retry reads the stored result and does not call the model again. More sections
than the install allows are left unread, and the run says so.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.wrapping import wrap_untrusted
from ar_domain.jobs.progress import note_job
from ar_domain.runs.request import asked

if TYPE_CHECKING:
    from typing import Any

_TOOL = "documents.section"


def next_batch(store: Any, run: dict[str, object]) -> list[dict[str, object]] | None:
    """Sections still to read, or None when this turn is not a section task."""
    if str(asked(run, "strategy") or "") != "map_reduce":
        return None
    plan = _plan(store, run)
    done = plan.get("done")
    finished = done if isinstance(done, dict) else {}
    pending = [
        _public(section) for section in _rows(plan.get("sections")) if _key(section) not in finished
    ]
    if pending:
        return pending
    if not plan.get("reduced"):
        _reduce(run, plan)
    return None


def run_section(
    store: Any, run: dict[str, object], section: dict[str, object]
) -> dict[str, object]:
    """One section. A stored result is returned without another model call."""
    plan = _plan(store, run)
    key = _key(section)
    done = plan.setdefault("done", {})
    if not isinstance(done, dict):
        done = {}
        plan["done"] = done
    stored = done.get(key)
    if isinstance(stored, dict):
        return stored
    passages = _rows(plan.get("sections"))
    source = next((row for row in passages if _key(row) == key), section)
    text = str(source.get("text") or "")
    quote = text[:240]
    summary = _summarise(store, run, source, text)
    result = {
        "fileId": str(source.get("fileId") or section.get("fileId") or ""),
        "anchor": str(source.get("anchor") or ""),
        "page": source.get("page"),
        "heading": str(source.get("heading") or ""),
        "quote": quote,
        "summary": summary or "",
        "model": bool(summary) and summary != _extractive(text),
    }
    done[key] = result
    completed = len(done)
    total = len(passages)
    _progress(
        store, run, completed, total, str(source.get("heading") or source.get("anchor") or "")
    )
    if completed >= total:
        _reduce(run, plan)
    return result


def review_part(run: dict[str, object]) -> dict[str, object] | None:
    """The gap or compare table for the message, when this turn produced one."""
    plan = _checkpoint(run).get("document_task")
    if not isinstance(plan, dict):
        return None
    rows = plan.get("review")
    if not isinstance(rows, list) or not rows:
        return None
    return {"type": "review", "task": str(asked(run, "task") or ""), "rows": rows}


def run_pending(store: Any, run: dict[str, object]) -> None:
    """Read every pending section in this process. The workflow uses activities instead."""
    pending = next_batch(store, run)
    while pending:
        for section in pending:
            run_section(store, run, section)
        pending = next_batch(store, run)


def _plan(store: Any, run: dict[str, object]) -> dict[str, object]:
    checkpoint = _checkpoint(run)
    current = checkpoint.get("document_task")
    if isinstance(current, dict) and isinstance(current.get("sections"), list):
        return current
    from ar_common.settings import get_settings  # noqa: PLC0415

    sections = _sections(store, run)
    cap = int(get_settings().document_section_cap)
    plan = {
        "sections": sections[:cap],
        "truncated": len(sections) > cap,
        "done": {},
        "reduced": False,
    }
    checkpoint["document_task"] = plan
    run["checkpoint"] = checkpoint
    return plan


def _sections(store: Any, run: dict[str, object]) -> list[dict[str, object]]:
    from ar_domain.files.attachments import conversation_attachments  # noqa: PLC0415

    found: list[dict[str, object]] = []
    library = getattr(store, "library_documents", {})
    files = getattr(store, "files", {})
    for item in conversation_attachments(store, run.get("conversation_id")):
        row = library.get(item.document_id) if isinstance(library, dict) else None
        passages = row.get("passages") if isinstance(row, dict) else None
        if not isinstance(passages, list):
            continue
        for passage in passages:
            if not isinstance(passage, dict) or not passage.get("anchor"):
                continue
            found.append(
                {
                    "fileId": str(item.file_id),
                    "documentId": str(item.document_id or ""),
                    "anchor": str(passage.get("anchor") or ""),
                    "page": passage.get("page"),
                    "heading": str(passage.get("heading") or ""),
                    "text": str(passage.get("text") or ""),
                }
            )
    del files
    return found


def _reduce(run: dict[str, object], plan: dict[str, object]) -> None:
    done = plan.get("done")
    rows = list(done.values()) if isinstance(done, dict) else []
    lines = [
        f"[{row.get('anchor')} p.{row.get('page')}] {row.get('summary') or row.get('quote')}"
        for row in rows
        if isinstance(row, dict)
    ]
    if plan.get("truncated"):
        lines.append("The rest of the document was not read. The section cap was reached.")
    note = "\n".join(lines)
    run["document_reduction"] = wrap_untrusted(source="document", content=note) if note else ""
    plan["reduced"] = True
    if str(asked(run, "task") or "") == "compare":
        plan["review"] = [
            {
                "status": "paired",
                "heading": row.get("heading"),
                "quote": row.get("quote"),
                "anchor": row.get("anchor"),
                "page": row.get("page"),
            }
            for row in rows
            if isinstance(row, dict)
        ]


def _summarise(store: Any, run: dict[str, object], section: dict[str, object], text: str) -> str:
    if not text.strip():
        return ""
    ask = _ask(store, run)
    if ask is None:
        return _extractive(text)
    from ar_domain.documents.model import ModelAsk  # noqa: PLC0415

    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        return _extractive(text)
    raw = ModelAsk(store, tenant, ask)(
        "Summarise this one section in one or two sentences. "
        "Use only the section. Do not add a fact that is not in it.",
        wrap_untrusted(
            source="document",
            content=f"[{section.get('anchor')}] {text}",
        ),
    )
    if not isinstance(raw, str) or not raw.strip():
        return _extractive(text)
    return " ".join(raw.split())[:800]


def _ask(store: Any, run: dict[str, object]) -> str | None:
    from ar_domain.tools.agent_loop import model_alias_for  # noqa: PLC0415

    try:
        alias = model_alias_for(store, run)
    except Exception:  # noqa: BLE001 — a turn with no model still keeps the quote
        return None
    return alias or None


def _extractive(text: str) -> str:
    sentence = text.strip().split(". ")[0].strip()
    return sentence[:400]


def _progress(store: Any, run: dict[str, object], completed: int, total: int, label: str) -> None:
    status = "completed" if total and completed >= total else "running"
    note_job(
        store,
        {
            "_tenant_id": run.get("tenant_id"),
            "_run_id": run.get("id"),
            "_conversation_id": run.get("conversation_id"),
            "_user_id": run.get("user_id"),
        },
        kind="document_section",
        tool_name=_TOOL,
        label=label or "section",
        completed=completed,
        total=total,
        status=status,
        detail=f"section {completed} of {total}",
    )
    emit = getattr(store, "_emit", None)
    if callable(emit):
        emit(
            run,
            "tool.progress",
            {"completed": completed, "total": total, "label": label, "status": status},
        )


def _checkpoint(run: dict[str, object]) -> dict[str, object]:
    current = run.get("checkpoint")
    if isinstance(current, dict):
        return current
    fresh: dict[str, object] = {}
    run["checkpoint"] = fresh
    return fresh


def _rows(value: object) -> list[dict[str, object]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _key(section: dict[str, object]) -> str:
    return f"{section.get('fileId')}:{section.get('anchor')}"


def _public(section: dict[str, object]) -> dict[str, object]:
    return {
        "fileId": section.get("fileId"),
        "documentId": section.get("documentId"),
        "anchor": section.get("anchor"),
        "page": section.get("page"),
        "heading": section.get("heading"),
    }
