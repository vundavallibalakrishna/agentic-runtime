"""In-process tool handlers for built-ins, the demo ticket server and the warehouse."""

import uuid
from typing import Any

from ar_common.errors import ArError
from ar_domain.files.logic import FileView, can_read_file
from ar_domain.tools.logic import as_int
from ar_domain.tools.sql_guard import SqlRejected, check_sql

Handler = Any
_ENDPOINTS: dict[str, Handler] = {}
_ORDERS = (
    {"id": 1, "sku": "paper", "quantity": 4},
    {"id": 2, "sku": "ink", "quantity": 2},
    {"id": 3, "sku": "stapler", "quantity": 1},
)


def orders() -> list[dict[str, object]]:
    return [dict(row) for row in _ORDERS]


def register_endpoint(endpoint: str, handler: Handler) -> None:
    """Let a pack serve an in-process endpoint. Core does not import the pack."""
    _ENDPOINTS[endpoint] = handler


def dispatch(  # noqa: PLR0911, PLR0912
    store: Any, endpoint: str, name: str, arguments: dict[str, object], token: str
) -> dict[str, object]:
    """Run one in-process tool. Unknown endpoints are upstream errors."""
    extra = _ENDPOINTS.get(endpoint)
    if extra is not None:
        result = extra(store, name, arguments, token)
        if isinstance(result, dict):
            return result
        return {
            "text": "upstream server is not reachable",
            "structured": {},
            "is_error": True,
            "code": "upstream_error",
        }
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
    if endpoint == "builtin://general":
        from ar_domain.tools.general import dispatch_general  # noqa: PLC0415

        return dispatch_general(store, name, arguments)
    if endpoint == "builtin://data":
        from ar_domain.tools.database import dispatch_data  # noqa: PLC0415

        return dispatch_data(store, name, arguments)
    if endpoint == "builtin://documents":
        from ar_domain.tools.documents import dispatch_documents  # noqa: PLC0415

        return dispatch_documents(store, name, arguments)
    if endpoint == "builtin://image":
        from ar_domain.tools.vision import dispatch_image  # noqa: PLC0415

        return dispatch_image(store, name, arguments)
    if endpoint == "builtin://http_operation":
        from ar_domain.tools.http_tools import execute_operation  # noqa: PLC0415

        return execute_operation(store, arguments)
    if endpoint == "builtin://control":
        return _control(store, name, arguments)
    if endpoint == "builtin://knowledge":
        return _knowledge(store, name, arguments)
    if endpoint == "builtin://memory":
        return _memory(store, name, arguments)
    if endpoint == "builtin://skills":
        return _skills(store, name, arguments)
    if endpoint == "builtin://records":
        return _records(store, name, arguments)
    if endpoint == "builtin://connectors":
        from ar_domain.connectors.dispatch import dispatch_connector  # noqa: PLC0415

        return dispatch_connector(store, name, arguments)
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


def _caller(arguments: dict[str, object]) -> tuple[str, str]:
    """The calling tenant and user as text. Empty when the call names no caller."""
    tenant = arguments.get("_tenant_id")
    user = arguments.get("_user_id")
    return (str(tenant) if tenant else "", str(user) if user else "")


def _own_conversations(store: Any, tenant: str, user: str, agent: str = "") -> set[object]:
    """Ids of the caller's conversations, with one agent when named. No caller owns none."""
    if not tenant or not user:
        return set()
    return {
        key
        for key, row in list(store.conversations.items())
        if str(row.get("tenant_id")) == tenant
        and str(row.get("user_id")) == user
        and row.get("deleted_at") is None
        and (not agent or str(row.get("agent_id")) == agent)
    }


def _may_read_file(row: object, tenant: str, user: str, own: set[object]) -> bool:
    """The file API's rule: same tenant, and the owner or the owner of its conversation."""
    if not tenant or not user or not isinstance(row, dict):
        return False
    conversation_id = row.get("conversation_id")
    owner = row.get("owner_user_id")
    view = FileView(
        tenant_id=str(row.get("tenant_id")),
        owner_user_id=str(owner) if owner else None,
        conversation_id=str(conversation_id) if conversation_id else None,
        status="deleted" if row.get("deleted_at") is not None else str(row.get("status") or ""),
    )
    return can_read_file(
        view,
        tenant_id=tenant,
        user_id=user,
        conversation_owner=conversation_id in own,
        read_all=False,
    )


