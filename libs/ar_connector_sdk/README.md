# ar-connector-sdk

Helper for a tool server that Agentic Runtime calls through `mcp-gateway`.

A server registers tools with a JSON Schema, a description and annotations. `ToolContext.from_headers` reads `x-ar-tenant-id`, `x-ar-user-id` and the bearer token. The token is the user's OAuth access token when the server uses `user_oauth`. Do not log it.

`conformance_errors` fails a server that has no tools, a missing object schema, or a handler that does not return text.

`DocumentSource` is the knowledge-connector interface. Search lands with the knowledge milestone; this package only defines the shape.

Examples:

- `examples/hello_connector.py` — one read-only ping tool.
- `examples/ticketing_server.py` — `create_ticket` and `list_tickets`. A call without a token fails. The first ticket id is `TCK-1001`.

```python
from ar_connector_sdk.context import ToolContext
from examples.ticketing_server import build

server = build()
context = ToolContext(tenant_id="tenant", user_id="user", token="access")
print(server.call("create_ticket", {"title": "Printer jammed"}, context)["text"])
```
