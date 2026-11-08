"""Rank tools against what was asked. Spec: docs/03-specs/08-tool-registry-mcp.md §4.

An agent with many tools is offered the ones closest to the request, and ``control.search``
finds a tool by description. Closeness is measured two ways and added up: by meaning, with
the tenant's embedding model, and by the words the request shares with the tool's name and
description. With no embedding model, or when it does not answer, the ranking is by words
alone, and the result says so. No vector is made up for a tool.

A search never waits for the catalogue to be embedded: a provider can take many seconds
over a few hundred descriptions. The vectors are made on a thread of their own, kept by
this process, and a search that arrives before they are ready is ranked by words.
"""

from __future__ import annotations

import hashlib
import re
import threading
import uuid
from typing import TYPE_CHECKING

from ar_common.logging import get_logger
from ar_common.time import utcnow
from ar_domain.models.embedding import (
    EmbeddingFailedError,
    EmbeddingUnconfiguredError,
    ModelTarget,
    embed,
    embedding_model,
)

if TYPE_CHECKING:
    from typing import Any

_log = get_logger("ar_domain.tools")
# A word is a run of letters and digits in any script.
_WORD = re.compile(r"[^\W_]+")
_WORDS_WEIGHT = 0.5
# How many tools a search returns, and how many an agent with many tools is offered,
# when its definition does not say (``tool_search.top_k``, 4 to 32).
DEFAULT_TOP_K = 12
BY_MEANING = "meaning_and_words"
BY_WORDS = "words"


def rank_tools(
    store: Any, tenant_id: object, query: str, tools: list[dict[str, object]]
) -> tuple[list[tuple[float, dict[str, object]]], str]:
    """Every tool with its score, best first, and how the ranking was made."""
    texts = [tool_text(tool) for tool in tools]
    words = [word_overlap(query, text) for text in texts]
    meaning = _by_meaning(store, tenant_id, query, texts) if query.strip() and tools else None
    if meaning is None:
        scores = words
        how = BY_WORDS
    else:
        scores = [
            close + _WORDS_WEIGHT * shared for close, shared in zip(meaning, words, strict=True)
        ]
        how = BY_MEANING
    order = sorted(
        range(len(tools)),
        key=lambda index: (-scores[index], str(tools[index].get("qualified_name") or "")),
    )
    return [(scores[index], tools[index]) for index in order], how


def tool_text(tool: dict[str, object]) -> str:
    """What a tool is matched on: its name and its description."""
    name = str(tool.get("qualified_name") or tool.get("name") or "")
    return f"{name}: {tool.get('description') or ''}".strip()


def word_overlap(query: str, text: str) -> float:
    """The share of the request's words found in the tool's name and description."""
    asked = set(_WORD.findall(query.casefold()))
    if not asked:
        return 0.0
    return len(asked & set(_WORD.findall(text.casefold()))) / len(asked)


def prepare_tools(
    store: Any, tenant_id: object, tools: list[dict[str, object]], *, wait: bool = False
) -> bool:
    """Embed the tools this process holds no vector for. True when every vector is held.

    The work runs on its own thread unless ``wait`` is set. A caller that waits (a
    script, a test) gets the provider's failure as ``EmbeddingFailedError``.
    """
    try:
        target = embedding_model(store, tenant_id)
    except EmbeddingUnconfiguredError:
        return False
    kept = _kept(store)
    missing = kept.missing(target, [tool_text(tool) for tool in tools])
    if not missing:
        return True
    if wait:
        kept.fill(target, missing, store=store, tenant_id=tenant_id)
        return True
    kept.start(target, missing, store=store, tenant_id=tenant_id)
    return False


def _by_meaning(store: Any, tenant_id: object, query: str, texts: list[str]) -> list[float] | None:
    """Cosine of the request and each tool, or None when it cannot be measured now."""
    try:
        target = embedding_model(store, tenant_id)
    except EmbeddingUnconfiguredError:
        return None
    kept = _kept(store)
    missing = kept.missing(target, texts)
    if missing:
        kept.start(target, missing, store=store, tenant_id=tenant_id)
        return None
    try:
        asked = embed(target, [query])[0]
    except EmbeddingFailedError as exc:
        _log.warning("tool_search_embedding_unavailable", code=exc.code.value)
        return None
    return [_cosine(asked, kept.vectors[_key(target, text)]) for text in texts]


