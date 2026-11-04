"""Real embeddings and reranking for knowledge.

The default model is ``BAAI/bge-m3`` (1024 dimensions). The same id runs on a
self-hosted OpenAI-compatible server (text-embeddings-inference or vLLM) and on
a hosted endpoint such as DeepInfra. A registered model with ``kind=embedding``
overrides the default. ``embed`` and ``fake-embed`` are not called on this path.
Unit tests inject ``store.embed_client``.
"""

from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

from ar_common.errors import ArError, ErrorCode
from ar_common.vectors import lexical_score

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-m3"
DEFAULT_EMBEDDING_DIMS = 1024
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
FAKE_EMBEDDINGS = frozenset({"fake-embed", "embed", "fake-rerank", "rerank"})
_BATCH = 32


@dataclass(frozen=True)
class LiveTarget:
    """Where a real embedding or rerank call is sent."""

    model: str
    dims: int
    base_url: str
    api_key: str
    rerank_model: str


def is_fake_embedding(model: str) -> bool:
    """True for the seeded aliases that return hash vectors."""
    return model.strip().lower() in FAKE_EMBEDDINGS


def collection_embedding(row: dict[str, object]) -> tuple[str, int]:
    """Model id and dimensions, including a row reloaded from Postgres."""
    chunking = row.get("chunking") if isinstance(row.get("chunking"), dict) else {}
    model = str(row.get("embedding_model") or "")
    if is_fake_embedding(model) or not model:
        stored = str(chunking.get("embedding_model") or "") if isinstance(chunking, dict) else ""
        alias = str(row.get("embedding_alias") or "")
        if stored and not is_fake_embedding(stored):
            model = stored
        elif alias and not is_fake_embedding(alias):
            model = alias
        else:
            model = "fake-embed"
    dims = row.get("dims")
    if not isinstance(dims, int):
        raw = chunking.get("dims") if isinstance(chunking, dict) else None
        dims = raw if isinstance(raw, int) else DEFAULT_EMBEDDING_DIMS
    return model, dims


async def load_provider_keys(store: Any) -> None:
    """Put encrypted provider keys back on the row before an embedding call."""
    engine = getattr(store, "durable_engine", None)
    if engine is None:
        return
    from ar_domain.models.registry import read_api_key  # noqa: PLC0415

    for row in getattr(store, "providers", {}).values():
        if not isinstance(row, dict) or row.get("api_key"):
            continue
        provider_id = row.get("id")
        if not isinstance(provider_id, uuid.UUID):
            try:
                provider_id = uuid.UUID(str(provider_id))
            except ValueError:
                continue
        try:
            key = await read_api_key(engine, provider_id)
        except Exception:  # noqa: BLE001 — a locked key ring leaves this provider unused
            key = ""
        if key:
            row["api_key"] = key
            row["has_api_key"] = True


def resolve_embedding(store: Any, tenant_id: object) -> LiveTarget | None:
    """A non-fake provider, or None when the process only has fake-llm."""
    providers = _real_providers(store, tenant_id)
    if not providers:
        return None
    by_id = {str(row.get("id")): row for row in providers}
    chosen: tuple[dict[str, object], str, int] | None = None
    for model in getattr(store, "models", {}).values():
        if not isinstance(model, dict) or str(model.get("kind") or "") != "embedding":
            continue
        upstream = str(model.get("upstream_model") or "")
        if is_fake_embedding(upstream):
            continue
        provider = by_id.get(str(model.get("provider_id")))
        if provider is None:
            continue
        raw_dims = model.get("embedding_dimensions") or model.get("dims")
        dims = raw_dims if isinstance(raw_dims, int) and raw_dims > 0 else DEFAULT_EMBEDDING_DIMS
        chosen = (provider, upstream, dims)
        break
    provider = chosen[0] if chosen else providers[0]
    model_name = chosen[1] if chosen else DEFAULT_EMBEDDING_MODEL
    dims = chosen[2] if chosen else DEFAULT_EMBEDDING_DIMS
    rerank = _rerank_model(store, by_id)
    return LiveTarget(
        model=model_name,
        dims=dims,
        base_url=str(provider.get("base_url") or "").rstrip("/"),
        api_key=str(provider.get("api_key") or ""),
        rerank_model=rerank,
    )


def embed_for_collection(
    store: Any, collection: dict[str, object], texts: Sequence[str]
) -> list[list[float]]:
    """Embed with the collection's model. Fake aliases stay on the test helper."""
    model, dims = collection_embedding(collection)
    if is_fake_embedding(model):
        from ar_domain.knowledge.embedder import embed_texts  # noqa: PLC0415

        return embed_texts(texts, model="fake-embed", dimensions=dims)
    return embed_live(
        store,
        collection.get("tenant_id"),
        texts,
        model=model,
        dimensions=dims,
    )


