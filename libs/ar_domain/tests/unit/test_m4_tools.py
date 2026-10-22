"""Tool registry, credentials, pipeline and the in-process desk agent."""

import uuid

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ar_common.errors import ArError, ErrorCode
from ar_common.wrapping import wrap_tool_result
from ar_domain.agents.access import Actor
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.tools.credentials import CredentialBook
from ar_domain.tools.drift import check_drift
from ar_domain.tools.logic import hash_embedding, propose_risk
from ar_domain.tools.openapi_import import operations_from
from ar_domain.tools.pipeline import ToolPipeline
from ar_domain.tools.registry import ToolRegistry
from ar_domain.tools.sql_guard import SqlRejected, check_sql

PET = {
    "openapi": "3.1.0",
    "paths": {
        "/pets": {
            "get": {"operationId": "listPets", "summary": "List pets"},
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                    },
                },
            },
        },
        "/pets/{petId}": {
            "delete": {
                "operationId": "deletePet",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
            }
        },
    },
    "components": {
        "schemas": {"Pet": {"type": "object", "properties": {"name": {"type": "string"}}}}
    },
}


def _actor(user: str = "admin") -> Actor:
    return Actor(demo_id("tenant"), demo_id(user), PERMISSION_KEYS, display_name="Dev Admin")


def test_openapi_risk_follows_the_spec() -> None:
    tools = {item["name"]: item for item in operations_from(PET)}
    assert tools["list_pets"]["risk_class"] == "R0"
    assert tools["create_pet"]["risk_class"] == "W2"
    assert tools["delete_pet"]["risk_class"] == "W3"
    assert propose_risk("sql") == "R1"
    assert propose_risk("remote", annotations={"destructiveHint": True}) == "W3"


def test_sql_guard_rejects_writes_and_limits_selects() -> None:
    limited = check_sql(
        "SELECT id FROM public.orders", allow_tables={"public.orders"}, deny_columns=set()
    )
    assert "LIMIT" in limited.upper()
    with pytest.raises(SqlRejected):
        check_sql("DROP TABLE public.orders", allow_tables={"public.orders"}, deny_columns=set())
    with pytest.raises(SqlRejected):
        check_sql("SELECT pg_sleep(1)", allow_tables={"public.orders"}, deny_columns=set())
    with pytest.raises(SqlRejected):
        check_sql(
            "SELECT password FROM public.orders",
            allow_tables={"public.orders"},
            deny_columns={"public.orders.password"},
        )


def test_seeded_servers_and_files_can_be_bound() -> None:
    store = ChatService()
    life_actor = _actor()
    registry = ToolRegistry(store)
    slugs = {row["slug"] for row in registry.list_servers(life_actor)}
    assert {"files", "conversations", "web", "control", "tickets", "petstore", "warehouse"} <= slugs
    from ar_domain.agents.service import AgentLifecycle

    life = AgentLifecycle(store)
    created = life.create(life_actor, slug="reader", name="Reader", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    life.save_draft(
        life_actor,
        agent_id,
        {
            "instructions": "Read files.",
            "tools": [{"server": "files", "version": "*", "include": ["*"]}],
        },
    )
    published = life.publish(life_actor, agent_id, change_note="files exist")
    assert published["status"] == "published"


def test_register_review_and_four_eyes() -> None:
    store = ChatService()
    admin = _actor()
    registry = ToolRegistry(store)
    created = registry.create_server(
        admin,
        {
            "slug": "echo",
            "name": "Echo",
            "kind": "remote_mcp",
            "version": {"version": "1.0.0", "endpoint_url": "memory://echo", "auth_mode": "none"},
        },
    )
    server_id = uuid.UUID(created["id"])
    version_id = uuid.UUID(str(created["versions"][0]["id"]))
    version = registry.get_version(admin, server_id, version_id)
    tool_version_id = uuid.UUID(str(version["tools"][0]["id"]))
    registry.patch_tool(admin, server_id, version_id, tool_version_id, {"risk_class": "R0"})
    registry.submit(admin, server_id, version_id)
    store.tenant_settings[admin.tenant_id]["security"]["allow_self_review"] = False
    with pytest.raises(ArError) as denied:
        registry.approve(admin, server_id, version_id, "ok")
    assert denied.value.code is ErrorCode.FORBIDDEN
    store.tenant_settings[admin.tenant_id]["security"]["allow_self_review"] = True
    approved = registry.approve(admin, server_id, version_id, "ok")
    assert approved["review_status"] == "approved"
    with pytest.raises(ArError):
        registry.patch_tool(admin, server_id, version_id, tool_version_id, {"risk_class": "R1"})
    outsider = Actor(uuid.uuid4(), uuid.uuid4(), PERMISSION_KEYS)
    with pytest.raises(ArError) as hidden:
        registry.get_server(outsider, server_id)
    assert hidden.value.code is ErrorCode.NOT_FOUND


def test_oauth_cache_is_ciphertext_and_refresh_rotates() -> None:
    store = ChatService()
    admin = _actor()
    book = CredentialBook(store)
    provider = book.create_provider(
        admin,
        {
            "slug": "demo",
            "name": "Demo",
            "authorize_url": "https://tickets.example/authorize",
            "token_url": "memory://oauth",
        },
    )
    started = book.start(admin, uuid.UUID(provider["id"]))
    assert "code_challenge=" in str(started["authorize_url"])
    import asyncio

    grant = asyncio.run(book.callback("code-1", str(started["state"])))
    assert grant["status"] == "active"
    token = asyncio.run(book.access_token_for(admin, uuid.UUID(provider["id"])))
    assert token.startswith("access-")
    sealed = next(iter(store.token_cache.values()))
    assert token.encode() not in sealed
    with pytest.raises(ArError):
        asyncio.run(book.callback("invalid", "missing"))


@pytest.mark.asyncio
async def test_desk_creates_a_ticket_and_counts_orders() -> None:
    store = ChatService()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    conversation = store.create_conversation(tenant, user, uuid.UUID(str(desk["id"])))
    conversation_id = uuid.UUID(str(conversation["id"]))
    posted = store.post_message(
        tenant,
        user,
        conversation_id,
        "File a ticket: the printer on floor 3 is jammed",
        schedule=False,
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    await store.generate(run_id, "File a ticket: the printer on floor 3 is jammed", [])
    assert "TCK-1001" in str(store.runs[run_id]["result_summary"])
    assert any(row.get("action") == "tool.called" for row in store.audit_log)
    counted = store.post_message(
        tenant, user, conversation_id, "How many orders are in the warehouse?", schedule=False
    )
    count_id = uuid.UUID(str(counted["run"]["id"]))
    await store.generate(count_id, "How many orders are in the warehouse?", [])
    assert store.runs[count_id]["result_summary"] == "3"
    calls = [row for row in store.tool_calls.values() if row.get("run_id") == run_id]
    assert calls and calls[0]["qualified_name"] == "tickets.create_ticket"


def test_invalid_arguments_do_not_call_the_server() -> None:
    store = ChatService()
    version = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "tickets.create_ticket"
    )
    before = len(store.tickets)
    result = ToolPipeline(store).execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "synthetic": True,
            "tool_version_id": version["id"],
            "arguments": {},
            "model_call_id": "bad",
        }
    )
    assert result["error"]["code"] == "validation_failed"
    assert len(store.tickets) == before