class _Kept:
    """The tool vectors this process holds, by embedding model and tool text.

    A changed description or a changed model has a new key, so it is embedded again.
    Only the thread started here writes while a search reads; it touches nothing else
    of the store.
    """

    def __init__(self) -> None:
        self.vectors: dict[tuple[str, str], list[float]] = {}
        self.worker: threading.Thread | None = None
        self._lock = threading.Lock()

    def sync(self, store: Any) -> None:
        """Take in any vectors the store hydrated from the durable table (M39-T04a)."""
        book = getattr(store, "tool_search_vectors", None)
        if not isinstance(book, dict):
            return
        for row in book.values():
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("model_id") or "")
            text_hash = str(row.get("text_hash") or "")
            vector = row.get("vector")
            if model_id and text_hash and isinstance(vector, list):
                self.vectors.setdefault((model_id, text_hash), [float(value) for value in vector])

    def missing(self, target: ModelTarget, texts: list[str]) -> list[str]:
        """The texts with no vector from this model, each once, in order."""
        return [text for text in dict.fromkeys(texts) if _key(target, text) not in self.vectors]

    def fill(
        self, target: ModelTarget, texts: list[str], *, store: Any = None, tenant_id: object = None
    ) -> None:
        for text, vector in zip(texts, embed(target, texts), strict=True):
            self.vectors[_key(target, text)] = vector
            _record(store, tenant_id, target, text, vector)

    def start(
        self, target: ModelTarget, texts: list[str], *, store: Any = None, tenant_id: object = None
    ) -> None:
        """Embed ``texts`` on a thread, unless one is already at work.

        Whatever is still missing when it ends is picked up by the next search.
        """
        with self._lock:
            if self.worker is not None and self.worker.is_alive():
                return
            self.worker = threading.Thread(
                target=self._work,
                args=(target, texts, store, tenant_id),
                name="tool-vectors",
                daemon=True,
            )
            self.worker.start()

    def _work(self, target: ModelTarget, texts: list[str], store: Any, tenant_id: object) -> None:
        try:
            self.fill(target, texts, store=store, tenant_id=tenant_id)
        except EmbeddingFailedError as exc:
            _log.warning("tool_search_embedding_unavailable", code=exc.code.value)
        except Exception as exc:  # noqa: BLE001 - a thread of its own: nothing above it to tell
            _log.warning("tool_search_embedding_unavailable", error=type(exc).__name__)


def _record(
    store: Any, tenant_id: object, target: ModelTarget, text: str, vector: list[float]
) -> None:
    """Keep a computed vector in the durable table, so a later process does not re-embed it."""
    book = getattr(store, "tool_search_vectors", None)
    if not isinstance(book, dict) or not isinstance(tenant_id, uuid.UUID) or not vector:
        return
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    row_id = uuid.uuid5(uuid.NAMESPACE_URL, f"toolvec:{tenant_id}:{target.model_id}:{text_hash}")
    now = utcnow()
    book[row_id] = {
        "id": row_id,
        "tenant_id": tenant_id,
        "model_id": str(target.model_id),
        "text_hash": text_hash,
        "vector": list(vector),
        "created_at": now,
        "updated_at": now,
    }


def _kept(store: Any) -> _Kept:
    kept = getattr(store, "tool_vectors", None)
    if not isinstance(kept, _Kept):
        kept = _Kept()
        store.tool_vectors = kept
    kept.sync(store)
    return kept


def _key(target: ModelTarget, text: str) -> tuple[str, str]:
    return str(target.model_id), hashlib.sha256(text.encode()).hexdigest()


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm = (sum(a * a for a in left) ** 0.5) * (sum(b * b for b in right) ** 0.5)
    return dot / norm if norm else 0.0
