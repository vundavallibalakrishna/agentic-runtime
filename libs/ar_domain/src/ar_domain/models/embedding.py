"""Embeddings and reranking with the models a tenant registered.

There is one path. An alias (``embed`` unless the caller names another) points at a model
of kind ``embedding``; the model belongs to a provider; the call goes to that provider's
``/embeddings``. Nothing here names a model, picks a provider the tenant did not choose,
or computes a vector in this process. With no model the caller is told how to set one.
Spec: docs/03-specs/04-model-gateway.md.
"""

from __future__ import annotations

import math
import os
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx

from ar_common.errors import ArError, ErrorCode
from ar_common.offload import blocking

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

EMBED_ALIAS = "embed"
RERANK_ALIAS = "rerank"
_BATCH = 32
_SIZE_CHECK = "vector size check"
NO_EMBEDDING_MODEL = (
    "No embedding model is set. An administrator sets one on the Models screen: "
    "add a model of kind embedding and point the embed alias at it."
)


class EmbeddingUnconfiguredError(ArError):
    """The tenant has not set the model this needs, or set one that does not fit."""

    def __init__(self, detail: str = NO_EMBEDDING_MODEL) -> None:
        super().__init__(ErrorCode.INVALID_STATE, detail)


class EmbeddingFailedError(ArError):
    """The tenant's embedding model did not answer, or answered without vectors."""

    def __init__(self, detail: str) -> None:
        super().__init__(ErrorCode.UPSTREAM_ERROR, detail)


# The bar a rerank model's scores must clear when the model sets none of its own.
DEFAULT_RERANK_FLOOR = 0.2


@dataclass(frozen=True, slots=True)
class ModelTarget:
    """A registered model and where its provider is reached."""

    model_id: uuid.UUID
    name: str
    label: str
    base_url: str
    api_key: str
    timeout_s: float
    dimensions: int | None
    # Provider-specific options stored on the model (``models.request_options``).
    request_options: dict[str, object] = field(default_factory=dict)


async def refresh_registry(store: Any) -> None:
    """Take up models that another process registered since this one last looked."""
    refresh = getattr(store, "refresh_models", None)
    if callable(refresh):
        await refresh()


def embedding_model(store: Any, tenant_id: object, alias: str = EMBED_ALIAS) -> ModelTarget:
    """The embedding model ``alias`` points at for this tenant."""
    target = _aliased(store, tenant_id, alias or EMBED_ALIAS, "embedding")
    if target is None:
        raise EmbeddingUnconfiguredError
    return target


def rerank_model(store: Any, tenant_id: object) -> ModelTarget | None:
    """The tenant's rerank model. Reranking is optional, so none is not an error."""
    return _aliased(store, tenant_id, RERANK_ALIAS, "rerank")


def registered_model(store: Any, tenant_id: object, model_id: object) -> ModelTarget | None:
    """The registered model with this id, when the tenant may still use it."""
    key = _as_uuid(model_id)
    if key is None:
        return None
    return _target(store, tenant_id, getattr(store, "models", {}).get(key))


def vector_size(target: ModelTarget, *, dimensions: int | None = None) -> int:
    """Ask the model for one vector and return its length."""
    return len(embed(target, [_SIZE_CHECK], dimensions=dimensions)[0])


def embed(
    target: ModelTarget,
    texts: Sequence[str],
    *,
    dimensions: int | None = None,
    size: int | None = None,
) -> list[list[float]]:
    """One vector for each text, from the provider of ``target``.

    ``dimensions`` asks a model that can shorten its vectors for that length; the
    model's own setting applies when the caller gives none. ``size`` is the length the
    caller can store: any other length is refused before a vector is kept.
    """
    rows = [text if isinstance(text, str) else str(text) for text in texts]
    if not rows:
        return []
    payload: dict[str, object] = {"model": target.name}
    asked = dimensions if dimensions is not None else target.dimensions
    if asked is not None:
        payload["dimensions"] = asked
    ordered: list[list[float] | None] = [None] * len(rows)
    try:
        with httpx.Client(timeout=_timeout(target)) as http:
            for start in range(0, len(rows), _BATCH):
                response = blocking(
                    http.post,
                    f"{target.base_url}/embeddings",
                    json={**payload, "input": rows[start : start + _BATCH]},
                    headers=_headers(target),
                )
                response.raise_for_status()
                _take(response.json(), ordered, start)
    except httpx.HTTPStatusError as exc:
        raise EmbeddingFailedError(
            f"The embedding model {target.label} refused the request "
            f"(HTTP {exc.response.status_code}). Test it on the Models screen."
        ) from exc
    except httpx.HTTPError as exc:
        raise EmbeddingFailedError(
            f"The embedding model {target.label} did not answer. Test it on the Models screen."
        ) from exc
    vectors = [vector for vector in ordered if vector]
    if len(vectors) != len(rows):
        raise EmbeddingFailedError(
            f"The embedding model {target.label} returned {len(vectors)} vectors "
            f"for {len(rows)} texts."
        )
    if size is not None and any(len(vector) != size for vector in vectors):
        raise EmbeddingUnconfiguredError(
            f"The embedding model {target.label} returns vectors of {len(vectors[0])} numbers "
            f"and this needs {size}. Set the model's embedding dimensions to {size} on the "
            "Models screen if the model supports it, or choose another embedding model."
        )
    return vectors


