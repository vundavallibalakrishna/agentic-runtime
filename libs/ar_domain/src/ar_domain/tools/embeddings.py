"""Tool embeddings. The embed alias replaces the hash vector when the gateway is wired."""

from ar_domain.tools.logic import cosine, hash_embedding

DIMENSIONS = 1024

__all__ = ["DIMENSIONS", "cosine", "hash_embedding"]
