"""One research state machine. Activities and the dev driver both call this.

A step reads the checkpoint and writes it back. Repeating a finished step is a no-op.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.research.citations import source_record, verify_report
from ar_domain.research.fetch import fetch_page
from ar_domain.research.providers import scope, search

if TYPE_CHECKING:
    from typing import Any

_DEFAULTS = {
    "max_depth": 2,
    "max_breadth": 4,
    "max_wall_clock_s": 120,
    "max_cost_micros": 1_000_000,
    "max_steps": 16,
}


def initial_state(question: str, bounds: dict[str, object] | None = None) -> dict[str, object]:
    limits = dict(_DEFAULTS)
    if isinstance(bounds, dict):
        for key in _DEFAULTS:
            value = bounds.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value > 0:
                limits[key] = value
    return {
        "question": question.strip(),
        "phase": "plan",
        "depth": 0,
        "queries": [],
        "sources": [],
        "subtasks": {},
        "report": "",
        "citations": [],
        "started_at": utcnow().isoformat(),
        "cost_micros": 0,
        **limits,
    }


def state_of(run: dict[str, object], question: str) -> dict[str, object]:
    checkpoint = run.get("checkpoint")
    if not isinstance(checkpoint, dict):
        checkpoint = {}
        run["checkpoint"] = checkpoint
    raw = checkpoint.get("research")
    if isinstance(raw, dict) and raw.get("question"):
        return raw
    bounds = run.get("research_bounds")
    state = initial_state(question, bounds if isinstance(bounds, dict) else None)
    checkpoint["research"] = state
    return state


def save_state(run: dict[str, object], state: dict[str, object]) -> None:
    checkpoint = run.get("checkpoint")
    if not isinstance(checkpoint, dict):
        checkpoint = {}
        run["checkpoint"] = checkpoint
    checkpoint["research"] = state


def _whole(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def over_budget(state: dict[str, object]) -> str | None:
    elapsed = _elapsed_s(state.get("started_at"))
    if elapsed > _whole(state.get("max_wall_clock_s"), 120):
        return "max_wall_clock_s"
    if _whole(state.get("cost_micros")) > _whole(state.get("max_cost_micros")):
        return "max_cost_micros"
    if _whole(state.get("depth")) > _whole(state.get("max_depth"), 1):
        return "max_depth"
    return None


def _elapsed_s(started_at: object) -> float:
    """Seconds since the stored start. Any replica reads the same clock time."""
    try:
        started = datetime.fromisoformat(str(started_at))
    except ValueError:
        return 0.0
    return (utcnow() - started).total_seconds()


def max_steps(state: dict[str, object]) -> int:
    return _whole(state.get("max_steps"), _DEFAULTS["max_steps"])


def plan_queries(question: str, *, breadth: int) -> list[dict[str, str]]:
    """Deterministic queries. A model may replace these before the search step."""
    text = " ".join(question.split())
    if not text:
        return []
    pieces = [part.strip() for part in text.replace("?", ".").split(".") if part.strip()]
    if not pieces:
        pieces = [text]
    queries: list[dict[str, str]] = []
    for index, piece in enumerate(pieces[:breadth]):
        queries.append({"id": str(index + 1), "text": piece[:240], "status": "pending"})
    if not queries:
        queries.append({"id": "1", "text": text[:240], "status": "pending"})
    return queries


def run_subtask(store: Any, tenant_id: object, query: dict[str, str]) -> dict[str, object]:
    """Search, fetch and read one query. Safe to call again: the caller skips stored ids."""
    hits = search(store, tenant_id, query["text"], limit=3)
    sources: list[dict[str, object]] = []
    for hit in hits[:2]:
        url = str(hit.get("url") or "")
        if not url:
            continue
        page = fetch_page(store, url, tenant_id=tenant_id)
        text = str(page.get("text") or "")
        if not text:
            continue
        row = source_record(
            url=url,
            title=str(hit.get("title") or url),
            text=text,
            query_id=query["id"],
        )
        row["extractor"] = page.get("extractor") or ""
        sources.append(row)
    return {"query_id": query["id"], "sources": sources, "status": "done"}


def synthesise(question: str, sources: list[dict[str, object]]) -> str:
    """An extractive report. Every sentence quotes a stored page and cites it."""
    if not sources:
        return "No pages were fetched, so there is no cited report."
    lines = [f"Report on: {question}", ""]
    for index, source in enumerate(sources, start=1):
        text = str(source.get("text") or "").strip()
        sentence = text.split(". ")[0].strip()
        if sentence and not sentence.endswith("."):
            sentence = sentence + "."
        if len(sentence) < 12:
            continue
        body = sentence[:-1] if sentence.endswith(".") else sentence
        lines.append(f"{body} [{index}].")
    if len(lines) <= 2:
        return "The fetched pages did not contain a sentence that can be cited."
    lines.append("")
    lines.append("Sources")
    for index, source in enumerate(sources, start=1):
        lines.append(f"[{index}] {_named(source)}")
    return "\n".join(lines)


def _named(source: dict[str, object]) -> str:
    """How a report names a source: a web page by title and address, a document by title.

    A library address is for the product, not a reader. The citation under the report
    opens the document.
    """
    title = str(source.get("title") or "").strip()
    address = str(source.get("url") or "")
    if address.startswith(("http://", "https://")):
        return f"{title} {address}".strip()
    return title or "Document"


def advance(store: Any, run: dict[str, object], question: str) -> str:  # noqa: PLR0911
    """Move one phase. Return ``fanout``, ``model``, ``final`` or ``paused``."""
    if str(run.get("status") or "") == "cancelled":
        return "final"
    state = state_of(run, question)
    limit = over_budget(state)
    if limit is not None and state.get("phase") not in {"verify", "done"}:
        state["phase"] = "verify"
        state["budget_limit"] = limit
    phase = str(state.get("phase") or "plan")
    if phase == "plan":
        return _plan(state, run)
    if phase == "fanout":
        return "fanout"
    if phase == "awaiting":
        return _collect(state, run)
    if phase == "synthesize":
        report = synthesise(str(state.get("question") or question), _sources(state))
        if not _sources(state):
            # Nothing matched. The report says where it looked, so the person can act.
            report = f"{report} {scope(store, run.get('tenant_id'))}"
        state["report"] = report
        state["phase"] = "verify"
        save_state(run, state)
        return "model"
    if phase == "verify":
        return _verify(state, run)
    return "final"


def pending_subtasks(state: dict[str, object]) -> list[dict[str, str]]:
    done = state.get("subtasks")
    finished = set(done) if isinstance(done, dict) else set()
    queries = state.get("queries")
    if not isinstance(queries, list):
        return []
    pending: list[dict[str, str]] = []
    for query in queries:
        if not isinstance(query, dict):
            continue
        item_id = str(query.get("id") or "")
        if item_id and item_id not in finished:
            pending.append(
                {"id": item_id, "text": str(query.get("text") or ""), "status": "pending"}
            )
    return pending


def store_subtask(run: dict[str, object], query_id: str, result: dict[str, object]) -> None:
    state = state_of(run, str(result.get("question") or ""))
    subtasks = state.get("subtasks")
    book = dict(subtasks) if isinstance(subtasks, dict) else {}
    book[query_id] = result
    state["subtasks"] = book
    save_state(run, state)


def _plan(state: dict[str, object], run: dict[str, object]) -> str:
    breadth = _whole(state.get("max_breadth"), 4)
    queries = plan_queries(str(state.get("question") or ""), breadth=breadth)
    state["queries"] = queries
    state["depth"] = _whole(state.get("depth")) + 1
    state["phase"] = "fanout"
    save_state(run, state)
    return "fanout"


def _collect(state: dict[str, object], run: dict[str, object]) -> str:
    if pending_subtasks(state):
        return "fanout"
    subtasks = state.get("subtasks")
    sources: list[dict[str, object]] = []
    if isinstance(subtasks, dict):
        for result in subtasks.values():
            if not isinstance(result, dict):
                continue
            rows = result.get("sources")
            if isinstance(rows, list):
                sources.extend(row for row in rows if isinstance(row, dict))
    # Two queries often find the same passage, and two documents can hold the same text.
    # A source is listed once per address and once per text.
    listed: dict[str, dict[str, object]] = {}
    texts: set[str] = set()
    for row in sources:
        address = str(row.get("url"))
        text = str(row.get("sha256") or row.get("text") or "")
        if address in listed or (text and text in texts):
            continue
        listed[address] = row
        texts.add(text)
    sources = list(listed.values())
    state["sources"] = sources
    state["phase"] = "synthesize"
    save_state(run, state)
    return "model"


def _verify(state: dict[str, object], run: dict[str, object]) -> str:
    report = str(state.get("report") or "")
    cleaned, citations = verify_report(report, _sources(state))
    state["report"] = cleaned
    state["citations"] = citations
    state["phase"] = "done"
    save_state(run, state)
    run["research_report"] = cleaned
    return "final"


def _sources(state: dict[str, object]) -> list[dict[str, object]]:
    raw = state.get("sources")
    if not isinstance(raw, list):
        return []
    return [row for row in raw if isinstance(row, dict)]


def public_research(run: dict[str, object]) -> dict[str, object]:
    """CamelCase view. Page text stays; secrets do not."""
    state = {}
    checkpoint = run.get("checkpoint")
    if isinstance(checkpoint, dict) and isinstance(checkpoint.get("research"), dict):
        state = checkpoint["research"]
    sources = []
    for index, source in enumerate(_sources(state), start=1):
        sources.append(
            {
                "index": index,
                "url": source.get("url"),
                "title": source.get("title"),
                "sha256": source.get("sha256"),
                "fetchedAt": source.get("fetched_at"),
                "extractor": source.get("extractor") or "",
            }
        )
    return {
        "runId": str(run.get("id") or ""),
        "status": str(run.get("status") or ""),
        "phase": str(state.get("phase") or ""),
        "question": str(state.get("question") or ""),
        "report": str(state.get("report") or run.get("research_report") or ""),
        "sources": sources,
        "citations": state.get("citations") if isinstance(state.get("citations"), list) else [],
        "queries": state.get("queries") if isinstance(state.get("queries"), list) else [],
    }


def tenant_of(run: dict[str, object]) -> uuid.UUID | None:
    raw = run.get("tenant_id")
    if isinstance(raw, uuid.UUID):
        return raw
    try:
        return uuid.UUID(str(raw))
    except ValueError:
        return None
