"""Agent keys, the external run path, MCP and A2A."""

import uuid

import httpx
import pytest

from ar_common.errors import NotFoundError
from ar_common.ids import new_id
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.exposure import a2a, keys, mcp_server, runs
from ar_domain.identity.tokens import sha256_hex
from ar_testing.demo import demo_store


def _store() -> ChatService:
    store = demo_store()
    store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    version = store.versions[agent["published_version_id"]]
    definition = dict(version["definition"])
    definition["tools"] = [
        {"server": "session", "version": "*", "include": ["propose_change", "a2a_call"]}
    ]
    definition["contract"] = {"description": "Answers short questions."}
    version["definition"] = definition
    return store


async def _answer(store: ChatService, run_id: uuid.UUID, text: str, names: list[str]) -> None:
    del text, names
    run = store.runs[run_id]
    run["status"] = "completed"
    assistant = store.messages[run["assistant_message_id"]]
    assistant["text"] = "4"
    assistant["status"] = "completed"


def test_key_is_hashed_and_shown_once() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    row, secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Desk",
        rate_limit_rpm=2,
    )
    assert secret.startswith("ara_")
    assert row["secret_hash"] == sha256_hex(secret)
    assert "secret" not in keys.public_key(row)
    assert keys.public_key(row)["prefix"] == secret[4:16]
    found, reason = keys.lookup(store, secret)
    assert reason == "ok"
    assert found is not None and found["id"] == row["id"]
    keys.revoke_key(store, demo_id("tenant"), agent["id"], row["id"], demo_id("admin"))
    _revoked, why = keys.lookup(store, secret)
    assert why == "revoked"
    assert keys.lookup(store, "ara_not-a-real-key")[1] == "missing"
    listed = keys.list_keys(store, demo_id("tenant"), agent["id"])
    assert listed[0]["revoked_at"] is not None
    assert "secret_hash" not in keys.public_key(listed[0])


def test_rate_limit_and_quota_trip() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Tight",
        rate_limit_rpm=1,
        monthly_quota=1,
    )
    assert keys.take_rate(store, row)[0] is True
    assert keys.take_rate(store, row)[0] is False
    assert keys.take_quota(row) is True
    assert keys.take_quota(row) is False


def test_workspace_key_sees_every_published_agent() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    other_id = new_id()
    version_id = new_id()
    store.versions[version_id] = {
        "id": version_id,
        "definition": {"contract": {"description": "Second"}},
    }
    store.agents[other_id] = {
        "id": other_id,
        "tenant_id": demo_id("tenant"),
        "slug": "second",
        "name": "Second",
        "description": "Second",
        "status": "published",
        "disabled": False,
        "published_version_id": version_id,
    }
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Workspace",
        scope="workspace",
    )
    names = [item["name"] for item in mcp_server.tools_list(store, row)["tools"]]
    assert "agent_assistant" in names
    assert "agent_second" in names
    assert len(names) > 2
    scoped, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="One",
    )
    assert [item["name"] for item in mcp_server.tools_list(store, scoped)["tools"]] == [
        "agent_assistant"
    ]


async def test_idempotent_send_starts_one_run_and_hides_other_keys() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        await _answer(store, run_id, text, names)

    store.generate = generate  # type: ignore[method-assign]
    first, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="A",
    )
    second, _other = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="B",
    )
    created = runs.create_conversation(store, first, "assistant")
    conversation_id = uuid.UUID(created["id"])
    reply, replayed = await runs.send_message(
        store, first, "assistant", conversation_id, "What is 2 + 2?", [], "same"
    )
    assert replayed is False
    assert reply["output"] == "4"
    again, replayed = await runs.send_message(
        store, first, "assistant", conversation_id, "What is 2 + 2?", [], "same"
    )
    assert replayed is True
    assert again["id"] == reply["id"]
    runs_for_chat = [
        run for run in store.runs.values() if run.get("conversation_id") == conversation_id
    ]
    assert len(runs_for_chat) == 1
    traced = runs.trace(store, first, "assistant", uuid.UUID(str(reply["id"])))
    assert traced["output"] == "4"
    with pytest.raises(NotFoundError):
        runs.trace(store, second, "assistant", uuid.UUID(str(reply["id"])))


