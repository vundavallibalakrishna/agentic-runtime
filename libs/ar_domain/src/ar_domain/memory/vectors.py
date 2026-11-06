"""The vectors memory stores and compares. Spec: docs/03-specs/11-memory.md §3.

A fact is embedded by the model the tenant's ``embed`` alias points at, and records
which model that was. Two vectors are compared only when one model wrote both. A fact
whose vector came from an earlier model is still matched by the words it shares with
the question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.logging import get_logger
from ar_domain.memory.logic import dimensions
from ar_domain.models.embedding import (
    EmbeddingFailedError,
    EmbeddingUnconfiguredError,
    ModelTarget,
    embed,
    embedding_model,
)

if TYPE_CHECKING:
    import uuid
    from typing import Any

_log = get_logger("ar_domain.memory")


class MemoryVectors:
    """Embeds memory text for one tenant with that tenant's embedding model."""

    def __init__(self, store: Any, tenant_id: uuid.UUID) -> None:
        self._store = store
        self._tenant_id = tenant_id
        self._made: dict[str, list[float]] = {}

    def model_id(self) -> uuid.UUID | None:
        """The embedding model in use, or None when the tenant has not set one."""
        target = self._model()
        return target.model_id if target is not None else None

    def for_write(self, text: str) -> list[float]:
        """The vector stored with a fact. A fact is not saved without one."""
        target = embedding_model(self._store, self._tenant_id)
        return self._embed(target, text)

    def for_read(self, text: str) -> list[float]:
        """The vector of a question. Empty when no model can give one: words still match."""
        target = self._model()
        if target is None or not text:
            return []
        try:
            return self._embed(target, text)
        except (EmbeddingFailedError, EmbeddingUnconfiguredError) as exc:
            _log.warning("memory_embedding_unavailable", code=exc.code.value)
            return []

    def of(self, row: dict[str, object]) -> list[float]:
        """A fact's vector when the model in use wrote it, and nothing otherwise."""
        stored = row.get("embedding")
        model_id = self.model_id()
        if model_id is None or not isinstance(stored, list):
            return []
        if str(row.get("embedding_model_id") or "") != str(model_id):
            return []
        return [float(item) for item in stored]

    def _model(self) -> ModelTarget | None:
        try:
            return embedding_model(self._store, self._tenant_id)
        except EmbeddingUnconfiguredError:
            return None

    def _embed(self, target: ModelTarget, text: str) -> list[float]:
        key = f"{target.model_id}:{text}"
        if key not in self._made:
            self._made[key] = embed(target, [text or " "], size=dimensions())[0]
        return self._made[key]


def reembed(store: Any, tenant_id: uuid.UUID, *, batch: int = 32) -> int:
    """Embed again every fact that the tenant's current embedding model did not write.

    Run after the ``embed`` alias is pointed at another model. Returns how many facts
    were embedded.
    """
    target = embedding_model(store, tenant_id)
    stale = [
        row
        for row in store.memory_facts.values()
        if row.get("tenant_id") == tenant_id
        and str(row.get("embedding_model_id") or "") != str(target.model_id)
    ]
    for start in range(0, len(stale), batch):
        rows = stale[start : start + batch]
        texts = [str(row.get("content") or " ") for row in rows]
        for row, vector in zip(rows, embed(target, texts, size=dimensions()), strict=True):
            row["embedding"] = vector
            row["embedding_model_id"] = target.model_id
            store.memory_facts[row["id"]] = row
    return len(stale)
