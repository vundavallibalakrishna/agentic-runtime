"""Rank tools by the deterministic embedding. Spec: docs/03-specs/08-tool-registry-mcp.md §9."""

from ar_domain.tools.logic import cosine, hash_embedding


def search_tools(
    tools: list[dict[str, object]], query: str, *, limit: int = 12
) -> list[dict[str, object]]:
    """Return the closest tools. A description that contains the query ranks higher."""
    vector = hash_embedding(query)
    scored: list[tuple[float, dict[str, object]]] = []
    for tool in tools:
        description = str(tool.get("description") or "")
        embedding = tool.get("embedding")
        current = embedding if isinstance(embedding, list) else hash_embedding(description)
        score = cosine(vector, [float(item) for item in current])
        if query.lower() in description.lower():
            score += 0.5
        scored.append((score, tool))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [tool for _score, tool in scored[:limit]]
