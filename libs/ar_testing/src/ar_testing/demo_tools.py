"""The demo tenant's tool rows: its settings, three stand-in servers, two agents, one review.

A test, the browser-test harness and the eval gym work on a tenant with fixed ids that
has no database behind it. Its tickets, pet store and warehouse servers are the stand-ins
in :mod:`ar_testing.tool_stand_ins`, and the agents here are bound to them. The product
builds none of this: an install's servers, agents and settings are rows a person made.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from ar_common.time import utcnow
from ar_domain.agents.logic import assistant_definition
from ar_domain.chat.service import demo_id
from ar_domain.runs.logic import DEFAULT_RUN_BUDGET
from ar_domain.tools.openapi_import import operations_from
from ar_domain.tools.seed_tools import approved_server, tool_row
from ar_testing.approval_tool import offer_approval_tool
from ar_testing.tool_stand_ins import PETSTORE, TICKETS, TOKEN_URL, WAREHOUSE

if TYPE_CHECKING:
    import uuid


def seed_demo_tools(store: Any) -> None:
    """Add the demo tenant's tool rows to ``store``. A second call adds nothing."""
    tenant = demo_id("tenant")
    admin = demo_id("admin")
    _settings(store, tenant)
    # A test that builds its store the way staging does asks for a tenant with no
    # stand-in servers: it has the settings, the review and the analyst only.
    if getattr(store, "fake_models_allowed", True):
        provider = _provider(store, tenant, admin)
        _tickets(store, tenant, admin, provider)
        _petstore(store, tenant, admin)
        _warehouse(store, tenant, admin)
        _desk(store, tenant, demo_id("builder"))
        offer_approval_tool(store)
    _reviews(store, tenant)
    _analyst(store, tenant, admin)


PETSTORE_DOCUMENT: dict[str, object] = {
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


def _settings(store: Any, tenant: uuid.UUID) -> None:
    current = store.tenant_settings.setdefault(tenant, {})
    if not isinstance(current, dict):
        return
    security = current.setdefault("security", {})
    if isinstance(security, dict):
        security.setdefault("allow_self_review", True)
        security.setdefault("require_step_up_for_w3", True)
        security.setdefault("require_step_up_for_signoff", True)
    features = current.setdefault("features", {})
    if isinstance(features, dict):
        features.setdefault("web_fetch", True)
        features.setdefault("custom_rego", False)
    approvals = current.setdefault("approvals", {})
    if isinstance(approvals, dict):
        approvals.setdefault("default_ttl_s", 86400)
    current.setdefault("egress_allowlist", ["example.com"])
    roles = getattr(store, "user_roles", None)
    if isinstance(roles, dict):
        roles.setdefault(demo_id("admin"), {"tenant_admin"})
        roles.setdefault(demo_id("builder"), {"builder"})
        roles.setdefault(demo_id("approver"), {"approver"})
        roles.setdefault(demo_id("member"), {"member"})
    names = getattr(store, "display_names", None)
    if isinstance(names, dict):
        names.setdefault(demo_id("admin"), "Dev Admin")
        names.setdefault(demo_id("builder"), "Dev Builder")
        names.setdefault(demo_id("approver"), "Dev Approver")
        names.setdefault(demo_id("member"), "Dev Member")
    for key in ("admin", "builder", "approver", "member"):
        store.user_emails.setdefault(demo_id(key), f"{key}@dev.local")
        store.user_statuses.setdefault(demo_id(key), "active")


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
            "token_url": TOKEN_URL,
            "client_id": "ar-tickets",
            "default_scopes": ["tickets.write"],
            "extra": {},
            "status": "active",
            "created_by": admin,
            "created_at": now,
            "updated_at": now,
        }
    return provider_id


