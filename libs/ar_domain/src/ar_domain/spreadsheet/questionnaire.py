"""Fill a questionnaire workbook and write the answers back to xlsx.

Answers come from the caller or from a library document that caller can read.
The workbook is the same writer as ``documents.create``.
"""

from __future__ import annotations

import re
import uuid
import zipfile
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ar_common.errors import ArError
from ar_domain.documents.chunk import score
from ar_domain.documents.create.spec import MAX_COLUMNS, MAX_ROWS, CreateError

if TYPE_CHECKING:
    from typing import Any

_GROUND = 0.34
_ANSWER_MARK = ("answer", "response")
_NOTE_MARK = ("note", "comment")
_CITE_MARK = ("citation", "evidence", "reference")
_QUESTION_MARK = ("question", "requirement", "inquiry", "prompt")


@dataclass(frozen=True)
class _Hit:
    answer: str
    notes: str
    citation: str
    status: str


def fill_questionnaire(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """Write a filled workbook into the run workspace."""
    try:
        return _fill(store, arguments)
    except CreateError as exc:
        return _error("validation_failed", str(exc))
    except ArError as exc:
        return _error(exc.code.value, exc.detail)
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        return _error("validation_failed", str(exc)[:300])


def _fill(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    from ar_domain.documents.create import publish  # noqa: PLC0415
    from ar_domain.documents.library import DocumentLibrary  # noqa: PLC0415
    from ar_domain.tools.documents import _actor  # noqa: PLC0415

    actor = _actor(arguments)
    if actor is None:
        return _error("validation_failed", "The document tool needs a tenant.")
    grid = _load_grid(store, arguments)
    columns = grid.columns
    roles = _roles(columns)
    passages = _passages(DocumentLibrary(store), actor, arguments)
    provided = _answers(arguments.get("answers"))
    filled, grounded, unanswered, rows, trace = _apply(grid, roles, provided, passages)
    sheets = [
        {"name": grid.name, "columns": list(_output_columns(columns)), "rows": rows},
        {
            "name": "Trace",
            "columns": ["Question ID", "Question", "Status", "Citation"],
            "rows": trace,
        },
    ]
    title = str(arguments.get("title") or "Filled questionnaire")
    filename = str(
        arguments.get("fileName") or arguments.get("file_name") or "questionnaire-filled.xlsx"
    )
    payload: dict[str, object] = {
        "format": "xlsx",
        "title": title,
        "template": "sheet",
        "fileName": filename,
        "sheets": sheets,
    }
    for key in ("_tenant_id", "_user_id", "_run_id", "_conversation_id"):
        if key in arguments:
            payload[key] = arguments[key]
    saved = publish(store, payload)
    if saved.get("is_error"):
        return saved
    structured = saved.get("structured")
    presentation = structured.get("presentation") if isinstance(structured, dict) else None
    if isinstance(presentation, dict):
        presentation["filled"] = filled
        presentation["grounded"] = grounded
        presentation["unanswered"] = unanswered
    saved["text"] = (
        f"Filled {filled + grounded} of {filled + grounded + unanswered} rows "
        f"({filled} provided, {grounded} grounded, {unanswered} unanswered). "
        f"{saved.get('text')}"
    )
    return saved


def _load_grid(store: Any, arguments: dict[str, object]) -> Any:
    from ar_domain.spreadsheet.grid import grids_from_xlsx  # noqa: PLC0415
    from ar_domain.tools.analysis import _open_path, _root  # noqa: PLC0415

    root = _root(store, arguments)
    path = _open_path(root, str(arguments.get("path") or ""))
    if path is None or path.suffix.lower() != ".xlsx":
        raise CreateError("path must be an xlsx file in this run's workspace")
    grids = grids_from_xlsx(path.read_bytes(), max_rows=MAX_ROWS)
    if not grids:
        raise CreateError("The workbook has no rows.")
    wanted = str(arguments.get("sheet") or "").strip().lower()
    grid = grids[0]
    if wanted:
        match = next((item for item in grids if item.name.lower() == wanted), None)
        if match is None:
            raise CreateError(f"sheet {wanted} was not found")
        grid = match
    if len(grid.columns) > MAX_COLUMNS:
        raise CreateError(f"A table can have at most {MAX_COLUMNS} columns.")
    if "question" not in _roles(grid.columns):
        raise CreateError("The sheet needs a question column.")
    return grid


def _extend(found: list[dict[str, str]], items: object, title: str) -> None:
    if not isinstance(items, list):
        return
    found.extend(
        [
            _passage(item, str(item.get("title") or title))
            for item in items
            if isinstance(item, dict)
        ]
    )


def _passages(library: Any, actor: Any, arguments: dict[str, object]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    document_id = arguments.get("documentId") or arguments.get("document_id")
    if document_id:
        body = library.read(actor, _uuid(document_id))
        _extend(found, body.get("passages"), str(body.get("title") or ""))
    if _flag(arguments.get("searchLibrary") or arguments.get("search_library")):
        _extend(found, library.search(actor, _questions_query(arguments)), "")
    _extend(found, arguments.get("sources"), "")
    if not found and not _answers(arguments.get("answers")):
        raise CreateError("pass answers, sources, or documentId")
    return found


def _passage(item: dict[str, object], title: str) -> dict[str, str]:
    anchor = str(item.get("anchor") or "")
    citation = f"{title} {anchor}".strip()
    return {
        "text": str(item.get("text") or item.get("snippet") or ""),
        "citation": citation,
    }


def _questions_query(arguments: dict[str, object]) -> str:
    raw = arguments.get("answers")
    if isinstance(raw, list):
        parts = [
            str(item.get("question") or "")
            for item in raw
            if isinstance(item, dict) and item.get("question")
        ]
        if parts:
            return " ".join(parts)[:500]
    return str(arguments.get("query") or "question")


def _apply(
    grid: Any,
    roles: dict[str, int],
    provided: list[dict[str, str]],
    passages: list[dict[str, str]],
) -> tuple[int, int, int, list[dict[str, object]], list[dict[str, str]]]:
    columns = _output_columns(grid.columns)
    filled = grounded = unanswered = 0
    rows: list[dict[str, object]] = []
    trace: list[dict[str, str]] = []
    for source in grid.rows:
        if not any(str(cell).strip() for cell in source):
            continue
        record = {columns[index]: _value(source, index) for index in range(len(grid.columns))}
        question = _text(source, roles.get("question"))
        row_id = _text(source, roles.get("id"))
        hit = _provided(row_id, question, provided) or _ground(question, passages)
        if hit is None and _text(source, roles.get("answer")).strip():
            hit = _Hit("", "", _text(source, roles.get("citation")), "kept")
        if hit is None:
            hit = _Hit("", "", "", "unanswered")
            unanswered += 1
        elif hit.status == "provided":
            filled += 1
        elif hit.status == "grounded":
            grounded += 1
        if hit.status != "kept":
            record["Answer" if "answer" not in roles else grid.columns[roles["answer"]]] = (
                hit.answer
            )
            record[_named(grid, roles, "notes", "Notes")] = hit.notes
            record[_named(grid, roles, "citation", "Citation")] = hit.citation
        record[_named(grid, roles, "status", "Status")] = hit.status
        rows.append(record)
        trace.append(
            {
                "Question ID": row_id,
                "Question": question,
                "Status": hit.status,
                "Citation": hit.citation
                or str(record.get(_named(grid, roles, "citation", "Citation")) or ""),
            }
        )
    if len(rows) > MAX_ROWS:
        raise CreateError(f"A table can have at most {MAX_ROWS} rows.")
    return filled, grounded, unanswered, rows, trace


def _named(grid: Any, roles: dict[str, int], role: str, fallback: str) -> str:
    if role in roles:
        return str(grid.columns[roles[role]])
    return fallback


def _output_columns(columns: tuple[str, ...]) -> tuple[str, ...]:
    roles = _roles(columns)
    names = list(columns)
    for role, label in (
        ("answer", "Answer"),
        ("notes", "Notes"),
        ("citation", "Citation"),
        ("status", "Status"),
    ):
        if role not in roles:
            names.append(label)
    if len(names) > MAX_COLUMNS:
        raise CreateError(f"A table can have at most {MAX_COLUMNS} columns.")
    return tuple(names)


def _roles(columns: tuple[str, ...]) -> dict[str, int]:
    found: dict[str, int] = {}
    for index, name in enumerate(columns):
        role = _role(name)
        if role and role not in found:
            found[role] = index
    return found


def _role(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    role = ""
    if key in {"id", "qid", "question_id", "questionid", "control_id", "caiq_id"} or (
        key.endswith("_id") and "question" in key
    ):
        role = "id"
    elif any(mark in key for mark in _ANSWER_MARK):
        role = "answer"
    elif key == "status":
        role = "status"
    elif any(mark in key for mark in _NOTE_MARK):
        role = "notes"
    elif any(mark in key for mark in _CITE_MARK) or key == "source":
        role = "citation"
    elif key in _QUESTION_MARK or key.endswith("question"):
        role = "question"
    return role


def _provided(row_id: str, question: str, answers: list[dict[str, str]]) -> _Hit | None:
    wanted_id = row_id.casefold()
    if wanted_id:
        for item in answers:
            if item.get("id", "").casefold() == wanted_id:
                return _hit(item, "provided")
    norm = _norm(question)
    if norm:
        for item in answers:
            if _norm(item.get("question", "")) == norm:
                return _hit(item, "provided")
    return None


def _ground(question: str, passages: list[dict[str, str]]) -> _Hit | None:
    if not question.strip() or not passages:
        return None
    best: dict[str, str] | None = None
    best_score = 0.0
    for item in passages:
        weight = score(question, item.get("text", ""))
        if weight > best_score:
            best_score = weight
            best = item
    if best is None or best_score < _GROUND:
        return None
    text = best.get("text", "").strip()
    return _Hit(text[:500], "", best.get("citation", ""), "grounded")


def _hit(item: dict[str, str], status: str) -> _Hit:
    return _Hit(
        item.get("answer", ""),
        item.get("notes", ""),
        item.get("citation", ""),
        status,
    )


def _answers(raw: object) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise CreateError("answers must be a list.")
    found: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise CreateError("Each answer must be an object.")
        found.append(
            {
                "id": str(
                    item.get("id") or item.get("questionId") or item.get("question_id") or ""
                ),
                "question": str(item.get("question") or ""),
                "answer": str(item.get("answer") or ""),
                "notes": str(item.get("notes") or ""),
                "citation": str(item.get("citation") or ""),
            }
        )
    return found


def _value(row: tuple[str, ...], index: int) -> object:
    text = row[index] if index < len(row) else ""
    stripped = text.strip()
    if re.fullmatch(r"-?\d+", stripped) and not (
        len(stripped.lstrip("-")) > 1 and stripped.lstrip("-").startswith("0")
    ):
        return int(stripped)
    if re.fullmatch(r"-?\d+\.\d+", stripped):
        return float(stripped)
    return text


def _text(row: tuple[str, ...], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return str(row[index])


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _flag(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).lower() in {"1", "true", "yes"}


def _uuid(value: object) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise CreateError("documentId must be a uuid") from exc


def _error(code: str, message: str) -> dict[str, object]:
    return {
        "text": message,
        "structured": {"presentation": {"kind": "error", "message": message}, "code": code},
        "is_error": True,
        "code": code,
    }