def test_w2_is_denied_until_approvals_exist() -> None:
    store = ChatService()
    version = next(row for row in store.tool_versions.values() if row.get("name") == "create_pet")
    result = ToolPipeline(store).execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "agent_version_id": next(
                row["published_version_id"]
                for row in store.agents.values()
                if row["slug"] == "desk"
            ),
            "tool_version_id": version["id"],
            "arguments": {"body": {"name": "cat"}},
            "model_call_id": "pet",
        }
    )
    assert result["error"]["code"] == "policy_denied"
    dry = ToolPipeline(store).execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "synthetic": True,
            "dry_run": True,
            "tool_version_id": version["id"],
            "arguments": {"body": {"name": "cat"}},
            "model_call_id": "dry",
        }
    )
    assert dry["status"] == "succeeded"


def test_manifest_drift_blocks_calls() -> None:
    store = ChatService()
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "tickets")
    version = store.tool_server_versions[server["current_version_id"]]
    version["upstream_manifest"] = {"tools": ["create_ticket", "list_tickets", "extra"]}
    changed = check_drift(store)
    assert changed and server["status"] == "pending_review"
    tool = next(
        row
        for row in store.tool_versions.values()
        if row.get("qualified_name") == "tickets.create_ticket"
    )
    result = ToolPipeline(store).execute(
        {
            "tenant_id": demo_id("tenant"),
            "user_id": demo_id("admin"),
            "synthetic": True,
            "tool_version_id": tool["id"],
            "arguments": {"title": "later"},
            "model_call_id": "drift",
        }
    )
    assert result["error"]["code"] == "tool_manifest_drift"


def test_tool_search_activates_past_thirty_tools() -> None:
    store = ChatService()
    desk = next(row for row in store.agents.values() if row.get("slug") == "desk")
    version = store.versions[desk["published_version_id"]]
    definition = version["definition"]
    names = []
    server = next(row for row in store.tool_servers.values() if row.get("slug") == "files")
    current = server["current_version_id"]
    for index in range(50):
        name = f"extra_{index}"
        tool_id = uuid.uuid4()
        version_id = uuid.uuid4()
        store.tool_defs[tool_id] = {
            "id": tool_id,
            "tenant_id": None,
            "tool_server_id": server["id"],
            "name": name,
            "disabled_at": None,
        }
        description = "order count helper" if index == 7 else f"unrelated tool {index}"
        embedding = hash_embedding("order count") if index == 7 else hash_embedding(description)
        store.tool_versions[version_id] = {
            "id": version_id,
            "tool_id": tool_id,
            "tool_server_version_id": current,
            "name": name,
            "qualified_name": f"files.{name}",
            "description": description,
            "input_schema": {"type": "object"},
            "risk_class": "R0",
            "data_classification": "internal",
            "embedding": embedding,
            "disabled_at": None,
        }
        names.append(name)
    definition["tools"] = [{"server": "files", "version": "*", "include": ["*"]}]
    catalog = ToolPipeline(store).resolve_catalog(
        agent_version_id=version["id"], user_id=demo_id("admin"), query="order count"
    )
    assert catalog["tool_search_active"] is True
    assert len(catalog["tools"]) <= 12
    assert catalog["tools"][0]["qualified_name"] == "files.extra_7"


@given(st.text(min_size=0, max_size=200))
def test_wrapping_cannot_be_closed_early(content: str) -> None:
    wrapped = wrap_tool_result(tool="files.read", call_id="1", content=content, nonce="n")
    assert wrapped.count("</tool_result>") == 1
    assert wrapped.startswith('<tool_result tool="files.read"')
