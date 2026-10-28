"""Pluggable web search. A missing provider returns a configuration error, never invented hits."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Protocol, cast

import httpx

if TYPE_CHECKING:
    from typing import Any

_INSTRUCTIONS = (
    "Web search is not configured. Set AR_SEARCH_PROVIDER to brave or tavily and "
    "AR_SEARCH_API_KEY to that provider's key, or set the tenant search provider and "
    "a secret name that holds the key. No results were invented."
)


class SearchProvider(Protocol):
    """One search backend."""

    def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
        """Return title, url and snippet rows."""


class SearchUnavailableError(RuntimeError):
    """The tenant has no working search provider."""

    def __init__(self, message: str = _INSTRUCTIONS) -> None:
        super().__init__(message)


def provider_for(store: Any, tenant_id: object) -> SearchProvider:
    """Resolve the configured provider. Tests may set ``store.search_provider``."""
    override = getattr(store, "search_provider", None)
    if override is not None and callable(getattr(override, "search", None)):
        return cast("SearchProvider", override)
    name, key = _configured(store, tenant_id)
    if name == "brave" and key:
        return BraveSearch(key)
    if name == "tavily" and key:
        return TavilySearch(key)
    raise SearchUnavailableError


def _configured(store: Any, tenant_id: object) -> tuple[str, str]:
    settings = _tenant_search(store, tenant_id)
    name = str(settings.get("provider") or os.environ.get("AR_SEARCH_PROVIDER") or "none")
    name = name.strip().lower()
    secret_name = str(settings.get("secret_name") or "")
    key = _secret(store, tenant_id, secret_name) if secret_name else ""
    if not key:
        key = os.environ.get("AR_SEARCH_API_KEY", "")
    return name, key


def _tenant_search(store: Any, tenant_id: object) -> dict[str, object]:
    book = getattr(store, "tenant_settings", None)
    if not isinstance(book, dict):
        return {}
    row = book.get(tenant_id)
    if not isinstance(row, dict):
        return {}
    search = row.get("search")
    return search if isinstance(search, dict) else {}


def _secret(store: Any, tenant_id: object, name: str) -> str:
    book = getattr(store, "named_secrets", None)
    if not isinstance(book, dict) or not name:
        return ""
    value = book.get((str(tenant_id), name))
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    return ""


class BraveSearch:
    """Brave web search. The subscription token is a request header, not a result."""

    def __init__(self, key: str) -> None:
        self._key = key

    def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
        response = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": max(1, min(limit, 10))},
            headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        web = payload.get("web") if isinstance(payload, dict) else None
        results = web.get("results") if isinstance(web, dict) else None
        return _rows(results)


class TavilySearch:
    """Tavily search. The key stays in the request body and is not returned."""

    def __init__(self, key: str) -> None:
        self._key = key

    def search(self, query: str, *, limit: int) -> list[dict[str, str]]:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self._key,
                "query": query,
                "max_results": max(1, min(limit, 10)),
                "include_answer": False,
            },
            timeout=15.0,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") if isinstance(payload, dict) else None
        return _rows(results)


def _rows(results: object) -> list[dict[str, str]]:
    if not isinstance(results, list):
        return []
    rows: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        url = str(item.get("url") or "")
        snippet = str(item.get("snippet") or item.get("content") or "")
        if title or url:
            rows.append({"title": title, "url": url, "snippet": snippet[:500]})
    return rows
