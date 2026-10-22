"""Qdrant filter builder. Spec: docs/03-specs/10-knowledge.md §8."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ar_domain.knowledge.store_types import HybridQuery

_BLOCK = 500


def physical_name(*, isolation_tier: str, tenant_short: str, model_key: str, dims: int) -> str:
    """Collection name for the tier. Shared installs share one physical collection."""
    key = "".join(char if char.isalnum() else "_" for char in model_key.lower()) or "model"
    if isolation_tier == "shared":
        return f"ar_kn_{key}_{dims}"
    cleaned = "".join(char if char.isalnum() else "" for char in tenant_short.lower())
    short = cleaned[:12] or "tenant"
    return f"ar_kn_t_{short}_{key}_{dims}"


def build_filter(query: HybridQuery) -> dict[str, object]:
    """Must-filters for tenant, version pairs, ACL and classification.

    Principal lists longer than 500 are split into ``should`` blocks.
    """
    if not query.principals or not query.allowed_classifications:
        raise ValueError("principals and classifications are required")
    pairs = [
        {
            "must": [
                {"key": "collection_id", "match": {"value": str(target.collection_id)}},
                {"key": "index_version", "match": {"value": target.index_version}},
            ]
        }
        for target in query.targets
    ]
    acl_blocks = [
        {"key": "acl", "match": {"any": query.principals[start : start + _BLOCK]}}
        for start in range(0, len(query.principals), _BLOCK)
    ]
    return {
        "must": [
            {"key": "tenant_id", "match": {"value": str(query.tenant_id)}},
            {"should": pairs},
            {"should": acl_blocks} if len(acl_blocks) > 1 else acl_blocks[0],
            {"key": "classification", "match": {"any": list(query.allowed_classifications)}},
        ]
    }


def hashed_sparse(text: str) -> tuple[list[int], list[float]]:
    """Sparse lexical vector used when the fastembed cache is empty.

    A rare token still occupies its own index, so lexical recall matches the
    conformance case. The baked ``Qdrant/bm25`` model replaces this when present.
    """
    weights: dict[int, float] = {}
    for token in text.lower().split():
        index = int.from_bytes(token.encode()[:8], "big") % (2**31 - 1)
        weights[index] = weights.get(index, 0.0) + 1.0
    indices = sorted(weights)
    return indices, [weights[index] for index in indices]
