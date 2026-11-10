"""In-process research and context tools. The gateway is what calls them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.loop.context import read_output
from ar_domain.research.fetch import fetch_page
from ar_domain.research.providers import search

if TYPE_CHECKING:
    from typing import Any


def dispatch_research(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name == "search":
        return _search(store, arguments)
    if name == "fetch":
        return _fetch(store, arguments)
    return _error("not_found", "That research tool does not exist.")


def dispatch_context(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name != "retrieve":
        return _error("not_found", "That context tool does not exist.")
    output_id = str(arguments.get("output_id") or arguments.get("outputId") or "").strip()
    if not output_id:
        return _error("validation_failed", "output_id is required")
    run = _run(store, arguments.get("_run_id"))
    if run is None:
        return _error("not_found", "The run is not available.")
    text = read_output(run, output_id)
    if text is None:
        return _error("not_found", "That output id is not stored on this run.")
    return {"text": text, "structured": {"output_id": output_id, "text": text}, "is_error": False}


def _search(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    query = str(arguments.get("query") or "").strip()
    if not query:
        return _error("validation_failed", "query is required")
    limit = arguments.get("limit")
    count = limit if isinstance(limit, int) and not isinstance(limit, bool) else 4
    hits = search(store, arguments.get("_tenant_id"), query, limit=max(1, min(count, 8)))
    lines = [f"{row['title']}: {row['url']}" for row in hits]
    return {
        "text": "\n".join(lines) or "No results.",
        "structured": {"hits": hits, "provider": "configured"},
        "is_error": False,
    }


def _fetch(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    url = str(arguments.get("url") or "").strip()
    if not url:
        return _error("validation_failed", "url is required")
    if (
        not url.startswith("fixture://")
        and not url.startswith("https://")
        and not url.startswith("http://")
    ):
        return _error("validation_failed", "url must be an http or https URL")
    page = fetch_page(store, url, query=str(arguments.get("query") or ""))
    if page.get("error"):
        code = str(page.get("error") or "upstream_error")
        return _error(code, str(page.get("message") or code))
    text = str(page.get("text") or "")
    return {
        "text": text[:4000],
        "structured": {"text": text, "extractor": page.get("extractor") or "", "url": url},
        "is_error": False,
    }


def _run(store: Any, raw: object) -> dict[str, object] | None:
    runs = getattr(store, "runs", None)
    if not isinstance(runs, dict) or raw is None:
        return None
    found = runs.get(raw)
    if isinstance(found, dict):
        return found
    try:
        import uuid  # noqa: PLC0415

        found = runs.get(uuid.UUID(str(raw)))
    except ValueError:
        return None
    return found if isinstance(found, dict) else None


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
