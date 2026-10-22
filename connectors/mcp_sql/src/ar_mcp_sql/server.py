"""Read-only SQL tools. Spec: docs/03-specs/08-tool-registry-mcp.md §10."""

from typing import TYPE_CHECKING

from ar_mcp_sql.guard import SqlRejected, check_sql

if TYPE_CHECKING:
    from typing import Any

_ORDERS = (
    {"id": 1, "sku": "paper", "quantity": 4},
    {"id": 2, "sku": "ink", "quantity": 2},
    {"id": 3, "sku": "stapler", "quantity": 1},
)


def tools() -> list[dict[str, object]]:
    return [
        {
            "name": "list_tables",
            "description": "List allowlisted tables.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "describe_table",
            "description": "Describe one allowlisted table.",
            "inputSchema": {
                "type": "object",
                "properties": {"table": {"type": "string"}},
                "required": ["table"],
            },
        },
        {
            "name": "run_query",
            "description": "Run one read-only select.",
            "inputSchema": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    ]


def call(
    name: str, arguments: dict[str, object], *, allow_tables: set[str] | None = None
) -> dict[str, object]:
    """Execute one tool against the in-process orders table."""
    allow = allow_tables or {"public.orders"}
    if name.endswith("list_tables"):
        return {"text": "\n".join(sorted(allow)), "is_error": False}
    if name.endswith("describe_table"):
        table = str(arguments.get("table") or "")
        if table.lower() not in allow:
            return {"text": f"table {table} is not allowlisted", "is_error": True}
        return {"text": "id, sku, quantity", "is_error": False}
    sql = str(arguments.get("sql") or "")
    try:
        checked = check_sql(sql, allow_tables=allow, deny_columns=set(), row_limit=1000)
    except SqlRejected as exc:
        return {"text": exc.reason, "is_error": True}
    if "count" in sql.lower():
        return {"text": str(len(_ORDERS)), "is_error": False, "sql": checked}
    return {"text": str(len(_ORDERS)), "is_error": False, "sql": checked}


def handle(body: dict[str, Any], *, allow_tables: set[str] | None = None) -> dict[str, object]:
    """JSON-RPC tools/list and tools/call."""
    method = str(body.get("method") or "")
    request_id = body.get("id", 1)
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools()}}
    if method == "tools/call":
        raw_params = body.get("params")
        params = raw_params if isinstance(raw_params, dict) else {}
        raw_arguments = params.get("arguments")
        arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
        outcome = call(str(params.get("name") or ""), arguments, allow_tables=allow_tables)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": outcome["text"]}],
                "isError": outcome["is_error"],
            },
        }
    return {"jsonrpc": "2.0", "id": request_id, "error": {"message": "unknown method"}}
