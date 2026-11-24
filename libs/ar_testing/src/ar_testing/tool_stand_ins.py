"""Stand-in tool servers for tests: tickets, a pet store, a warehouse and an echo.

A test needs a tool server it can register, call and watch fail without a network. No
product tool server is one of these, so they live here. Each is an in-process endpoint,
registered the way a pack registers its own (``register_endpoint``). The product holds
none of this: a tool server at one of these addresses is unreachable in an install,
because nothing there registers it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_domain.tools.handlers import orders, register_endpoint
from ar_domain.tools.logic import as_int
from ar_domain.tools.sql_guard import SqlRejected, check_sql

if TYPE_CHECKING:
    from typing import Any

TICKETS = "memory://tickets"
ECHO = "memory://echo"
PETSTORE = "memory://petstore"
WAREHOUSE = "memory://warehouse"

ECHO_TOOLS: list[dict[str, object]] = [
    {
        "name": "ping",
        "title": "Ping",
        "description": "Return the message so a reviewer can see the tool.",
        "input_schema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
        "risk_class": "R0",
        "annotations": {"readOnlyHint": True},
    }
]


def register_stand_ins() -> None:
    """Serve the four stand-in addresses in this process. Safe to call again."""
    register_endpoint(TICKETS, _tickets)
    register_endpoint(ECHO, _echo, tools=ECHO_TOOLS)
    register_endpoint(
        PETSTORE, lambda store, name, arguments, _token: _pets(store, name, arguments)
    )
    register_endpoint(
        WAREHOUSE, lambda store, name, arguments, _token: _sql(store, name, arguments)
    )


def _echo(_store: Any, _name: str, arguments: dict[str, object], _token: str) -> dict[str, object]:
    return {
        "text": f"pong {arguments.get('message', '')}".strip(),
        "structured": {},
        "is_error": False,
    }


def _tickets(store: Any, name: str, arguments: dict[str, object], token: str) -> dict[str, object]:
    if not token:
        return _error("credential_required", "Connect the tickets account to continue.")
    book = store.tickets
    if name == "list_tickets":
        lines = [f"{row['id']}: {row['title']}" for row in book]
        return {
            "text": "\n".join(lines) or "No tickets yet.",
            "structured": {"tickets": list(book)},
            "is_error": False,
        }
    if name != "create_ticket":
        return _error("unknown_tool", f"unknown tool {name}")
    title = str(arguments.get("title") or "").strip()
    if not title:
        return _error("validation_failed", "title is required")
    number = 1000 + len(book) + 1
    row = {"id": f"TCK-{number}", "title": title, "body": str(arguments.get("body") or "")}
    book.append(row)
    return {"text": f"Filed ticket {row['id']}.", "structured": row, "is_error": False}


def _pets(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:  # noqa: PLR0911
    pets: list[dict[str, object]] = store.pets
    if name == "list_pets":
        return {
            "text": ", ".join(str(pet["name"]) for pet in pets),
            "structured": {"pets": list(pets)},
            "is_error": False,
        }
    if name == "show_pet":
        pet_id = arguments.get("petId")
        for pet in pets:
            if pet["id"] == pet_id or str(pet["id"]) == str(pet_id):
                return {"text": str(pet["name"]), "structured": pet, "is_error": False}
        return _error("not_found", "pet was not found")
    if name == "create_pet":
        body = arguments.get("body")
        name_value = body.get("name") if isinstance(body, dict) else arguments.get("name")
        pet = {"id": len(pets) + 1, "name": str(name_value or "pet")}
        pets.append(pet)
        return {"text": f"Created pet {pet['id']}.", "structured": pet, "is_error": False}
    if name == "delete_pet":
        pet_id = arguments.get("petId")
        for index, pet in enumerate(list(pets)):
            if pet["id"] == pet_id or str(pet["id"]) == str(pet_id):
                pets.pop(index)
                return {
                    "text": f"Deleted pet {pet_id}.",
                    "structured": {"id": pet_id},
                    "is_error": False,
                }
        return _error("not_found", "pet was not found")
    return _error("unknown_tool", f"unknown tool {name}")


def _sql(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    connection = _connection(store, arguments)
    allow = {item.lower() for item in _strings(connection.get("tables"))} or {"public.orders"}
    deny = {item.lower() for item in _strings(connection.get("columns_deny"))}
    limit = as_int(connection.get("row_limit"), 1000)
    if name.endswith("list_tables"):
        return {
            "text": "\n".join(sorted(allow)),
            "structured": {"tables": sorted(allow)},
            "is_error": False,
        }
    if name.endswith("describe_table"):
        table = str(arguments.get("table") or "public.orders")
        if table.lower() not in allow:
            return _error("not_allowlisted", f"table {table} is not allowlisted")
        columns = ["id", "sku", "quantity"]
        return {"text": ", ".join(columns), "structured": {"columns": columns}, "is_error": False}
    sql = str(arguments.get("sql") or "")
    try:
        checked = check_sql(sql, allow_tables=allow, deny_columns=deny, row_limit=limit)
    except SqlRejected as exc:
        return _error("sql_rejected", exc.reason)
    rows = orders()
    if "count" in sql.lower():
        text = str(len(rows))
        structured: dict[str, object] = {
            "columns": ["count"],
            "rows": [[len(rows)]],
            "truncated": False,
        }
    else:
        header = "id,sku,quantity"
        body = "\n".join(f"{row['id']},{row['sku']},{row['quantity']}" for row in rows)
        text = f"{header}\n{body}"
        structured = {
            "columns": ["id", "sku", "quantity"],
            "rows": [[row["id"], row["sku"], row["quantity"]] for row in rows],
            "truncated": False,
            "sql": checked,
        }
    return {"text": text, "structured": structured, "is_error": False}


def _connection(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    connection_id = arguments.get("data_connection_id")
    if isinstance(connection_id, uuid.UUID):
        row = store.data_connections.get(connection_id)
        if isinstance(row, dict):
            allow = row.get("allowlist")
            if isinstance(allow, dict):
                return {
                    "tables": allow.get("tables") or [],
                    "columns_deny": allow.get("columns_deny") or [],
                    "row_limit": row.get("row_limit") or 1000,
                }
    return {"tables": ["public.orders"], "columns_deny": [], "row_limit": 1000}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