def embed_live(
    store: Any,
    tenant_id: object,
    texts: Sequence[str],
    *,
    model: str,
    dimensions: int,
) -> list[list[float]]:
    """Call the provider. A missing provider is an error, not a hash vector."""
    rows = [text if isinstance(text, str) else str(text) for text in texts]
    if not rows:
        return []
    client = getattr(store, "embed_client", None)
    if callable(client):
        vectors = client(rows)
        if not isinstance(vectors, list) or len(vectors) != len(rows):
            raise EmbeddingUnconfiguredError("the test embedder returned the wrong shape")
        return vectors
    if is_fake_embedding(model):
        raise EmbeddingUnconfiguredError("the fake embedding alias is not on the live path")
    target = resolve_embedding(store, tenant_id)
    if target is None or not target.base_url:
        raise EmbeddingUnconfiguredError("no embedding provider is configured")
    headers = {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}
    ordered: list[list[float] | None] = [None] * len(rows)
    url = f"{target.base_url}/embeddings"
    timeout = float(os.environ.get("AR_EMBEDDING_TIMEOUT_S", "60"))
    try:
        with httpx.Client(timeout=timeout) as http:
            for start in range(0, len(rows), _BATCH):
                batch = rows[start : start + _BATCH]
                response = http.post(
                    url,
                    json={"model": model, "input": batch, "dimensions": dimensions},
                    headers=headers,
                )
                response.raise_for_status()
                _take(response.json(), ordered, start)
    except httpx.HTTPError as exc:
        raise EmbeddingUnconfiguredError("the embedding provider did not answer") from exc
    if any(vector is None for vector in ordered):
        raise EmbeddingUnconfiguredError("the embedding provider returned no vectors")
    return [vector for vector in ordered if vector is not None]


def rerank_live(
    store: Any,
    tenant_id: object,
    query: str,
    documents: Sequence[str],
    *,
    model: str,
) -> list[float]:
    """Rerank candidates. A provider miss falls back to token overlap."""
    docs = list(documents)
    if not docs:
        return []
    client = getattr(store, "rerank_client", None)
    if callable(client):
        scores = client(query, docs)
        if isinstance(scores, list) and len(scores) == len(docs):
            return [float(score) for score in scores]
    target = resolve_embedding(store, tenant_id)
    rerank_model = model if model and not is_fake_embedding(model) else DEFAULT_RERANK_MODEL
    if target is not None and target.rerank_model and target.rerank_model != DEFAULT_RERANK_MODEL:
        rerank_model = target.rerank_model
    if target is not None and target.base_url:
        remote = _remote_rerank(target, query, docs, rerank_model)
        if remote is not None:
            return remote
    return [lexical_score(query, document) for document in docs]


class EmbeddingUnconfiguredError(ArError):
    """The live path refused to invent vectors."""

    def __init__(self, detail: str) -> None:
        super().__init__(ErrorCode.UNAVAILABLE, detail)


def _real_providers(store: Any, tenant_id: object) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for row in getattr(store, "providers", {}).values():
        if not isinstance(row, dict) or str(row.get("kind") or "") == "fake":
            continue
        owner = row.get("tenant_id")
        if owner is not None and owner != tenant_id:
            continue
        base = str(row.get("base_url") or "")
        key = row.get("api_key")
        if not base or not isinstance(key, str) or not key:
            continue
        found.append(row)
    return found


def _rerank_model(store: Any, providers: dict[str, dict[str, object]]) -> str:
    for model in getattr(store, "models", {}).values():
        if not isinstance(model, dict) or str(model.get("kind") or "") != "rerank":
            continue
        upstream = str(model.get("upstream_model") or "")
        if is_fake_embedding(upstream):
            continue
        if str(model.get("provider_id")) in providers:
            return upstream
    return DEFAULT_RERANK_MODEL


def _take(body: object, ordered: list[list[float] | None], start: int) -> None:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
            continue
        index = int(item.get("index", 0))
        slot = start + index
        if 0 <= slot < len(ordered):
            ordered[slot] = [float(value) for value in item["embedding"]]


def _remote_rerank(
    target: LiveTarget, query: str, documents: list[str], model: str
) -> list[float] | None:
    headers = {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}
    openai_url = f"{target.base_url}/rerank"
    inference = _inference_url(target.base_url, model)
    payloads = (
        (openai_url, {"model": model, "query": query, "documents": documents}),
        (inference, {"queries": [query], "documents": documents}),
    )
    try:
        with httpx.Client(timeout=30.0) as http:
            for url, payload in payloads:
                if not url:
                    continue
                response = http.post(url, json=payload, headers=headers)
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                scores = _scores(response.json(), len(documents))
                if scores is not None:
                    return _as_unit(scores)
    except httpx.HTTPError:
        return None
    return None


def _inference_url(base_url: str, model: str) -> str:
    marker = "/openai"
    if base_url.endswith(marker):
        return f"{base_url[: -len(marker)]}/inference/{model}"
    return ""


def _scores(body: object, count: int) -> list[float] | None:
    if not isinstance(body, dict):
        return None
    results = body.get("results")
    if isinstance(results, list):
        scores = [0.0] * count
        for item in results:
            if not isinstance(item, dict):
                continue
            index = int(item.get("index", 0))
            if 0 <= index < count:
                raw = item.get("relevance_score", item.get("score", 0.0))
                scores[index] = float(raw) if isinstance(raw, int | float) else 0.0
        return scores
    raw_scores = body.get("scores")
    if isinstance(raw_scores, list) and raw_scores and isinstance(raw_scores[0], list):
        raw_scores = raw_scores[0]
    if isinstance(raw_scores, list) and len(raw_scores) == count:
        return [float(item) if isinstance(item, int | float) else 0.0 for item in raw_scores]
    return None


def _as_unit(scores: list[float]) -> list[float]:
    if any(score < 0.0 or score > 1.0 for score in scores):
        return [1.0 / (1.0 + math.exp(-score)) for score in scores]
    return scores
