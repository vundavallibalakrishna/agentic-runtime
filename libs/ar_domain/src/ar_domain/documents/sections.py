"""One section of a documents.map call.

The model asks for the reading. Each section is one activity. The key is the
run, the file and the anchor. A retry reads the stored result and does not call
the model again. A missing model is an error. Results are kept so a later turn
can read them with context.retrieve.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson
from jsonschema import Draft202012Validator

from ar_common.errors import ArError, ErrorCode
from ar_common.settings import get_settings
from ar_common.wrapping import wrap_untrusted
from ar_domain.jobs.progress import note_job

if TYPE_CHECKING:
    from typing import Any

_TOOL = "documents.map"


def pending_sections(_store: Any, run: dict[str, object]) -> list[dict[str, object]] | None:
    """Sections still to read for the open map, or None when there is no open map."""
    job = _job(run)
    if job is None or job.get("delivered"):
        return None
    done = job.get("done")
    finished = done if isinstance(done, dict) else {}
    pending = [
        _public(section) for section in _rows(job.get("sections")) if _key(section) not in finished
    ]
    return pending or None


def map_ready(run: dict[str, object]) -> bool:
    """True when the open map has a stored result for every section it took."""
    job = _job(run)
    if job is None:
        return False
    done = job.get("done")
    finished = done if isinstance(done, dict) else {}
    sections = _rows(job.get("sections"))
    return bool(sections) and all(_key(section) in finished for section in sections)


def begin_map(
    store: Any, run: dict[str, object], arguments: dict[str, object]
) -> dict[str, object]:
    """Record the model's map. A second call for the same cursor does not rebuild it."""
    current = _job(run)
    cursor = str(arguments.get("cursor") or "")
    if (
        current is not None
        and not current.get("delivered")
        and str(current.get("cursor") or "") == cursor
    ):
        return current
    sections = _select(store, run, arguments)
    settings = get_settings()
    cap = int(settings.document_section_cap)
    start = _cursor_index(cursor)
    window = sections[start : start + cap]
    job = {
        "instruction": str(arguments.get("instruction") or "").strip(),
        "outputSchema": arguments.get("outputSchema") or arguments.get("output_schema"),
        "sections": window,
        "done": {},
        "delivered": False,
        "cursor": cursor,
        "nextCursor": f"s:{start + cap}" if start + cap < len(sections) else "",
        "total": len(sections),
        "start": start,
    }
    if not job["instruction"]:
        raise ArError(ErrorCode.VALIDATION_FAILED, "documents.map needs the instruction.")
    schema = job["outputSchema"]
    if schema is not None and not isinstance(schema, dict):
        raise ArError(ErrorCode.VALIDATION_FAILED, "outputSchema must be a JSON Schema object.")
    checkpoint = _checkpoint(run)
    checkpoint["document_map"] = job
    run["checkpoint"] = checkpoint
    return job


def run_section(
    store: Any, run: dict[str, object], section: dict[str, object]
) -> dict[str, object]:
    """One section. A stored result is returned without another model call."""
    job = _job(run)
    if job is None:
        raise ArError(ErrorCode.INVALID_STATE, "There is no document map to read.")
    key = _key(section)
    done = job.setdefault("done", {})
    if not isinstance(done, dict):
        done = {}
        job["done"] = done
    stored = done.get(key)
    if isinstance(stored, dict):
        return stored
    passages = _rows(job.get("sections"))
    source = next((row for row in passages if _key(row) == key), section)
    text = str(source.get("text") or "")
    output = _read_model(store, run, job, source, text)
    quote = text[: int(get_settings().document_search_snippet_chars)]
    result = {
        "fileId": str(source.get("fileId") or section.get("fileId") or ""),
        "documentId": str(source.get("documentId") or ""),
        "anchor": str(source.get("anchor") or ""),
        "page": source.get("page"),
        "heading": str(source.get("heading") or ""),
        "quote": quote,
        "output": output,
    }
    done[key] = result
    completed = len(done)
    total = len(passages)
    _progress(
        store, run, completed, total, str(source.get("heading") or source.get("anchor") or "")
    )
    return result