def rerank(target: ModelTarget, query: str, documents: Sequence[str]) -> list[float]:
    """A score from 0 to 1 for each document, from the tenant's rerank model."""
    docs = list(documents)
    if not docs:
        return []
    url, shape = rerank_route(target)
    payload: dict[str, object] = (
        {"queries": [query], "documents": docs}
        if shape == "queries"
        else {"model": target.name, "query": query, "documents": docs}
    )
    try:
        with httpx.Client(timeout=_timeout(target)) as http:
            response = blocking(http.post, url, json=payload, headers=_headers(target))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise EmbeddingFailedError(f"The rerank model {target.label} did not answer.") from exc
    scores = _scores(response.json(), len(docs))
    if scores is None:
        raise EmbeddingFailedError(f"The rerank model {target.label} returned no scores.")
    return _as_unit(scores)


def rerank_route(target: ModelTarget) -> tuple[str, str]:
    """Where a rerank model is called and how the request is shaped.

    Both are the model's own settings, ``request_options.rerank`` ``{path, body}``: a
    path under the provider's address (or a full URL), and ``query`` for the usual
    ``{model, query, documents}`` body or ``queries`` for ``{queries, documents}``. The
    defaults are ``/rerank`` and ``query``. No vendor's address is built into the code.
    """
    raw = target.request_options.get("rerank")
    section = raw if isinstance(raw, dict) else {}
    path = str(section.get("path") or "/rerank").strip()
    if path.startswith(("http://", "https://")):
        url = path
    else:
        url = f"{target.base_url.rstrip('/')}/{path.lstrip('/')}"
    shape = "queries" if str(section.get("body") or "").strip() == "queries" else "query"
    return url, shape


def rerank_floor(target: ModelTarget | None) -> float:
    """The lowest score at which a passage counts as answering the question.

    Each rerank model scores on its own scale, so the bar is the model's setting,
    ``request_options.rerank.min_score`` (0 to 1). Unset, it is ``DEFAULT_RERANK_FLOOR``.
    """
    if target is None:
        return DEFAULT_RERANK_FLOOR
    raw = target.request_options.get("rerank")
    section = raw if isinstance(raw, dict) else {}
    value = section.get("min_score")
    if isinstance(value, int | float) and 0.0 <= float(value) <= 1.0:
        return float(value)
    return DEFAULT_RERANK_FLOOR


def _aliased(store: Any, tenant_id: object, alias: str, kind: str) -> ModelTarget | None:
    """The tenant's own alias wins over one that belongs to no tenant."""
    own: dict[str, object] | None = None
    shared: dict[str, object] | None = None
    for row in getattr(store, "aliases", {}).values():
        if not isinstance(row, dict) or row.get("alias") != alias:
            continue
        if str(row.get("status") or "active") != "active":
            continue
        owner = row.get("tenant_id")
        if owner is None:
            shared = shared or row
        elif owner == tenant_id:
            own = own or row
    for row in (own, shared):
        if row is None:
            continue
        key = _as_uuid(row.get("primary_model_id"))
        model = getattr(store, "models", {}).get(key) if key is not None else None
        target = _target(store, tenant_id, model)
        if target is not None and isinstance(model, dict) and model.get("kind") == kind:
            return target
    return None


def _target(store: Any, tenant_id: object, model: object) -> ModelTarget | None:
    if not isinstance(model, dict) or not _usable(model, tenant_id):
        return None
    provider_id = _as_uuid(model.get("provider_id"))
    provider = getattr(store, "providers", {}).get(provider_id)
    if not isinstance(provider, dict) or not _usable(provider, tenant_id):
        return None
    base_url = str(provider.get("base_url") or "").rstrip("/")
    model_id = _as_uuid(model.get("id"))
    name = str(model.get("upstream_model") or model.get("name") or "")
    if not base_url or model_id is None or not name:
        return None
    key = provider.get("api_key")
    raw = model.get("embedding_dimensions")
    options = model.get("request_options")
    timeout = provider.get("timeout_s")
    return ModelTarget(
        model_id=model_id,
        name=name,
        label=str(model.get("name") or name),
        base_url=base_url,
        api_key=key if isinstance(key, str) else "",
        timeout_s=float(timeout) if isinstance(timeout, int | float) and timeout > 0 else 0.0,
        dimensions=raw if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0 else None,
        request_options=dict(options) if isinstance(options, dict) else {},
    )


def _usable(row: dict[str, object], tenant_id: object) -> bool:
    if str(row.get("status") or "active") != "active":
        return False
    owner = row.get("tenant_id")
    return owner is None or owner == tenant_id


def _timeout(target: ModelTarget) -> float:
    """``AR_EMBEDDING_TIMEOUT_S`` when set, then the provider's own timeout."""
    raw = os.environ.get("AR_EMBEDDING_TIMEOUT_S", "").strip()
    try:
        chosen = float(raw) if raw else target.timeout_s
    except ValueError:
        chosen = target.timeout_s
    return chosen if chosen > 0 else 60.0


def _headers(target: ModelTarget) -> dict[str, str]:
    return {"Authorization": f"Bearer {target.api_key}"} if target.api_key else {}


def _as_uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _take(body: object, ordered: list[list[float] | None], start: int) -> None:
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, list):
        return
    for position, item in enumerate(data):
        if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
            continue
        index = item.get("index")
        slot = start + (index if isinstance(index, int) else position)
        if 0 <= slot < len(ordered):
            ordered[slot] = [float(value) for value in item["embedding"]]


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
