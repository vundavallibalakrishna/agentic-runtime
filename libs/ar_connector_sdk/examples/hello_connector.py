"""Smallest conforming server."""

from ar_connector_sdk.context import ToolContext, annotations
from ar_connector_sdk.server import ToolServer


def build() -> ToolServer:
    server = ToolServer("hello")

    def ping(arguments: dict[str, object], _context: ToolContext) -> dict[str, object]:
        return {"text": f"pong {arguments.get('message', '')}".strip(), "is_error": False}

    server.tool(
        "ping",
        "Return the message.",
        {"type": "object", "properties": {"message": {"type": "string"}}},
        ping,
        annotations=annotations(read_only=True),
    )
    return server
