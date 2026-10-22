"""Deterministic vectors shared by fake-llm and the model gateway.

Knowledge embeddings call the gateway. The gateway's fake provider returns these
vectors, which match ``POST /v1/embeddings`` on fake-llm.
"""

import hashlib
import math
import random


def unit_vector(text: str, dimensions: int) -> list[float]:
    """SHA-256-seeded unit vector. Stable for the same text and dimension."""
    seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
    rng = random.Random(seed)  # noqa: S311 — deterministic embeddings, not secrets
    raw = [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]
    norm = math.sqrt(sum(item * item for item in raw)) or 1.0
    return [item / norm for item in raw]


def lexical_score(query: str, document: str) -> float:
    """Overlap of whitespace tokens, normalised by the query length."""
    left = set(query.lower().split())
    right = set(document.lower().split())
    if not left:
        return 0.0
    return len(left & right) / len(left)
