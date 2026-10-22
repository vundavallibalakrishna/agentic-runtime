"""Idempotent tool catalogue for the dev process and ``make seed``."""

from typing import TYPE_CHECKING, Any

from ar_common.time import utcnow
from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import demo_id
from ar_domain.tools.logic import description_hash, hash_embedding, manifest_hash
from ar_domain.tools.openapi_import import operations_from

if TYPE_CHECKING:
    import uuid

PETSTORE: dict[str, object] = {
    "openapi": "3.0.3",
    "info": {"title": "Petstore", "version": "1.0.0"},
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List pets",
                "description": "Return the pets the caller can see.",
                "responses": {"200": {"description": "ok"}},
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "description": "Add a pet. This writes a new row.",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                                "required": ["name"],
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "showPet",
                "summary": "Show one pet",
                "description": "Return one pet by id.",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"200": {"description": "ok"}},
            },
            "delete": {
                "operationId": "deletePet",
                "summary": "Delete a pet",
                "description": "Remove a pet. This cannot be undone.",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "responses": {"204": {"description": "gone"}},
            },
        },
    },
}


def seed(store: Any) -> None:
    """Insert built-ins, the ticket server, petstore and the warehouse."""
    import ar_domain.tools.resolvers  # noqa: F401, PLC0415

    if getattr(store, "tools_seeded", False):
        return
    tenant = demo_id("tenant")
    admin = demo_id("admin")
    _settings(store, tenant)
    _builtin(store, "files", "Files", "builtin://files", _file_tools())
    _builtin(store, "conversations", "Conversations", "builtin://conversations", _history_tools())
    _builtin(store, "web", "Web", "builtin://web", _web_tools())
    _builtin(store, "control", "Control", "builtin://control", _control_tools())
    provider = _provider(store, tenant, admin)
    _tickets(store, tenant, admin, provider)
    _echo(store, tenant, admin)
    _petstore(store, tenant, admin)
    _warehouse(store, tenant, admin)
    _desk(store, tenant, admin)
    store.tools_seeded = True


def _settings(store: Any, tenant: uuid.UUID) -> None:
    store.tenant_settings.setdefault(
        tenant,
        {
            "security": {"allow_self_review": True},
            "features": {"web_fetch": True},
            "egress_allowlist": ["example.com"],
        },
    )


def _builtin(
    store: Any, slug: str, name: str, endpoint: str, tools: list[dict[str, object]]
) -> None:
    _approved(
        store,
        tenant_id=None,
        owner=None,
        slug=slug,
        name=name,
        description=f"Platform {name.lower()} tools.",
        kind="builtin",
        endpoint=endpoint,
        auth_mode="none",
        provider_id=None,
        tools=tools,
        config={},
    )


def _tickets(store: Any, tenant: uuid.UUID, admin: uuid.UUID, provider: uuid.UUID) -> None:
    _approved(
        store,
        tenant_id=tenant,
        owner=admin,
        slug="tickets",
        name="Tickets",
        description="Files a ticket on the workspace tracker.",
        kind="remote_mcp",
        endpoint="memory://tickets",
        auth_mode="user_oauth",
        provider_id=provider,
        tools=[
            _tool(
                "create_ticket",
                "Create a ticket",
                "Create a ticket for the signed-in person.",
                {
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["title"],
                },
                "W1",
            ),
            _tool(
                "list_tickets",
                "List tickets",
                "List tickets the signed-in person has filed.",
                {"type": "object", "properties": {}},
                "R0",
            ),
        ],
        config={},
    )
    grant_id = demo_id("grant-tickets")
    if grant_id not in store.credential_grants:
        store.credential_grants[grant_id] = {
            "id": grant_id,
            "tenant_id": tenant,
            "user_id": admin,
            "provider_id": provider,
            "scopes": ["tickets.write"],
            "status": "active",
            "refresh_token": "refresh-admin",
            "access_token": "access-admin",
            "external_account_label": "admin@dev.local",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }


def _echo(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    """A draft-ready catalogue entry is created on demand. The approved echo is for the wizard demo."""  # noqa: E501
    del store, tenant, admin


def _petstore(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    parsed = operations_from(PETSTORE)
    tools = [
        _tool(
            str(item["name"]),
            str(item["title"]),
            str(item["description"]),
            item["input_schema"] if isinstance(item["input_schema"], dict) else {},
            str(item["risk_class"]),
            annotations=item["annotations"] if isinstance(item["annotations"], dict) else {},
        )
        for item in parsed
    ]
    _approved(
        store,
        tenant_id=tenant,
        owner=admin,
        slug="petstore",
        name="Petstore",
        description="Sample OpenAPI tools from the Petstore document.",
        kind="openapi",
        endpoint="memory://petstore",
        auth_mode="none",
        provider_id=None,
        tools=tools,
        config={
            "openapi": {
                "base_url": "https://petstore.example",
                "operations": [item["operation_id"] for item in parsed],
            }
        },
    )


def _warehouse(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    connection_id = demo_id("connection-warehouse")
    secret_id = demo_id("secret-warehouse")
    if connection_id not in store.data_connections:
        store.secret_values[secret_id] = b"memory://warehouse"
        store.data_connections[connection_id] = {
            "id": connection_id,
            "tenant_id": tenant,
            "name": "Warehouse",
            "engine": "postgres",
            "dsn_secret_ref_id": secret_id,
            "identity_mode": "service",
            "allowlist": {"schemas": ["public"], "tables": ["public.orders"], "columns_deny": []},
            "row_limit": 1000,
            "statement_timeout_s": 30,
            "classification": "internal",
            "schema_notes": "Orders the workspace can read.",
            "status": "active",
            "created_by": admin,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
    slug = "warehouse"
    tools = [
        _tool(
            "list_tables",
            "List tables",
            "List tables on the warehouse connection.",
            {"type": "object", "properties": {}},
            "R0",
        ),
        _tool(
            "describe_table",
            "Describe a table",
            "Describe one allowlisted table.",
            {"type": "object", "properties": {"table": {"type": "string"}}, "required": ["table"]},
            "R0",
        ),
        _tool(
            "run_query",
            "Run a query",
            "Run one read-only select against the warehouse.",
            {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
            "R1",
        ),
    ]
    _approved(
        store,
        tenant_id=tenant,
        owner=admin,
        slug=slug,
        name="Warehouse",
        description="Read-only questions over the orders table.",
        kind="sql",
        endpoint="memory://warehouse",
        auth_mode="none",
        provider_id=None,
        tools=tools,
        config={"sql": {"data_connection_id": str(connection_id)}},
    )


def _desk(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    for agent in store.agents.values():
        if agent.get("tenant_id") == tenant and agent.get("slug") == "desk":
            return
    definition = assistant_definition()
    definition["persona"] = {
        "display_name": "Desk",
        "greeting": "Tell me the ticket or the question.",
    }
    definition["instructions"] = (
        "You file tickets and answer questions about orders. "
        "Use the tickets and warehouse tools when the person asks."
    )
    definition["starter_prompts"] = [
        "File a ticket: the printer on floor 3 is jammed",
        "How many orders are in the warehouse?",
    ]
    definition["tools"] = [
        {"server": "tickets", "version": "*", "include": ["*"]},
        {"server": "warehouse", "version": "*", "include": ["*"]},
        {"server": "petstore", "version": "*", "include": ["*"]},
    ]
    budget = definition.get("budget")
    if isinstance(budget, dict):
        budget["max_tool_calls"] = 8
        budget["max_parallel_tool_calls"] = 4
    from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415

    AgentLifecycle(store)._insert(
        tenant,
        admin,
        slug="desk",
        name="Desk",
        description="Files tickets and reads the orders table.",
        visibility="tenant",
        definition=definition,
        published=True,
    )


def _provider(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> uuid.UUID:
    provider_id = demo_id("provider-tickets")
    if provider_id not in store.credential_providers:
        now = utcnow()
        store.credential_providers[provider_id] = {
            "id": provider_id,
            "tenant_id": tenant,
            "slug": "tickets",
            "name": "Tickets",
            "kind": "oauth2",
            "authorize_url": "https://tickets.example/authorize",
            "token_url": "memory://oauth",
            "client_id": "ar-tickets",
            "default_scopes": ["tickets.write"],
            "extra": {},
            "status": "active",
            "created_by": admin,
            "created_at": now,
            "updated_at": now,
        }
    return provider_id


def _approved(
    store: Any,
    *,
    tenant_id: uuid.UUID | None,
    owner: uuid.UUID | None,
    slug: str,
    name: str,
    description: str,
    kind: str,
    endpoint: str,
    auth_mode: str,
    provider_id: uuid.UUID | None,
    tools: list[dict[str, object]],
    config: dict[str, object],
) -> None:
    for row in store.tool_servers.values():
        if row.get("slug") == slug and row.get("tenant_id") == tenant_id:
            return
    now = utcnow()
    server_id = demo_id(f"server-{slug}")
    version_id = demo_id(f"server-version-{slug}")
    manifest = {"tools": [item["name"] for item in tools]}
    digest = manifest_hash(manifest)
    store.tool_servers[server_id] = {
        "id": server_id,
        "tenant_id": tenant_id,
        "slug": slug,
        "name": name,
        "description": description,
        "kind": kind,
        "owner_team_id": None,
        "owner_user_id": owner,
        "status": "approved",
        "disabled_at": None,
        "disabled_reason": None,
        "current_version_id": version_id,
        "created_at": now,
        "updated_at": now,
    }
    store.tool_server_versions[version_id] = {
        "id": version_id,
        "tenant_id": tenant_id,
        "tool_server_id": server_id,
        "version": "1.0.0",
        "endpoint_url": endpoint,
        "config": config,
        "auth_mode": auth_mode,
        "secret_ref_id": None,
        "credential_provider_id": provider_id,
        "manifest": manifest,
        "manifest_hash": digest,
        "upstream_hash": digest,
        "review_status": "approved",
        "review_notes": "",
        "reviewed_by": owner,
        "reviewed_at": now,
        "discovered_at": now,
        "created_by": owner,
        "created_at": now,
    }
    for item in tools:
        tool_id = demo_id(f"tool-{slug}-{item['name']}")
        version_tool_id = demo_id(f"tool-version-{slug}-{item['name']}")
        text = str(item["description"])
        store.tool_defs[tool_id] = {
            "id": tool_id,
            "tenant_id": tenant_id,
            "tool_server_id": server_id,
            "name": item["name"],
            "qualified_name": f"{slug}.{item['name']}",
            "disabled_at": None,
            "disabled_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        store.tool_versions[version_tool_id] = {
            "id": version_tool_id,
            "tenant_id": tenant_id,
            "tool_id": tool_id,
            "tool_server_version_id": version_id,
            "name": item["name"],
            "qualified_name": f"{slug}.{item['name']}",
            "title": item["title"],
            "description": text,
            "description_hash": description_hash(text),
            "input_schema": item["input_schema"],
            "output_schema": None,
            "annotations": item.get("annotations") or {},
            "risk_class": item["risk_class"],
            "proposed_risk_class": item["risk_class"],
            "risk_confirmed": True,
            "data_classification": "internal",
            "timeout_s": 60,
            "rate_limit_per_minute": 60,
            "max_result_bytes": 65536,
            "idempotent": item["risk_class"] in {"R0", "R1"},
            "approval_preview": {},
            "embedding": hash_embedding(text),
            "created_at": now,
        }


def _tool(  # noqa: PLR0917
    name: str,
    title: str,
    description: str,
    schema: dict[str, object],
    risk: str,
    annotations: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "name": name,
        "title": title,
        "description": description,
        "input_schema": schema,
        "risk_class": risk,
        "annotations": annotations or {},
    }


def _file_tools() -> list[dict[str, object]]:
    return [
        _tool(
            "list",
            "List files",
            "List files visible in this conversation.",
            {"type": "object", "properties": {"scope": {"type": "string"}}},
            "R0",
        ),
        _tool(
            "read",
            "Read a file",
            "Read text from a file the person can access.",
            {
                "type": "object",
                "properties": {
                    "file_id": {"type": "string"},
                    "offset": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
                "required": ["file_id"],
            },
            "R0",
        ),
    ]


def _history_tools() -> list[dict[str, object]]:
    return [
        _tool(
            "search_history",
            "Search history",
            "Search the person's earlier messages with this agent.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                "required": ["query"],
            },
            "R1",
        )
    ]


def _web_tools() -> list[dict[str, object]]:
    return [
        _tool(
            "fetch",
            "Fetch a page",
            "Fetch readable text from an https page on the egress allowlist.",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}, "max_chars": {"type": "integer"}},
                "required": ["url"],
            },
            "R1",
            {"openWorldHint": True, "readOnlyHint": True},
        )
    ]


def _control_tools() -> list[dict[str, object]]:
    return [
        _tool(
            "plan_update",
            "Update the plan",
            "Replace the visible plan for this conversation.",
            {"type": "object", "properties": {"plan": {"type": "array"}}, "required": ["plan"]},
            "R0",
        ),
        _tool(
            "search",
            "Search tools",
            "Find a tool by what it does.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            "R0",
        ),
    ]
