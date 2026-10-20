"""RetrievalStore port. The pgvector and qdrant adapters land in M7."""


def backend_name() -> str:
    """Return the default retrieval backend."""
    return "pgvector"
