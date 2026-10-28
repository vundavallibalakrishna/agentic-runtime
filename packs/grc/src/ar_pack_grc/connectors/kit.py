"""Cursor loops, backoff and evidence capture for GRC connectors.

Spec: docs/10-grc-pack/connectors.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, cast

import orjson
from pydantic import JsonValue

from ar_common.jcs import args_hash as canonical_hash
from ar_common.settings import get_settings
from ar_domain.records.vault import EvidenceBook

if TYPE_CHECKING:
    from collections.abc import Callable

    from ar_domain.agents.access import Actor

READ_METHODS = frozenset({"GET", "HEAD"})
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CURSOR_KEYS = ("nextCursor", "NextToken", "nextPageToken", "next_cursor")


class Transport(Protocol):
    def exchange(self, method: str, path: str, query: dict[str, str]) -> tuple[int, dict[str, Any]]:
        """Return the HTTP status and a JSON object. The kit retries status 429."""


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    risk: str
    method: str
    path: str


@dataclass(frozen=True)
class HttpCall:
    method: str
    path: str
    query: dict[str, str]
    status: int


class MemoryTransport:
    """Replay a recorded list of HTTP pages, including 429s."""

    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.pages = pages
        self.calls: list[HttpCall] = []
        self._index = 0

    def exchange(self, method: str, path: str, query: dict[str, str]) -> tuple[int, dict[str, Any]]:
        page = self.pages[min(self._index, max(len(self.pages) - 1, 0))]
        self._index += 1
        status = int(page.get("status") or 200)
        body = page.get("body")
        payload = {str(key): value for key, value in body.items()} if isinstance(body, dict) else {}
        self.calls.append(HttpCall(method=method, path=path, query=dict(query), status=status))
        return status, payload


def request_hash(method: str, path: str, query: dict[str, str]) -> str:
    """SHA-256 of the canonical request. Key order does not change the digest."""
    document = {
        "method": method,
        "path": path,
        "query": {key: query[key] for key in sorted(query)},
    }
    return canonical_hash(cast("JsonValue", document))


def _noop(_seconds: float) -> None:
    return None


class ConnectorKit:
    """Follow a remote cursor, back off on 429, and capture one item per kept page."""

    def __init__(
        self,
        store: Any,
        actor: Actor,
        source_system: str,
        transport: Transport,
        *,
        max_pages: int | None = None,
        sleeper: Callable[[float], None] | None = None,
        provenance: dict[str, str] | None = None,
    ) -> None:
        self.store = store
        self.actor = actor
        self.source_system = source_system
        self.transport = transport
        limit = get_settings().grc_connector_max_pages if max_pages is None else max_pages
        self.max_pages = max(0, limit)
        self.sleeper = sleeper or _noop
        self.provenance = dict(provenance or {})
        self.delays: list[float] = []

    def collect(self, tool: Tool, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        if tool.method not in READ_METHODS:
            return []
        kept: list[dict[str, Any]] = []
        cursor = ""
        page = 0
        base = dict(query or {})
        while page < self.max_pages:
            query_now = dict(base)
            if cursor:
                query_now["cursor"] = cursor
            status, body = self._exchange(tool.method, tool.path, query_now)
            if status >= 400:
                break
            page += 1
            digest = request_hash(tool.method, tool.path, query_now)
            kept.append(self._capture(tool, body, digest, page))
            cursor = _cursor(body)
            if not cursor:
                break
        return kept

    def submit(self, tool: Tool, query: dict[str, str] | None = None) -> dict[str, Any]:
        """One write request. The caller has already passed approval."""
        status, body = self._exchange(tool.method, tool.path, dict(query or {}))
        return {"status": status, "body": body}

    def _exchange(
        self, method: str, path: str, query: dict[str, str]
    ) -> tuple[int, dict[str, Any]]:
        delay = 0.05
        status = 429
        body: dict[str, Any] = {}
        for _attempt in range(6):
            status, body = self.transport.exchange(method, path, query)
            if status != 429:
                return status, body
            self.delays.append(delay)
            self.sleeper(delay)
            delay *= 2
        return status, body

    def _capture(self, tool: Tool, body: dict[str, Any], digest: str, page: int) -> dict[str, Any]:
        provenance = {
            "request_sha256": digest,
            "tool": tool.name,
            "page": str(page),
            **self.provenance,
        }
        return EvidenceBook(self.store).capture(
            self.actor,
            {
                "media_type": "application/json",
                "source_system": self.source_system,
                "collection_method": "tool_call",
                "provenance": provenance,
            },
            orjson.dumps(body),
            idempotency_key=f"{self.source_system}:{tool.name}:{digest}:{page}",
        )


def _cursor(body: dict[str, Any]) -> str:
    for key in _CURSOR_KEYS:
        value = body.get(key)
        if isinstance(value, str) and value:
            return value
    return ""
