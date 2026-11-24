"""In-process tool handlers for the built-in tool servers, and for endpoints a pack registers."""

import uuid
from typing import Any

from ar_common.errors import ArError
from ar_domain.files.logic import FileView, can_read_file
from ar_domain.tools.logic import as_int

Handler = Any
_ENDPOINTS: dict[str, Handler] = {}
_DISCOVERED: dict[str, list[dict[str, object]]] = {}


def register_endpoint(
    endpoint: str, handler: Handler, *, tools: list[dict[str, object]] | None = None
) -> None:
    """Let a pack serve an in-process endpoint. Core does not import the pack.

    ``tools`` is what discovery lists for a tool server registered at this address.
    """
    _ENDPOINTS[endpoint] = handler
    _DISCOVERED[endpoint] = [dict(item) for item in tools or []]


def endpoint_registered(endpoint: str) -> bool:
    """Whether something in this process serves the address."""
    return endpoint in _ENDPOINTS


def endpoint_tools(endpoint: str) -> list[dict[str, object]]:
    """The tools a registered in-process endpoint offers to discovery."""
    return [dict(item) for item in _DISCOVERED.get(endpoint, [])]


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
        from ar_domain.tools.web import dispatch_web  # noqa: PLC0415

        return dispatch_web(store, name, arguments)
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
    if endpoint == "builtin://session":
        return _session(store, name, arguments)
    if endpoint == "builtin://knowledge":
        return _knowledge(store, name, arguments)
    if endpoint == "builtin://memory":
        return _memory(store, name, arguments)
    if endpoint == "builtin://routines":
        return _routines(store, name, arguments)
    if endpoint == "builtin://skills":
        return _skills(store, name, arguments)
    if endpoint == "builtin://connectors":
        from ar_domain.connectors.dispatch import dispatch_connector  # noqa: PLC0415

        return dispatch_connector(store, name, arguments)
    if endpoint == "builtin://research":
        from ar_domain.research.handlers import dispatch_research  # noqa: PLC0415

        return dispatch_research(store, name, arguments)
    if endpoint == "builtin://context":
        from ar_domain.research.handlers import dispatch_context  # noqa: PLC0415

        return dispatch_context(store, name, arguments)
    return {
        "text": "upstream server is not reachable",
        "structured": {},
        "is_error": True,
        "code": "upstream_error",
    }


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
    from ar_domain.durability.store import read_blob  # noqa: PLC0415

    blob = read_blob(store, key)
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