def deliver_map(store: Any, run: dict[str, object]) -> dict[str, object]:
    """The cited map result, stored so a follow-up can retrieve it."""
    job = _job(run)
    if job is None or not map_ready(run):
        raise ArError(ErrorCode.INVALID_STATE, "The document map is not finished.")
    done = job.get("done")
    rows = [row for row in done.values() if isinstance(row, dict)] if isinstance(done, dict) else []
    body = {
        "kind": "map",
        "results": [_cited(row) for row in rows],
        "nextCursor": str(job.get("nextCursor") or ""),
        "total": job.get("total"),
        "read": len(rows),
    }
    note = _note(rows, str(job.get("nextCursor") or ""))
    from ar_domain.loop.context import context_book, retain_output  # noqa: PLC0415

    retained = context_book(run)
    output_id = retain_output(retained, note) if note else ""
    if output_id:
        body["outputId"] = output_id
    job["delivered"] = True
    wrapped = wrap_untrusted(source="document", content=note) if note else ""
    run["document_reduction"] = wrapped
    _remember_for_followups(store, run, retained, wrapped)
    return body


def run_pending(store: Any, run: dict[str, object]) -> None:
    """Read every pending section in this process. The workflow uses activities instead."""
    pending = pending_sections(store, run)
    while pending:
        for section in pending:
            run_section(store, run, section)
        pending = pending_sections(store, run)


def carry_outputs(store: Any, run: dict[str, object]) -> None:
    """Copy map results the conversation already stored into this run's retrieve book."""
    from ar_domain.loop.context import context_book  # noqa: PLC0415

    conversation = _conversation(store, run)
    if not isinstance(conversation, dict):
        return
    saved = conversation.get("document_outputs")
    if isinstance(saved, dict) and saved:
        book = context_book(run)
        outputs = book.get("outputs")
        if not isinstance(outputs, dict):
            outputs = {}
            book["outputs"] = outputs
        for key, value in saved.items():
            if key not in outputs:
                outputs[key] = value
    if not run.get("document_reduction") and isinstance(
        conversation.get("document_reduction"), str
    ):
        run["document_reduction"] = conversation["document_reduction"]


def _remember_for_followups(
    store: Any, run: dict[str, object], retained: dict[str, object], wrapped: str
) -> None:
    conversation = _conversation(store, run)
    if not isinstance(conversation, dict):
        return
    outputs = retained.get("outputs")
    if isinstance(outputs, dict):
        conversation["document_outputs"] = dict(outputs)
    if wrapped:
        conversation["document_reduction"] = wrapped


