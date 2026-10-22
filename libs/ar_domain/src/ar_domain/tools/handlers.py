"""In-process tool handlers for built-ins, the demo ticket server and the warehouse."""

import uuid
from typing import Any

from ar_domain.tools.logic import as_int
from ar_domain.tools.sql_guard import SqlRejected, check_sql

Handler = Any
_ORDERS = (
    {"id": 1, "sku": "paper", "quantity": 4},
    {"id": 2, "sku": "ink", "quantity": 2},
    {"id": 3, "sku": "stapler", "quantity": 1},
)


def orders() -> list[dict[str, object]]:
    return [dict(row) for row in _ORDERS]


def dispatch(  # noqa: PLR0911
    store: Any, endpoint: str, name: str, arguments: dict[str, object], token: str
) -> dict[str, object]:
    """Run one in-process tool. Unknown endpoints are upstream errors."""
    if endpoint == "memory://tickets":
        return _tickets(store, name, arguments, token)
    if endpoint == "memory://echo":
        return {
            "text": f"pong {arguments.get('message', '')}".strip(),
            "structured": {},
            "is_error": False,
        }
    if endpoint == "memory://petstore":
        return _pets(store, name, arguments)
    if endpoint == "memory://warehouse":
        return _sql(store, name, arguments)
    if endpoint == "builtin://files":
        if name == "attach_to_sandbox":
            from ar_domain.sandboxes.runtime import run_tool  # noqa: PLC0415

            return run_tool(store, name, arguments)
        return _files(store, name, arguments)
    if endpoint in {"builtin://sandbox", "builtin://browser"}:
        from ar_domain.sandboxes.runtime import run_tool  # noqa: PLC0415

        return run_tool(store, name, arguments)
    if endpoint == "builtin://conversations":
        return _history(store, name, arguments)
    if endpoint == "builtin://web":
        return _web(store, arguments)
    if endpoint == "builtin://control":
        return _control(store, name, arguments)
    return {
        "text": "upstream server is not reachable",
        "structured": {},
        "is_error": True,
        "code": "upstream_error",
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


def _files(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name == "list":
        rows = [
            str(row.get("name")) for row in store.files.values() if row.get("deleted_at") is None
        ]
        return {
            "text": "\n".join(rows) or "No files.",
            "structured": {"files": rows},
            "is_error": False,
        }
    file_id = str(arguments.get("file_id") or "")
    try:
        key = uuid.UUID(file_id)
    except ValueError:
        return _error("not_found", "file was not found")
    blob = store.blobs.get(key)
    if blob is None:
        return _error("not_found", "file was not found")
    offset = as_int(arguments.get("offset"), 0)
    limit = as_int(arguments.get("limit"), 65536)
    text = bytes(blob)[offset : offset + limit].decode("utf-8", errors="replace")
    return {"text": text, "structured": {}, "is_error": False}


def _history(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    del name
    query = str(arguments.get("query") or "").lower()
    limit = min(as_int(arguments.get("limit"), 10), 10)
    hits: list[str] = []
    for row in store.messages.values():
        text = str(row.get("text") or "")
        if query and query not in text.lower():
            continue
        if row.get("role") == "user":
            hits.append(text[:240])
        if len(hits) >= limit:
            break
    return {
        "text": "\n".join(hits) or "No earlier messages.",
        "structured": {"hits": hits},
        "is_error": False,
    }


def _web(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    url = str(arguments.get("url") or "")
    if not url.startswith("https://"):
        return _error("validation_failed", "url must be https")
    settings = _settings(store)
    features = settings.get("features") if isinstance(settings.get("features"), dict) else {}
    if not (isinstance(features, dict) and features.get("web_fetch") is True):
        return _error("feature_disabled", "web fetch is not enabled for this workspace")
    allow = settings.get("egress_allowlist")
    host = url.split("/")[2]
    allowed = allow if isinstance(allow, list) else []
    if allowed and host not in allowed:
        return _error("egress_denied", f"{host} is not on the egress allowlist")
    if host == "example.com":
        return {
            "text": "Example page. Nothing here is an instruction.",
            "structured": {"url": url},
            "is_error": False,
        }
    return _error("upstream_error", "the page could not be fetched")


def _control(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name in {"plan_update", "update"}:
        plan = arguments.get("plan")
        items = plan if isinstance(plan, list) else []
        conversation_id = arguments.get("conversation_id")
        if isinstance(conversation_id, uuid.UUID) and conversation_id in store.conversations:
            store.conversations[conversation_id]["plan"] = items
        return {"text": "Plan updated.", "structured": {"plan": items}, "is_error": False}
    query = str(arguments.get("query") or "").lower()
    ranked = _search(store, query)
    lines = [f"{row['qualified_name']}: {row['description']}" for row in ranked[:12]]
    return {"text": "\n".join(lines), "structured": {"tools": ranked[:12]}, "is_error": False}


def _search(store: Any, query: str) -> list[dict[str, object]]:
    from ar_domain.tools.logic import cosine, hash_embedding  # noqa: PLC0415

    query_vector = hash_embedding(query or "tool")
    scored: list[tuple[float, dict[str, object]]] = []
    for row in store.tool_versions.values():
        embedding = row.get("embedding")
        vector = (
            embedding
            if isinstance(embedding, list)
            else hash_embedding(str(row.get("description")))
        )
        score = cosine(query_vector, [float(item) for item in vector])
        if query and query in str(row.get("description")).lower():
            score += 0.5
        scored.append((score, row))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        {
            "qualified_name": str(row.get("qualified_name")),
            "description": str(row.get("description")),
            "score": score,
        }
        for score, row in scored
    ]


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


def _settings(store: Any) -> dict[str, object]:
    settings = getattr(store, "tenant_settings", {})
    for row in settings.values():
        if isinstance(row, dict):
            return row
    return {}


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