def _files(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    tenant, user = _caller(arguments)
    own = _own_conversations(store, tenant, user)
    if name == "list":
        rows = [
            str(row.get("name"))
            for row in list(store.files.values())
            if _may_read_file(row, tenant, user, own)
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
    if blob is None or not _may_read_file(store.files.get(key), tenant, user, own):
        return _error("not_found", "file was not found")
    offset = as_int(arguments.get("offset"), 0)
    limit = as_int(arguments.get("limit"), 65536)
    text = bytes(blob)[offset : offset + limit].decode("utf-8", errors="replace")
    return {"text": text, "structured": {}, "is_error": False}


def _history(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    del name
    query = str(arguments.get("query") or "").lower()
    limit = min(as_int(arguments.get("limit"), 10), 10)
    tenant, user = _caller(arguments)
    agent = arguments.get("_agent_id")
    own = _own_conversations(store, tenant, user, str(agent) if agent else "")
    hits: list[str] = []
    for row in list(store.messages.values()):
        if str(row.get("tenant_id")) != tenant or row.get("conversation_id") not in own:
            continue
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
    settings = _settings(store, arguments)
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
        if not isinstance(plan, list):
            return _error("validation_failed", "plan must be a list of steps")
        items = [str(item) for item in plan]
        conversation_id = arguments.get("conversation_id")
        if isinstance(conversation_id, uuid.UUID) and conversation_id in store.conversations:
            store.conversations[conversation_id]["plan"] = items
        return {"text": "Plan updated.", "structured": {"plan": items}, "is_error": False}
    if name == "checkpoint":
        return _checkpoint(store, arguments)
    if name == "propose_change":
        return _propose_change(store, arguments)
    if name == "a2a_call":
        from ar_domain.exposure.a2a import call_remote  # noqa: PLC0415

        return call_remote(store, arguments)
    from ar_domain.tools.search import DEFAULT_TOP_K  # noqa: PLC0415

    query = str(arguments.get("query") or "")
    ranked, how = _search(store, query, _caller(arguments)[0], _granted_names(store, arguments))
    lines = [f"{row['qualified_name']}: {row['description']}" for row in ranked[:DEFAULT_TOP_K]]
    return {
        "text": "\n".join(lines),
        "structured": {"tools": ranked[:DEFAULT_TOP_K], "ranked_by": how},
        "is_error": False,
    }


def _checkpoint(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """First call in a run fails so the agent can read the error and retry."""
    note = str(arguments.get("note") or "").strip()
    if not note:
        return _error("validation_failed", "note is required")
    from ar_domain.records.memory import bucket  # noqa: PLC0415

    seen = bucket(store, "checkpoints")
    key = str(arguments.get("_run_id") or arguments.get("conversation_id") or "run")
    current = seen.get(key)
    previous = 0
    if isinstance(current, dict):
        raw_count = current.get("count")
        if isinstance(raw_count, int) and not isinstance(raw_count, bool):
            previous = raw_count
    count = previous + 1
    seen[key] = {"count": count}
    if count == 1:
        return _error(
            "upstream_error",
            "temporary failure, call checkpoint again with confirm set to true",
        )
    if arguments.get("confirm") is not True:
        return _error("validation_failed", "set confirm to true and retry")
    return {
        "text": f"Checkpoint saved: {note}",
        "structured": {"saved": True},
        "is_error": False,
    }


def _propose_change(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """Persist a change. The policy gate runs this only after approval."""
    summary = str(arguments.get("summary") or "").strip()
    if not summary:
        return _error("validation_failed", "summary is required")
    conversation_id = arguments.get("_conversation_id")
    if isinstance(conversation_id, uuid.UUID):
        conversation = store.conversations.get(conversation_id)
        if isinstance(conversation, dict):
            conversation["accepted_change"] = True
    return {"text": "Change saved.", "structured": {"saved": True}, "is_error": False}


def searchable_tools(store: Any, tenant: str) -> list[dict[str, object]]:
    """Every tool ``control.search`` ranks for a caller of this tenant."""
    return [row for row in list(store.tool_versions.values()) if _searchable(store, row, tenant)]


def _searchable(store: Any, row: dict[str, object], tenant: str) -> bool:
    """A platform tool or the caller's tenant's tool, on an approved server's current version."""
    owner = row.get("tenant_id")
    if owner is not None and (not tenant or str(owner) != tenant):
        return False
    tool = store.tool_defs.get(row.get("tool_id"))
    if not isinstance(tool, dict) or tool.get("disabled_at") is not None:
        return False
    server = store.tool_servers.get(tool.get("tool_server_id"))
    if not isinstance(server, dict):
        return False
    if server.get("status") != "approved" or server.get("disabled_at") is not None:
        return False
    return row.get("tool_server_version_id") == server.get("current_version_id")


def _granted_names(store: Any, arguments: dict[str, object]) -> set[str] | None:
    """The qualified names this agent is granted, or None when no agent is named (F45)."""
    version_id = arguments.get("_agent_version_id")
    user_id = arguments.get("_user_id")
    if not isinstance(version_id, uuid.UUID) or not isinstance(user_id, uuid.UUID):
        return None
    from ar_domain.tools.pipeline import ToolPipeline  # noqa: PLC0415

    catalog = ToolPipeline(store).resolve_catalog(agent_version_id=version_id, user_id=user_id)
    tools = catalog.get("tools")
    if not isinstance(tools, list):
        return None
    return {str(row.get("qualified_name")) for row in tools if isinstance(row, dict)}


def _search(
    store: Any, query: str, tenant: str, granted: set[str] | None = None
) -> tuple[list[dict[str, object]], str]:
    """The caller's searchable tools, closest to ``query`` first, and how they were ranked.

    When ``granted`` is given, only tools the agent is bound to (plus the always-available
    file and control tools) are searched, so a search never leaks another agent's tools (F45).
    """
    from ar_domain.tools.search import rank_tools  # noqa: PLC0415

    rows = searchable_tools(store, tenant)
    if granted is not None:
        rows = [
            row
            for row in rows
            if str(row.get("qualified_name")) in granted
            or str(row.get("qualified_name")).split(".", 1)[0] in {"files", "control"}
        ]
    try:
        tenant_id: object = uuid.UUID(tenant) if tenant else None
    except ValueError:
        tenant_id = None
    ranked, how = rank_tools(store, tenant_id, query, rows)
    found = [
        {
            "qualified_name": str(row.get("qualified_name")),
            "description": str(row.get("description")),
            "score": score,
        }
        for score, row in ranked
    ]
    return found, how


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


def _knowledge(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:  # noqa: PLR0911
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.knowledge.book import KnowledgeBook  # noqa: PLC0415

    tenant = arguments.get("_tenant_id")
    user = arguments.get("_user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return _error("validation_failed", "knowledge search needs a signed-in person")
    actor = Actor(tenant, user, frozenset({"knowledge:read"}))
    book = KnowledgeBook(store)
    if name == "list_collections":
        rows = book.list_collections(actor)
        lines = [f"{row['slug']}: {row['name']}" for row in rows]
        text = "\n".join(lines) or "No collections."
        return {"text": text, "structured": {"collections": rows}, "is_error": False}
    if name == "get_document":
        try:
            document = book.get_document(actor, uuid.UUID(str(arguments.get("document_id"))))
        except ValueError, TypeError, ArError:
            return _error("not_found", "document was not found")
        return {
            "text": str(document.get("summary") or document.get("title") or ""),
            "structured": document,
            "is_error": False,
        }
    if name != "search":
        return _error("unknown_tool", f"unknown tool {name}")
    raw_ids = arguments.get("collection_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        raw_ids = [row["id"] for row in book.list_collections(actor)]
    raw_top = arguments.get("top_k")
    top_k = raw_top if isinstance(raw_top, int) and not isinstance(raw_top, bool) else 8
    try:
        found = book.search(
            actor,
            {
                "query": str(arguments.get("query") or ""),
                "collection_ids": raw_ids,
                "top_k": top_k,
            },
        )
    except (ValueError, TypeError, ArError) as exc:
        return _error("validation_failed", str(exc))
    raw_hits = found.get("hits")
    hits: list[object] = raw_hits if isinstance(raw_hits, list) else []
    if not found.get("answerable"):
        return {
            "text": "No sufficiently relevant documents were found.",
            "structured": {"hits": [], "answerable": False},
            "is_error": False,
        }
    lines = [
        f"[{index}] {hit.get('title')}: {hit.get('snippet')}"
        for index, hit in enumerate(hits, start=1)
        if isinstance(hit, dict)
    ]
    return {"text": "\n".join(str(line) for line in lines), "structured": found, "is_error": False}


def _memory(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.memory.book import MemoryBook  # noqa: PLC0415

    tenant = arguments.get("_tenant_id")
    user = arguments.get("_user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return _error("validation_failed", "memory tools need a signed-in person")
    actor = Actor(tenant, user, frozenset({"chat:use", "memory:manage_agent"}))
    book = MemoryBook(store)
    run_id = arguments.get("_run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    try:
        bound = run if isinstance(run, dict) else None
        if name == "search":
            rows = book.search_from_tool(actor, arguments, run=bound)
            lines = [f"{row['id']}: {row['content']}" for row in rows]
            text = "\n".join(lines) or "No memories."
            return {"text": text, "structured": {"facts": rows}, "is_error": False}
        if name == "save":
            fact = book.save_from_tool(actor, arguments, run=bound)
            return {"text": f"Saved memory {fact['id']}.", "structured": fact, "is_error": False}
        if name == "forget":
            count = book.forget_from_tool(actor, arguments)
            return {"text": f"Forgot {count}.", "structured": {"deleted": count}, "is_error": False}
    except (ValueError, TypeError, ArError) as exc:
        return _error("validation_failed", str(exc))
    return _error("unknown_tool", f"unknown tool {name}")


def _settings(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """The calling tenant's settings. A call without a tenant gets the defaults."""
    from ar_domain.identity.tenant_settings import settings_for  # noqa: PLC0415

    return settings_for(store, arguments.get("_tenant_id"))


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _skills(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name != "load":
        return _error("unknown_tool", f"unknown tool {name}")
    raw_run = arguments.get("_run_id")
    try:
        run_id = uuid.UUID(str(raw_run))
    except ValueError:
        return _error("validation_failed", "skill load needs a run")
    run = store.runs.get(run_id)
    if not isinstance(run, dict):
        return _error("validation_failed", "skill load needs a run")
    from ar_domain.skills.load import load_skill  # noqa: PLC0415

    return load_skill(store, run, str(arguments.get("skill") or ""))


def _records(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415
    from ar_domain.records.vault import EvidenceBook  # noqa: PLC0415

    try:
        tenant_id = uuid.UUID(str(arguments.get("_tenant_id")))
        user_id = uuid.UUID(str(arguments.get("_user_id")))
    except ValueError:
        return _error("validation_failed", "records tools need a tenant")
    actor = Actor(tenant_id=tenant_id, user_id=user_id, permissions=PERMISSION_KEYS)
    book = EvidenceBook(store)
    if name == "capture":
        text = str(arguments.get("text") or "")
        file_id = arguments.get("bytes_file_id") or arguments.get("file_id")
        data = text.encode()
        if file_id:
            blob = store.blobs.get(uuid.UUID(str(file_id)))
            data = blob if isinstance(blob, bytes) else data
        if str(arguments.get("collection_method")) == "browser_screenshot" and not file_id:
            return _error("validation_failed", "browser screenshots are captured from a file")
        captured = book.capture(actor, arguments, data)
        return {
            "text": str(captured.get("content_sha256")),
            "structured": {
                "evidence_item_id": str(captured.get("id")),
                "content_sha256": captured.get("content_sha256"),
            },
            "is_error": False,
        }
    if name == "get":
        item = book.get(actor, uuid.UUID(str(arguments.get("evidence_item_id"))))
        return {"text": str(item.get("content_sha256")), "structured": item, "is_error": False}
    if name == "verify":
        report = book.verify(actor, uuid.UUID(str(arguments.get("evidence_item_id"))))
        return {"text": str(report.get("valid")), "structured": report, "is_error": False}
    return _error("unknown_tool", f"unknown tool {name}")


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
