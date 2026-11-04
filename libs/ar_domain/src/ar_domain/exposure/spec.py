"""The agent API OpenAPI document, filtered from the live application routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

_INFO = {
    "title": "Agentic Runtime Agent API",
    "version": "1.0.0",
    "description": (
        "Call a published agent with an agent API key. "
        "Create a conversation, send a message, stream the reply, attach a file, "
        "and read that run's trace. The same key authenticates the MCP server and A2A tasks. "
        "Send Idempotency-Key on a message so a retry returns the original run."
    ),
}


def agent_paths(document: dict[str, Any]) -> dict[str, Any]:
    """Keep the external surface. Internal `/api/v1` routes stay out of this document."""
    paths = document.get("paths")
    selected: dict[str, Any] = {}
    if isinstance(paths, dict):
        for path, item in paths.items():
            if path.startswith("/v1/") or path == "/.well-known/agent-card.json":
                selected[str(path)] = item
    return {
        "openapi": document.get("openapi", "3.1.0"),
        "info": _INFO,
        "paths": selected,
        "components": document.get("components")
        if isinstance(document.get("components"), dict)
        else {},
    }