def test_write_returns_approval_required() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Write",
    )
    outcome = runs.execute_write(
        store, row, "assistant", "session.propose_change", {"summary": "rename the record"}
    )
    assert outcome["status"] == "approval_required"
    assert outcome["output"] == "Approval required"
    assert outcome["approval_id"]


def test_agent_card_and_unimplemented_a2a_method() -> None:
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Card",
    )
    card = a2a.agent_card(store, row, "assistant", "http://localhost:8000")
    assert card["url"].endswith("/v1/agents/assistant/a2a")
    assert card["capabilities"]["push_notifications"] is True
    import asyncio

    result = asyncio.run(
        a2a.rpc(
            store,
            row,
            "assistant",
            {"jsonrpc": "2.0", "id": 1, "method": "tasks/resubscribe", "params": {}},
        )
    )
    assert result["error"]["code"] == -32601


def test_remote_a2a_uses_named_secret_and_not_the_model_argument() -> None:
    store = _store()
    from ar_domain.tools.named_secrets import write_named_secret

    write_named_secret(store, demo_id("tenant"), "remote-token", "secret-token")
    seen: dict[str, str] = {}

    def http_send(method: str, url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs.get("headers")
        if isinstance(headers, dict) and "authorization" in headers:
            seen["authorization"] = str(headers["authorization"])
        if method == "GET":
            return httpx.Response(200, json={"url": "http://127.0.0.1:9/a2a", "name": "remote"})
        return httpx.Response(
            200,
            json={
                "result": {
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"kind": "text", "text": "remote says 4"}]}],
                }
            },
        )

    store.http_send = http_send  # type: ignore[attr-defined]
    outcome = a2a.call_remote(
        store,
        {
            "url": "http://127.0.0.1:9/.well-known/agent-card.json",
            "message": "What is 2 + 2?",
            "secret_name": "remote-token",
            "_tenant_id": demo_id("tenant"),
        },
    )
    assert outcome["is_error"] is False
    assert outcome["text"] == "remote says 4"
    assert seen["authorization"] == "Bearer secret-token"
    blocked = a2a.call_remote(
        store, {"url": "http://10.1.1.1/a2a", "message": "no", "_tenant_id": demo_id("tenant")}
    )
    assert blocked["is_error"] is True
    missing_secret = a2a.call_remote(
        store,
        {
            "url": "http://127.0.0.1:9/a2a",
            "message": "hi",
            "secret_name": "missing",
            "_tenant_id": demo_id("tenant"),
        },
    )
    assert missing_secret["code"] == "credential_required"


def test_rotate_upload_quota_and_a2a_cancel() -> None:
    import asyncio

    from ar_common.errors import ArError
    from ar_domain.exposure.tables import A2ATask, AgentApiKey

    assert AgentApiKey.__tablename__ == "agent_api_keys"
    assert A2ATask.__tablename__ == "a2a_tasks"
    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        await _answer(store, run_id, text, names)

    store.generate = generate  # type: ignore[method-assign]
    row, secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Rotate me",
        monthly_quota=1,
    )
    rotated, new_secret = keys.rotate_key(
        store, demo_id("tenant"), agent["id"], row["id"], demo_id("admin")
    )
    assert new_secret != secret
    assert keys.lookup(store, secret)[1] == "revoked"
    assert keys.lookup(store, new_secret)[1] == "ok"
    with pytest.raises(ArError):
        keys.rotate_key(store, demo_id("tenant"), agent["id"], row["id"], demo_id("admin"))
    uploaded = runs.upload_file(store, rotated, "assistant", "note.txt", "text/plain", b"hello")
    assert uploaded["name"] == "note.txt"
    created = runs.create_conversation(store, rotated, "assistant")
    conversation_id = uuid.UUID(created["id"])
    _reply, _replayed = asyncio.run(
        runs.send_message(store, rotated, "assistant", conversation_id, "one", [], "")
    )
    with pytest.raises(ArError):
        asyncio.run(runs.send_message(store, rotated, "assistant", conversation_id, "two", [], ""))
    fresh, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="Tasks",
        monthly_quota=5,
    )
    sent = asyncio.run(
        a2a.send_task(
            store,
            fresh,
            "assistant",
            {"message": {"role": "user", "parts": [{"kind": "text", "text": "hello"}]}},
        )
    )
    fetched = a2a.get_task(store, fresh, uuid.UUID(sent["id"]))
    assert fetched["status"]["state"] == "completed"
    cancelled = a2a.cancel_task(store, fresh, "assistant", uuid.UUID(sent["id"]))
    assert cancelled["status"]["state"] in {"completed", "canceled"}
    with pytest.raises(NotFoundError):
        a2a.get_task(store, fresh, uuid.uuid4())
    unknown = asyncio.run(
        a2a.rpc(store, fresh, "assistant", {"jsonrpc": "2.0", "id": 1, "method": "nope"})
    )
    assert unknown["error"]["code"] == -32601


