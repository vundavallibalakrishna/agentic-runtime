"""Embeddings and rerank through the model gateway.

The gateway route and this module share ``embed_via_provider``. When
``AR_MODEL_GATEWAY_URL`` is set, callers POST ``/v1/embeddings``. When it is
empty, the dev API runs the same function the gateway serves (OQ-36). Fake
models return the vectors fake-llm publishes. Tool-catalogue hash vectors stay
on their own path (OQ-35).
"""

import os
from typing import TYPE_CHECKING

import httpx

from ar_common.vectors import lexical_score, unit_vector

if TYPE_CHECKING:
    from collections.abc import Sequence

_FAKE_EMBED = frozenset({"fake-embed", "embed"})
_FAKE_RERANK = frozenset({"fake-rerank", "rerank"})


def embed_via_provider(
    texts: Sequence[str], *, model: str, dimensions: int, provider_url: str = ""
) -> list[list[float]]:
    """Compute embeddings the way the gateway does for one provider."""
    if provider_url and model not in _FAKE_EMBED:
        return _http_embed(provider_url, texts, model=model, dimensions=dimensions)
    if model in _FAKE_EMBED or not provider_url:
        return [unit_vector(text, dimensions) for text in texts]
    return _http_embed(provider_url, texts, model=model, dimensions=dimensions)


def embed_texts(
    texts: Sequence[str], *, model: str = "fake-embed", dimensions: int = 1024
) -> list[list[float]]:
    """Embed through the gateway when a URL is configured."""
    gateway = os.environ.get("AR_MODEL_GATEWAY_URL", "").strip()
    if gateway:
        try:
            return _http_embed(gateway, texts, model=model, dimensions=dimensions)
        except httpx.HTTPError:
            if model not in _FAKE_EMBED:
                raise
    return embed_via_provider(texts, model=model, dimensions=dimensions)


def rerank(query: str, documents: Sequence[str], *, model: str = "fake-rerank") -> list[float]:
    """Return a 0..1 score per document, gateway first."""
    gateway = os.environ.get("AR_MODEL_GATEWAY_URL", "").strip()
    if gateway:
        try:
            return _http_rerank(gateway, query, documents, model=model)
        except httpx.HTTPError:
            if model not in _FAKE_RERANK:
                raise
    return [lexical_score(query, document) for document in documents]


def _http_embed(
    base_url: str, texts: Sequence[str], *, model: str, dimensions: int
) -> list[list[float]]:
    payload = {"model": model, "input": list(texts), "dimensions": dimensions}
    with httpx.Client(timeout=5.0) as client:
        response = client.post(f"{base_url.rstrip('/')}/v1/embeddings", json=payload)
        response.raise_for_status()
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return []
    ordered = sorted(
        data,
        key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0,
    )
    return [
        [float(value) for value in item["embedding"]]
        for item in ordered
        if isinstance(item, dict) and isinstance(item.get("embedding"), list)
    ]


def _http_rerank(base_url: str, query: str, documents: Sequence[str], *, model: str) -> list[float]:
    payload = {"model": model, "query": query, "documents": list(documents)}
    with httpx.Client(timeout=5.0) as client:
        response = client.post(f"{base_url.rstrip('/')}/v1/rerank", json=payload)
        response.raise_for_status()
    body = response.json()
    results = body.get("results") if isinstance(body, dict) else None
    scores = [0.0] * len(documents)
    if not isinstance(results, list):
        return scores
    for item in results:
        if not isinstance(item, dict):
            continue
        index = int(item.get("index", 0))
        if 0 <= index < len(scores):
            scores[index] = float(item.get("relevance_score", 0.0))
    return scores