def _session(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    if name in {"plan_update", "update"}:
        plan = arguments.get("plan")
        if not isinstance(plan, list):
            return _error("validation_failed", "plan must be a list of steps")
        items = [str(item) for item in plan]
        conversation_id = arguments.get("conversation_id")
        if isinstance(conversation_id, uuid.UUID) and conversation_id in store.conversations:
            store.conversations[conversation_id]["plan"] = items
        return {"text": "Plan updated.", "structured": {"plan": items}, "is_error": False}
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
    """Every tool ``session.search`` ranks for a caller of this tenant."""
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
    if row.get("tool_server_version_id") != server.get("current_version_id"):
        return False
    from ar_domain.proof import offered_to_model  # noqa: PLC0415
    from ar_domain.tools.readiness import ready_for  # noqa: PLC0415

    name = str(row.get("qualified_name") or "")
    return offered_to_model(name, store, _tenant_uuid(tenant)) and ready_for(
        store, _tenant_uuid(tenant), name
    )


def _tenant_uuid(tenant: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(tenant)
    except ValueError:
        return None


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
            or str(row.get("qualified_name")).split(".", 1)[0] in {"files", "session"}
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


def _resolve_collection_ids(raw: object, collections: list[dict[str, object]]) -> list[str]:
    """Turn a model's ``collection_ids`` into real collection ids.

    The model only sees collection names in its context, so it often passes a name, a slug
    or a hallucinated id instead of a uuid. Accept any of a uuid, a slug or a name
    (case-insensitive), matched against the collections the person can read, and drop
    anything that does not match — so a bad id never crashes the search, and the handler
    falls back to searching every readable collection.
    """
    if not isinstance(raw, list):
        return []
    by_id = {str(row["id"]): str(row["id"]) for row in collections}
    by_slug = {
        str(row.get("slug") or "").lower(): str(row["id"]) for row in collections if row.get("slug")
    }
    by_name = {
        str(row.get("name") or "").lower(): str(row["id"]) for row in collections if row.get("name")
    }
    resolved: list[str] = []
    for item in raw:
        key = str(item).strip()
        match = by_id.get(key) or by_slug.get(key.lower()) or by_name.get(key.lower())
        if match and match not in resolved:
            resolved.append(match)
    return resolved


def _bound_collections(store: Any, arguments: dict[str, object]) -> set[str] | None:
    """The collection slugs the calling agent is bound to, or None when it names none.

    An agent that binds collections reads those and no others, whatever the person may
    read. One that binds none reads what the person may read.
    """
    version = getattr(store, "versions", {}).get(arguments.get("_agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    knowledge = definition.get("knowledge") if isinstance(definition, dict) else None
    slugs = knowledge.get("collections") if isinstance(knowledge, dict) else None
    if not isinstance(slugs, list) or not slugs:
        return None
    return {str(item).lower() for item in slugs}


def _within(rows: list[dict[str, object]], bound: set[str] | None) -> list[dict[str, object]]:
    if bound is None:
        return rows
    return [row for row in rows if str(row.get("slug") or "").lower() in bound]


def _document_within(store: Any, document: dict[str, object], bound: set[str] | None) -> bool:
    if bound is None:
        return True
    collections = getattr(store, "knowledge_collections", {})
    if not isinstance(collections, dict):
        return False
    wanted = str(document.get("collection_id") or document.get("collectionId") or "")
    for key, row in collections.items():
        if str(key) == wanted and isinstance(row, dict):
            return str(row.get("slug") or "").lower() in bound
    return False


def _knowledge(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:  # noqa: PLR0911
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.knowledge.book import KnowledgeBook  # noqa: PLC0415

    tenant = arguments.get("_tenant_id")
    user = arguments.get("_user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return _error("validation_failed", "knowledge search needs a signed-in person")
    actor = Actor(tenant, user, frozenset({"knowledge:read"}))
    book = KnowledgeBook(store)
    bound = _bound_collections(store, arguments)
    if name == "list_collections":
        rows = _within(book.list_collections(actor), bound)
        lines = [f"{row['slug']}: {row['name']}" for row in rows]
        text = "\n".join(lines) or "No collections."
        return {"text": text, "structured": {"collections": rows}, "is_error": False}
    if name == "get_document":
        try:
            document = book.get_document(actor, uuid.UUID(str(arguments.get("document_id"))))
        except ValueError, TypeError, ArError:
            return _error("not_found", "document was not found")
        if not _document_within(store, document, bound):
            return _error("not_found", "document was not found")
        return {
            "text": str(document.get("summary") or document.get("title") or ""),
            "structured": document,
            "is_error": False,
        }
    if name != "search":
        return _error("unknown_tool", f"unknown tool {name}")
    collections = _within(book.list_collections(actor), bound)
    if bound is not None and not collections:
        return {
            "text": "No sufficiently relevant documents were found.",
            "structured": {"hits": [], "answerable": False},
            "is_error": False,
        }
    raw_ids: list[object] = list(
        _resolve_collection_ids(arguments.get("collection_ids"), collections)
    )
    if not raw_ids:
        # None given, or none matched a readable collection: search them all, as the tool's
        # description promises ("omit to search every collection the person can read").
        raw_ids = [row["id"] for row in collections]
    raw_top = arguments.get("top_k")
    top_k = raw_top if isinstance(raw_top, int) and not isinstance(raw_top, bool) else 8
    try:
        body: dict[str, object] = {
            "query": str(arguments.get("query") or ""),
            "collection_ids": raw_ids,
            "top_k": top_k,
        }
        if arguments.get("min_score") is not None:
            body["min_score"] = arguments.get("min_score")
        if arguments.get("document_ids"):
            body["document_ids"] = arguments.get("document_ids")
        found = book.search(actor, body)
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


def _nothing_to_report(store: Any, arguments: dict[str, object]) -> dict[str, object]:
    """Note that this run found nothing to report. The saved call is the note."""
    run_id = arguments.get("_run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    by_routine = isinstance(run, dict) and run.get("trigger") == "routine"
    text = (
        "Noted. Deliveries set to send only when there is something to report will not be "
        "sent for this run. Give your short answer now."
        if by_routine
        else "Noted. This run was not started by a routine, so nothing is delivered either way."
    )
    return {"text": text, "structured": {"nothingToReport": True}, "is_error": False}


def _routines(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.routines.book import RoutineBook  # noqa: PLC0415

    tenant = arguments.get("_tenant_id")
    user = arguments.get("_user_id")
    if not isinstance(tenant, uuid.UUID) or not isinstance(user, uuid.UUID):
        return _error("validation_failed", "routine tools need a signed-in person")
    actor = Actor(tenant, user, frozenset({"routines:create", "routines:read", "chat:use"}))
    book = RoutineBook(store)
    try:
        if name == "list":
            rows = book.list_routines(actor)
            return {
                "text": f"{len(rows)} routines.",
                "structured": {"routines": rows},
                "is_error": False,
            }
        if name == "nothing_to_report":
            return _nothing_to_report(store, arguments)
        if name != "create":
            return _error("unknown_tool", f"unknown tool {name}")
        trigger_type = str(arguments.get("trigger_type") or arguments.get("triggerType") or "")
        trigger: dict[str, object] = {"type": trigger_type}
        if trigger_type == "schedule":
            trigger["cron"] = str(arguments.get("cron") or "0 * * * *")
            trigger["timezone"] = str(arguments.get("timezone") or "UTC")
        run_id = arguments.get("_run_id")
        run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
        agent_id = arguments.get("agent_id") or (
            run.get("agent_id") if isinstance(run, dict) else None
        )
        created = book.create(
            actor,
            {
                "name": arguments.get("name"),
                "instructions": arguments.get("instructions"),
                "agent_id": agent_id,
                "trigger": trigger,
            },
        )
    except (ValueError, TypeError, ArError) as exc:
        return _error("validation_failed", str(exc))
    return {
        "text": f"Created routine {created.get('id')}.",
        "structured": created,
        "is_error": False,
    }


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


def _error(code: str, message: str) -> dict[str, object]:
    return {"text": message, "structured": {}, "is_error": True, "code": code}