async def test_mcp_initialize_and_message_call() -> None:
    from ar_common.errors import ArError

    store = _store()
    agent = next(row for row in store.agents.values() if row["slug"] == "assistant")

    async def generate(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        await _answer(store, run_id, text, names)

    store.generate = generate  # type: ignore[method-assign]
    row, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="MCP",
    )
    started = await mcp_server.handle_rpc(
        store, row, {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
    )
    assert started is not None
    assert started["result"]["protocol_version"] == "2025-03-26"
    ping = await mcp_server.handle_rpc(store, row, {"jsonrpc": "2.0", "id": 2, "method": "ping"})
    assert ping == {"jsonrpc": "2.0", "id": 2, "result": {}}
    notice = await mcp_server.handle_rpc(
        store, row, {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )
    assert notice is None
    called = await mcp_server.tools_call(store, row, "agent_assistant", {"message": "hi"})
    assert called["content"][0]["text"] == "4"
    missing = await mcp_server.tools_call(store, row, "agent_missing", {"message": "hi"})
    assert missing["is_error"] is True
    created = runs.create_conversation(store, row, "assistant")
    conversation_id = uuid.UUID(created["id"])
    await runs.send_message(store, row, "assistant", conversation_id, "same", [], "once")
    with pytest.raises(ArError):
        await runs.send_message(store, row, "assistant", conversation_id, "other", [], "once")
    assert a2a.stream_events({"id": "1"})[0]["kind"] == "task"


async def test_durable_exposure_rows_round_trip_sql() -> None:
    from datetime import UTC, datetime

    from ar_domain.durable.m29 import load_exposure, save_exposure

    class Session:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, object]]] = []

        async def execute(self, sql: object, params: dict[str, object]) -> object:
            self.calls.append((str(sql), params))
            return self

        def mappings(self) -> list[dict[str, object]]:
            return []

    session = Session()
    tenant = demo_id("tenant")
    agent = demo_id("admin")
    key_id = uuid.uuid4()
    now_row = {
        "id": key_id,
        "tenant_id": tenant,
        "agent_id": agent,
        "created_by_user_id": agent,
        "label": "Desk",
        "prefix": "abc",
        "secret_hash": "hash",
        "scope": "nope",
        "rate_limit_rpm": 3,
        "monthly_quota": 4,
        "month_stamp": "2026-11",
        "month_count": 1,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    await save_exposure(
        session,  # type: ignore[arg-type]
        {
            "agent_api_keys": [now_row, {"id": "nope"}],
            "agent_api_idempotency": [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant,
                    "key_id": key_id,
                    "idempotency_key": "once",
                    "request_hash": "abc",
                    "response": {"output": "4"},
                    "state": "weird",
                    "created_at": now_row["created_at"],
                }
            ],
            "agent_api_grants": [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant,
                    "key_id": key_id,
                    "agent_id": agent,
                    "conversation_id": uuid.uuid4(),
                    "created_at": now_row["created_at"],
                }
            ],
            "a2a_tasks": [
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant,
                    "agent_id": agent,
                    "key_id": key_id,
                    "conversation_id": uuid.uuid4(),
                    "state": "completed",
                    "output_text": "6",
                    "artifacts": [],
                    "created_at": now_row["created_at"],
                    "updated_at": now_row["updated_at"],
                }
            ],
        },
    )
    assert any("INSERT INTO agent_api_keys" in sql for sql, _params in session.calls)
    assert any(params.get("scope") == "agent" for _sql, params in session.calls)
    store = _store()
    await load_exposure(session, store, tenant)  # type: ignore[arg-type]