def _tickets(store: Any, tenant: uuid.UUID, admin: uuid.UUID, provider: uuid.UUID) -> None:
    approved_server(
        store,
        tenant_id=tenant,
        owner=admin,
        slug="tickets",
        name="Tickets",
        description="Files a ticket on the workspace tracker.",
        kind="remote_mcp",
        endpoint=TICKETS,
        auth_mode="user_oauth",
        provider_id=provider,
        tools=[
            tool_row(
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
            tool_row(
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


def _petstore(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    parsed = operations_from(PETSTORE_DOCUMENT)
    tools = [
        tool_row(
            str(item["name"]),
            str(item["title"]),
            str(item["description"]),
            item["input_schema"] if isinstance(item["input_schema"], dict) else {},
            str(item["risk_class"]),
            annotations=item["annotations"] if isinstance(item["annotations"], dict) else {},
        )
        for item in parsed
    ]
    approved_server(
        store,
        tenant_id=tenant,
        owner=admin,
        slug="petstore",
        name="Petstore",
        description="Sample OpenAPI tools from the Petstore document.",
        kind="openapi",
        endpoint=PETSTORE,
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
        store.secret_values[secret_id] = WAREHOUSE.encode()
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
        tool_row(
            "list_tables",
            "List tables",
            "List tables on the warehouse connection.",
            {"type": "object", "properties": {}},
            "R0",
        ),
        tool_row(
            "describe_table",
            "Describe a table",
            "Describe one allowlisted table.",
            {"type": "object", "properties": {"table": {"type": "string"}}, "required": ["table"]},
            "R0",
        ),
        tool_row(
            "run_query",
            "Run a query",
            "Run one read-only select against the warehouse.",
            {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
            "R1",
        ),
    ]
    approved_server(
        store,
        tenant_id=tenant,
        owner=admin,
        slug=slug,
        name="Warehouse",
        description="Read-only questions over the orders table.",
        kind="sql",
        endpoint=WAREHOUSE,
        auth_mode="none",
        provider_id=None,
        tools=tools,
        config={"sql": {"data_connection_id": str(connection_id)}},
    )


def _reviews(store: Any, tenant: uuid.UUID) -> None:
    """One queue and one item so the reviews screen is not empty."""
    queues = getattr(store, "review_queues", None)
    items = getattr(store, "review_items", None)
    if not isinstance(queues, dict) or not isinstance(items, dict):
        return
    queue_id = demo_id("queue-output")
    if queue_id in queues:
        return
    now = utcnow()
    subject_id = demo_id("sample-output")
    statement = "I reviewed the sample output."
    queues[queue_id] = {
        "id": queue_id,
        "tenant_id": tenant,
        "slug": "output",
        "name": "Output review",
        "subject_type": "artifact",
        "levels": [{"level": 1, "role_key": "", "required_count": 1}],
        "statement_template": "I reviewed {title} ({content_hash}).",
        "created_at": now,
        "updated_at": now,
    }
    items[demo_id("review-sample")] = {
        "id": demo_id("review-sample"),
        "tenant_id": tenant,
        "queue_id": queue_id,
        "subject_type": "artifact",
        "subject_id": subject_id,
        "subject_ref": {},
        "content_hash": hashlib.sha256(f"artifact:{subject_id}".encode()).hexdigest(),
        "statement_text": statement,
        "statement_hash": hashlib.sha256(statement.encode()).hexdigest(),
        "status": "pending",
        "current_level": 1,
        "levels": [{"level": 1, "role_key": "", "required_count": 1}],
        "preparer_principal_type": "user",
        "preparer_principal_id": demo_id("builder"),
        "agent_id": None,
        "expires_at": None,
        "created_at": now,
        "updated_at": now,
    }


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


def _analyst(store: Any, tenant: uuid.UUID, admin: uuid.UUID) -> None:
    from ar_domain.agents.service import AgentLifecycle  # noqa: PLC0415

    for agent in store.agents.values():
        if agent.get("tenant_id") == tenant and agent.get("slug") == "revenue-analyst":
            return
    AgentLifecycle(store)._insert(
        tenant,
        admin,
        slug="revenue-analyst",
        name="Revenue analyst",
        description="Charts a spreadsheet on the computer.",
        visibility="tenant",
        published=True,
        definition={
            "persona": {
                "display_name": "Revenue analyst",
                "greeting": "Attach a spreadsheet and I will chart it.",
            },
            "instructions": "Use the computer to chart the attached spreadsheet.",
            "starter_prompts": ["Analyse the attached CSV and chart revenue by month"],
            "model": {"alias": "reasoning", "fast_alias": "fast", "vision_alias": "vision"},
            "tools": [
                {"server": "general", "include": ["*"]},
                {"server": "files", "include": ["*"]},
                {"server": "browser", "include": ["*"]},
            ],
            "sandbox": {"enabled": True, "template": "python-data", "scope": "conversation"},
            "budget": {
                "max_steps": 8,
                "max_tokens": DEFAULT_RUN_BUDGET["max_tokens"],
                "max_cost_micros": 1_000_000,
                "max_wall_clock_s": 120,
                "max_tool_calls": 4,
                "max_parallel_tool_calls": 1,
            },
        },
    )
