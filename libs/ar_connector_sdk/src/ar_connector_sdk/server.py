"""Small tool-server helper. Spec: docs/05-contracts/connector-sdk.md."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ar_connector_sdk.context import ToolContext

if TYPE_CHECKING:
    from typing import Any

Handler = Callable[[dict[str, object], ToolContext], dict[str, object]]


class ToolServer:
    """Register tools and answer tools/list and tools/call."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, dict[str, object]] = {}

    def tool(
        self,
        name: str,
        description: str,
        input_schema: dict[str, object],
        handler: Handler,
        *,
        annotations: dict[str, bool] | None = None,
    ) -> None:
        self._tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "annotations": annotations or {},
            "handler": handler,
        }

    def listed(self) -> list[dict[str, object]]:
        return [
            {
                "name": row["name"],
                "description": row["description"],
                "inputSchema": row["inputSchema"],
                "annotations": row["annotations"],
            }
            for row in self._tools.values()
        ]

    def call(
        self, name: str, arguments: dict[str, object], context: ToolContext
    ) -> dict[str, object]:
        row = self._tools.get(name)
        if row is None:
            return {"text": f"unknown tool {name}", "is_error": True}
        handler = row["handler"]
        if not callable(handler):
            return {"text": "tool has no handler", "is_error": True}
        try:
            result = handler(arguments, context)
        except Exception as exc:  # noqa: BLE001 — the server reports handler faults as tool errors
            return {"text": str(exc), "is_error": True}
        if not isinstance(result, dict) or "text" not in result:
            return {"text": "handler returned no text", "is_error": True}
        return result

    def handle(self, body: dict[str, Any], context: ToolContext) -> dict[str, object]:
        method = str(body.get("method") or "")
        request_id = body.get("id", 1)
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": self.listed()}}
        if method == "tools/call":
            raw_params = body.get("params")
            params = raw_params if isinstance(raw_params, dict) else {}
            raw_arguments = params.get("arguments")
            arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
            outcome = self.call(str(params.get("name") or ""), arguments, context)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": str(outcome.get("text") or "")}],
                    "isError": bool(outcome.get("is_error")),
                },
            }
        return {"jsonrpc": "2.0", "id": request_id, "error": {"message": "unknown method"}}
