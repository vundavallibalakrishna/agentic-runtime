"""Checks a tool server before it can be registered."""

from typing import TYPE_CHECKING

from ar_connector_sdk.context import ToolContext

if TYPE_CHECKING:
    from ar_connector_sdk.server import ToolServer


def conformance_errors(server: ToolServer) -> list[str]:
    """Return human-readable failures. An empty list means the server conforms."""
    errors: list[str] = []
    tools = server.listed()
    if not tools:
        errors.append("the server exposes no tools")
        return errors
    context = ToolContext(tenant_id="tenant", user_id="user", token="dev")  # noqa: S106
    for tool in tools:
        name = str(tool.get("name") or "")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            errors.append(f"{name} needs an object input schema")
        if not str(tool.get("description") or "").strip():
            errors.append(f"{name} needs a description")
        if not isinstance(tool.get("annotations"), dict):
            errors.append(f"{name} needs annotations")
        outcome = server.call(name, {}, context)
        if "text" not in outcome:
            errors.append(f"{name} did not return text")
    return errors
