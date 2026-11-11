"""Search and fetch go through the tool gateway, same as every other tool."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.research.engine import run_subtask
from ar_domain.tools.gateway_client import execute_tool

if TYPE_CHECKING:
    from typing import Any


def subtask_via_gateway(
    store: Any, run: dict[str, object], query: dict[str, str]
) -> dict[str, object]:
    """Prefer gateway tools. Fall back to the in-process provider when they are absent."""
    search_id = _version_id(store, "research.search")
    fetch_id = _version_id(store, "research.fetch")
    if search_id is None or fetch_id is None:
        return run_subtask(store, run.get("tenant_id"), query)
    found = execute_tool(
        store,
        _request(
            run,
            search_id,
            {"query": query["text"], "limit": 3},
            query_id=query["id"],
            call_index=0,
            label="search",
        ),
    )
    hits = _hits(found)
    sources: list[dict[str, object]] = []
    for index, hit in enumerate(hits[:2], start=1):
        url = str(hit.get("url") or "")
        if not url:
            continue
        page = execute_tool(
            store,
            _request(
                run,
                fetch_id,
                {"url": url, "query": query["text"]},
                query_id=query["id"],
                call_index=index,
                label=url,
            ),
        )
        text = str(page.get("result_preview") or "")
        structured = page.get("structured")
        if isinstance(structured, dict) and isinstance(structured.get("text"), str):
            text = structured["text"]
        if page.get("status") != "succeeded" or not text:
            continue
        from ar_domain.research.citations import source_record  # noqa: PLC0415

        row = source_record(
            url=url,
            title=str(hit.get("title") or url),
            text=text,
            query_id=query["id"],
        )
        if isinstance(structured, dict):
            row["extractor"] = str(structured.get("extractor") or "")
        sources.append(row)
    return {"query_id": query["id"], "sources": sources, "status": "done"}


def _version_id(store: Any, qualified: str) -> uuid.UUID | None:
    versions = getattr(store, "tool_versions", None)
    if not isinstance(versions, dict):
        return None
    for row in versions.values():
        if isinstance(row, dict) and row.get("qualified_name") == qualified:
            raw = row.get("id")
            if isinstance(raw, uuid.UUID):
                return raw
            try:
                return uuid.UUID(str(raw))
            except ValueError:
                return None
    return None


def _request(
    run: dict[str, object],
    version_id: uuid.UUID,
    arguments: dict[str, object],
    *,
    query_id: str,
    call_index: int,
    label: str,
) -> dict[str, object]:
    """One search or fetch. The key is the run, the query and this call, not the tool version."""
    return {
        "tenant_id": run.get("tenant_id"),
        "user_id": run.get("user_id"),
        "run_id": run.get("id"),
        "agent_id": run.get("agent_id"),
        "agent_version_id": run.get("agent_version_id"),
        "tool_version_id": version_id,
        "arguments": arguments,
        "step": "research",
        "query_id": query_id,
        "call_index": call_index,
        "model_call_id": f"research:{query_id}:{call_index}:{label}",
    }


def _hits(result: dict[str, object]) -> list[dict[str, object]]:
    structured = result.get("structured")
    if isinstance(structured, dict) and isinstance(structured.get("hits"), list):
        return [row for row in structured["hits"] if isinstance(row, dict)]
    return []
