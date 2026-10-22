"""Example ticketing server used by the tools demo and conformance tests."""

from ar_connector_sdk.context import ContextError, ToolContext, annotations
from ar_connector_sdk.server import ToolServer

_TICKETS: list[dict[str, str]] = []


def build() -> ToolServer:
    server = ToolServer("ticketing")

    def create_ticket(arguments: dict[str, object], context: ToolContext) -> dict[str, object]:
        if not context.token:
            raise ContextError("an oauth token is required")
        title = str(arguments.get("title") or "").strip()
        if not title:
            return {"text": "title is required", "is_error": True}
        number = 1000 + len(_TICKETS) + 1
        row = {"id": f"TCK-{number}", "title": title, "user": context.user_id}
        _TICKETS.append(row)
        return {"text": f"Filed ticket {row['id']}.", "is_error": False}

    def list_tickets(_arguments: dict[str, object], context: ToolContext) -> dict[str, object]:
        if not context.token:
            raise ContextError("an oauth token is required")
        lines = [f"{row['id']}: {row['title']}" for row in _TICKETS]
        return {"text": "\n".join(lines) or "No tickets yet.", "is_error": False}

    server.tool(
        "create_ticket",
        "File a ticket.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
        create_ticket,
        annotations=annotations(read_only=False),
    )
    server.tool(
        "list_tickets",
        "List tickets the user filed.",
        {"type": "object", "properties": {}},
        list_tickets,
        annotations=annotations(read_only=True),
    )
    return server