def _conversation(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    conversations = getattr(store, "conversations", None)
    if not isinstance(conversations, dict):
        return None
    row = conversations.get(run.get("conversation_id"))
    return row if isinstance(row, dict) else None


def tools_part(run: dict[str, object]) -> dict[str, object] | None:
    """The tools this turn called, so the reading chip can name them."""
    raw = run.get("tools_used")
    if not isinstance(raw, list) or not raw:
        return None
    names = [str(item) for item in raw if str(item)]
    if not names:
        return None
    return {"type": "reading", "tools": names}


def _read_model(
    store: Any,
    run: dict[str, object],
    job: dict[str, object],
    section: dict[str, object],
    text: str,
) -> object:
    if not text.strip():
        return ""
    alias = _alias(store, run)
    if not alias:
        raise ArError(
            ErrorCode.INVALID_STATE,
            "No model is configured, so this section cannot be read.",
        )
    from ar_domain.documents.model import ModelAsk  # noqa: PLC0415

    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        raise ArError(
            ErrorCode.INVALID_STATE, "No model is configured, so this section cannot be read."
        )
    schema = job.get("outputSchema")
    task = str(job.get("instruction") or "")
    if isinstance(schema, dict):
        task = (
            f"{task}\n\nReturn one JSON object that validates against this JSON Schema. "
            "Use only the section. Do not add a fact that is not in it.\n"
            + orjson.dumps(schema).decode()
        )
    else:
        task = f"{task}\n\nUse only the section. Do not add a fact that is not in it."
    raw = ModelAsk(store, tenant, alias)(
        task,
        wrap_untrusted(source="document", content=f"[{section.get('anchor')}] {text}"),
    )
    if not isinstance(raw, str) or not raw.strip():
        raise ArError(ErrorCode.INVALID_STATE, "The model returned no reading for this section.")
    if not isinstance(schema, dict):
        return " ".join(raw.split())
    parsed = _json_object(raw)
    errors = list(Draft202012Validator(schema).iter_errors(parsed))
    if errors:
        raise ArError(ErrorCode.INVALID_STATE, "The model reading did not match outputSchema.")
    return parsed


def _json_object(raw: str) -> object:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return orjson.loads(text)
    except orjson.JSONDecodeError as exc:
        raise ArError(ErrorCode.INVALID_STATE, "The model reading was not JSON.") from exc


def _alias(store: Any, run: dict[str, object]) -> str:
    from ar_domain.tools.agent_loop import model_alias_for  # noqa: PLC0415

    try:
        alias = model_alias_for(store, run)
    except Exception as exc:
        raise ArError(
            ErrorCode.INVALID_STATE,
            "No model is configured, so this section cannot be read.",
        ) from exc
    return str(alias or "")


def _select(
    store: Any, run: dict[str, object], arguments: dict[str, object]
) -> list[dict[str, object]]:
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415

    library = DocumentLibrary(store)
    actor = _actor(store, run)
    if actor is None:
        raise ArError(ErrorCode.VALIDATION_FAILED, "The document tool needs a tenant.")
    rows = library.rows_for_map(
        actor,
        run,
        document_ids=_ids(arguments.get("documentIds") or arguments.get("document_ids")),
        file_ids=_ids(arguments.get("fileIds") or arguments.get("file_ids")),
        collection_ids=_ids(arguments.get("collectionIds") or arguments.get("collection_ids")),
    )
    heading = str(arguments.get("heading") or "").strip()
    anchor_from = str(arguments.get("anchorFrom") or arguments.get("anchor_from") or "")
    anchor_to = str(arguments.get("anchorTo") or arguments.get("anchor_to") or "")
    page_from = _int(arguments.get("pageFrom") or arguments.get("page_from"))
    page_to = _int(arguments.get("pageTo") or arguments.get("page_to"))
    found: list[dict[str, object]] = []
    for row in rows:
        for passage in _rows(row.get("passages")):
            if not passage.get("anchor"):
                continue
            if heading and str(passage.get("heading") or "") != heading:
                continue
            page = _int(passage.get("page")) or 1
            if page_from and page < page_from:
                continue
            if page_to and page > page_to:
                continue
            anchor = str(passage.get("anchor") or "")
            if anchor_from and anchor < anchor_from:
                continue
            if anchor_to and anchor > anchor_to:
                continue
            found.append(
                {
                    "fileId": str(row.get("file_id") or ""),
                    "documentId": str(row.get("id") or ""),
                    "anchor": anchor,
                    "page": passage.get("page"),
                    "heading": str(passage.get("heading") or ""),
                    "text": str(passage.get("text") or ""),
                }
            )
    if not found:
        raise ArError(ErrorCode.NOT_FOUND, "No section matched that map.")
    return found


def _actor(_store: Any, run: dict[str, object]) -> Any:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

    tenant = run.get("tenant_id")
    user = run.get("user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return None
    return Actor(tenant, user, PERMISSION_KEYS)


def _ids(value: object) -> list[str]:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _cited(row: dict[str, object]) -> dict[str, object]:
    return {
        "fileId": row.get("fileId"),
        "documentId": row.get("documentId"),
        "anchor": row.get("anchor"),
        "page": row.get("page"),
        "heading": row.get("heading"),
        "quote": row.get("quote"),
        "output": row.get("output"),
    }


def _note(rows: list[dict[str, object]], nxt: str) -> str:
    lines = [
        f"[{row.get('anchor')} p.{row.get('page')}] {row.get('output') or row.get('quote')}"
        for row in rows
    ]
    if nxt:
        lines.append(f"More sections remain. Pass cursor {nxt} to read the next page.")
    return "\n".join(str(line) for line in lines)


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


def _job(run: dict[str, object]) -> dict[str, object] | None:
    checkpoint = run.get("checkpoint")
    if not isinstance(checkpoint, dict):
        return None
    job = checkpoint.get("document_map")
    return job if isinstance(job, dict) else None


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


def _cursor_index(cursor: str) -> int:
    if cursor.startswith("s:"):
        try:
            return max(0, int(cursor[2:]))
        except ValueError:
            return 0
    return 0


def _int(value: object) -> int:
    if isinstance(value, bool) or value in {None, ""}:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0
