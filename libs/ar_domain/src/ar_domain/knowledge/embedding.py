"""Which model embeds a collection, and the call that does it.

A collection records the model that indexed it and the length of its vectors. Its
documents and every search of it are embedded by that same model, because vectors from
two models do not compare. Spec: docs/03-specs/10-knowledge-rag.md.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ar_common.errors import ConflictError
from ar_domain.models.embedding import (
    EmbeddingUnconfiguredError,
    ModelTarget,
    embed,
    embedding_model,
    registered_model,
    vector_size,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def choose_model(
    store: Any, tenant_id: object, alias: str, *, dimensions: int | None = None
) -> dict[str, object]:
    """The fields a collection records about the model ``alias`` points at.

    The model is asked for one vector, so a collection is never created against a model
    that does not answer, and the recorded length is the one it really returns.
    """
    target = embedding_model(store, tenant_id, alias)
    size = vector_size(target, dimensions=dimensions)
    fields: dict[str, object] = {
        "embedding_alias": alias,
        "embedding_model": target.name,
        "embedding_model_id": target.model_id,
        "dims": size,
    }
    if dimensions is not None:
        fields["request_dims"] = dimensions
    return fields


def collection_model(store: Any, row: dict[str, object]) -> ModelTarget:
    """The registered model that indexed this collection."""
    tenant_id = row.get("tenant_id")
    name = str(row.get("embedding_model") or "")
    target = registered_model(store, tenant_id, row.get("embedding_model_id"))
    if target is not None and name and target.name != name:
        target = None
    if target is None and name:
        target = _named(store, tenant_id, name)
    if target is None:
        raise EmbeddingUnconfiguredError(
            f"This collection was indexed with the embedding model {name or 'of an earlier setup'}"
            ", which is not registered. Register that model on the Models screen, or re-index "
            "the collection with the current embedding model."
        )
    return target


def collection_dims(row: dict[str, object]) -> int | None:
    """The length of this collection's vectors, including a row reloaded from Postgres."""
    return _whole(row.get("dims")) or _whole(_chunking(row).get("dims"))


def embed_for_collection(
    store: Any, collection: dict[str, object], texts: Sequence[str]
) -> list[list[float]]:
    """Embed with the collection's model, at the collection's vector length."""
    return embed(
        collection_model(store, collection),
        texts,
        dimensions=_whole(_chunking(collection).get("request_dims")),
        size=collection_dims(collection),
    )


def _named(store: Any, tenant_id: object, name: str) -> ModelTarget | None:
    for model in getattr(store, "models", {}).values():
        if not isinstance(model, dict) or model.get("kind") != "embedding":
            continue
        if str(model.get("upstream_model") or model.get("name") or "") != name:
            continue
        target = registered_model(store, tenant_id, model.get("id"))
        if target is not None:
            return target
    return None


def _chunking(row: dict[str, object]) -> dict[str, object]:
    raw = row.get("chunking")
    return raw if isinstance(raw, dict) else {}


def refuse_embedding_mismatch(store: Any, collections: list[dict[str, object]]) -> None:
    """HTTP 409 when a stored chunk was embedded by a different model than the collection."""
    documents = getattr(store, "knowledge_documents", None)
    chunks = getattr(store, "document_chunks", None)
    if not isinstance(documents, dict) or not isinstance(chunks, dict):
        return
    for collection in collections:
        expected = collection.get("embedding_model_id")
        if not expected:
            continue
        collection_id = collection.get("id")
        document_ids = {
            key
            for key, document in documents.items()
            if isinstance(document, dict) and document.get("collection_id") == collection_id
        }
        for chunk in chunks.values():
            if not isinstance(chunk, dict) or chunk.get("document_id") not in document_ids:
                continue
            recorded = chunk.get("embedding_model_id")
            if recorded and str(recorded) != str(expected):
                raise ConflictError(
                    "A passage was embedded with a different model than this collection. "
                    "Re-index the collection before searching it."
                )


def _whole(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value
