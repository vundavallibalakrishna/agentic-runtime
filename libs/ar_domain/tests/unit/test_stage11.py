"""Stage 11 robustness. Proof is unit, or contract when HTTP is recorded."""

from __future__ import annotations

import uuid
from datetime import timedelta

import httpx
import pytest

from ar_common.errors import ArError, NotFoundError
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.connectors.book import ConnectorBook
from ar_domain.connectors.dispatch import dispatch_connector
from ar_domain.conversations.summary import read_summary, refresh_summary, write_summary
from ar_domain.documents.ocr_cloud import read_cloud
from ar_domain.exposure import a2a
from ar_domain.exposure.grpc_a2a import grpc_call
from ar_domain.identity.guests import open_agent_turn
from ar_domain.identity.membership import memberships, password_matches
from ar_domain.identity.passwords import hash_password, verify_password
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.recovery import confirm_reset, remember_person, request_reset
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.qdrant_memory import MemoryPoint, MemoryQdrant, MemoryQdrantDouble
from ar_domain.notifications.dispatch import notify_user, subscribe, unsubscribe
from ar_domain.records.memory import bucket
from ar_domain.sandboxes.runtime import _mime
from ar_domain.tools.handlers import dispatch as run_tool
from ar_domain.tools.named_secrets import write_named_secret
from ar_domain.tools.seed_tools import seed
from ar_testing.demo import demo_store


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


def test_workspace_memory_can_be_edited_and_deleted() -> None:
    store = demo_store()
    actor = _actor()
    book = MemoryBook(store)
    created = book.create_user(
        actor, {"content": "The workspace prefers short answers.", "scope": "workspace"}
    )
    listed = book.list_user(actor, scope="workspace")
    assert created["id"] in {row["id"] for row in listed}
    patched = book.patch_user(
        actor, uuid.UUID(str(created["id"])), {"content": "The workspace prefers brief answers."}
    )
    assert "brief" in str(patched["content"])
    book.delete_user(actor, uuid.UUID(str(created["id"])))
    assert book.list_user(actor, scope="workspace") == []


def test_password_reset_stores_a_hash_and_mails_the_token() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=tenant,
        user_id=user,
        password_hash=hash_password("old-password"),
    )
    request_reset(store, "ada@example.com")
    token = store.outbox[-1]["body"]
    assert token not in {row["token_hash"] for row in store.password_resets.values()}
    confirm_reset(store, token, "new-password-1")
    person = next(iter(store.local_people.values()))
    assert verify_password(str(person["password_hash"]), "new-password-1")
    assert store.audit_log[-1]["action"] == "auth.password_reset"


def test_one_password_can_match_two_tenants() -> None:
    store = demo_store()
    secret = hash_password("shared-password")
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        password_hash=secret,
        tenant_name="North",
    )
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        password_hash=secret,
        tenant_name="South",
    )
    found = password_matches(store, "ada@example.com", "shared-password")
    assert [row["tenant_name"] for row in found] == ["North", "South"]


def test_recorded_gmail_list_is_contract() -> None:
    store = demo_store()
    seed(store, tenant=False)
    actor = _actor()
    ConnectorBook(store).install(
        actor,
        "gmail",
        {"connection_name": "mail", "kind": "bearer", "secret": "token"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/profile"):
            return httpx.Response(200, json={"emailAddress": "ada@example.com"})
        return httpx.Response(200, json={"messages": [{"id": "m1"}]})

    store.connector_transport = httpx.MockTransport(handler)  # type: ignore[attr-defined]
    result = dispatch_connector(
        store,
        "gmail_list",
        {"q": "newer_than:1d", "_tenant_id": actor.tenant_id, "_user_id": actor.user_id},
    )
    assert result["is_error"] is False
    assert result["structured"]["items"][0]["id"] == "m1"


def test_cloud_ocr_uses_a_named_secret_and_a_recorded_body() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    write_named_secret(store, tenant, "ocr_aws", "https://ocr.example/textract")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "ocr.example"
        return httpx.Response(200, json={"text": "recorded page"})

    found = read_cloud(
        store,
        tenant,
        "aws_textract",
        b"page",
        transport=httpx.MockTransport(handler),
    )
    assert found is not None
    assert found["structured"]["proof"] == "contract"  # type: ignore[index]
    assert found["text"] == "recorded page"


def test_qdrant_memory_hybrid_keeps_the_embedding_model() -> None:
    index = MemoryQdrant(MemoryQdrantDouble())
    fact_id = uuid.uuid4()
    tenant = demo_id("tenant")
    index.upsert(
        MemoryPoint(
            fact_id=fact_id,
            tenant_id=tenant,
            scope="workspace",
            text="brief answers",
            dense=[0.1, 0.2],
            embedding_model_id="embed-1",
        )
    )
    hits = index.search(tenant_id=tenant, query="brief", dense=[0.1, 0.2])
    assert hits[0]["embedding_model_id"] == "embed-1"
    assert hits[0]["fact_id"] == str(fact_id)


def test_resubscribe_and_grpc_return_the_task() -> None:
    import asyncio

    from ar_domain.exposure import keys

    store = demo_store()
    store.ensure_assistant(demo_id("tenant"), demo_id("admin"))

    async def _answer(run_id: uuid.UUID, text: str, names: list[str]) -> None:
        del text, names
        run = store.runs[run_id]
        run["status"] = "completed"
        assistant = store.messages[run["assistant_message_id"]]
        assistant["text"] = "hello"
        assistant["status"] = "completed"

    store.generate = _answer  # type: ignore[method-assign]
    agent = next(row for row in store.agents.values() if row.get("slug") == "assistant")
    key, _secret = keys.create_key(
        store,
        tenant_id=demo_id("tenant"),
        agent_id=agent["id"],
        user_id=demo_id("admin"),
        label="stage11",
    )
    sent = asyncio.run(
        a2a.rpc(
            store,
            key,
            "assistant",
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "message/send",
                "params": {
                    "message": {"role": "user", "parts": [{"kind": "text", "text": "hello"}]}
                },
            },
        )
    )
    task_id = sent["result"]["id"]
    again = asyncio.run(
        a2a.rpc(
            store,
            key,
            "assistant",
            {"jsonrpc": "2.0", "id": 2, "method": "tasks/resubscribe", "params": {"id": task_id}},
        )
    )
    assert again["result"]["resubscribed"] is True
    payload, status = asyncio.run(
        grpc_call(store, key, "assistant", "a2a.v1.A2AService/ResubscribeToTask", {"id": task_id})
    )
    assert status == 0
    assert payload["id"] == task_id
    missing, code = asyncio.run(grpc_call(store, key, "assistant", "a2a.v1.A2AService/Nope", {}))
    assert code == 12
    assert "unimplemented" in str(missing["message"])


def test_agent_can_create_a_scheduled_routine() -> None:
    store = demo_store()
    seed(store)
    tenant = demo_id("tenant")
    user = demo_id("admin")
    agent_id = next(row["id"] for row in store.agents.values() if row.get("tenant_id") == tenant)
    result = run_tool(
        store,
        "builtin://routines",
        "create",
        {
            "_tenant_id": tenant,
            "_user_id": user,
            "name": "Hourly note",
            "instructions": "Write one line.",
            "trigger_type": "schedule",
            "cron": "0 * * * *",
            "agent_id": agent_id,
        },
        "",
    )
    assert result["is_error"] is False
    assert store.temporal_schedules


def test_guest_reaches_only_the_granted_agent() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    guest = uuid.uuid4()
    agent_id = next(
        row["id"]
        for row in store.agents.values()
        if row.get("tenant_id") == tenant and row.get("status") == "published"
    )
    grant_id = uuid.uuid4()
    bucket(store, "guest_grants")[grant_id] = {
        "id": grant_id,
        "tenant_id": tenant,
        "guest_id": guest,
        "expires_at": utcnow() + timedelta(days=1),
        "scope": {"agent_ids": [str(agent_id)]},
    }
    actor = Actor(tenant, guest, frozenset(), kind="guest")
    posted = open_agent_turn(store, actor, agent_id, "Hello")
    assert posted["run"]["id"]
    other = uuid.uuid4()
    store.agents[other] = {
        "id": other,
        "tenant_id": tenant,
        "name": "Other",
        "status": "published",
        "disabled": False,
    }
    with pytest.raises(ArError, match="guest_forbidden"):
        open_agent_turn(store, actor, other, "No")


def test_push_and_email_notice_stay_pending_without_a_vapid_secret() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    created = subscribe(
        store,
        tenant_id=tenant,
        user_id=user,
        endpoint="https://push.example/sub",
    )
    note = notify_user(
        store,
        tenant_id=tenant,
        user_id=user,
        title="Done",
        body="The run finished.",
        email="ada@example.com",
    )
    assert created["endpoint"] == "https://push.example/sub"
    assert note["push"]["pending"] is True
    assert store.outbox[-1]["subject"] == "Done"


def test_a_failed_run_with_a_checkpoint_can_resume() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    run_id = uuid.uuid4()
    store.runs[run_id] = {
        "id": run_id,
        "tenant_id": tenant,
        "user_id": user,
        "status": "failed",
        "conversation_id": uuid.uuid4(),
        "checkpoint": {"worker_loop": {"step": 1}},
    }
    resumed = store.resume_run(tenant, user, run_id)
    assert resumed["status"] == "running"


def test_reset_rejects_unknown_short_expired_and_spent_tokens() -> None:
    store = demo_store()
    request_reset(store, "missing@example.com")
    assert getattr(store, "outbox", None) in (None, [])
    tenant = demo_id("tenant")
    user = demo_id("admin")

    class Account:
        password_hash = ""

    account = Account()
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=tenant,
        user_id=user,
        password_hash=hash_password("old-password"),
        user=account,
    )
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        password_hash=hash_password("other-password"),
        tenant_name="South",
    )
    mailed: list[dict[str, str]] = []
    store.mailer = mailed.append  # type: ignore[attr-defined]
    request_reset(store, "ada@example.com")
    token = mailed[-1]["body"]
    with pytest.raises(ArError, match="too short"):
        confirm_reset(store, token, "short")
    assert password_matches(store, "ada@example.com", "nope") == []
    assert memberships(store, "ada@example.com")
    person = store.local_people[str(user)]
    person["permissions"] = "not-a-list"
    assert password_matches(store, "ada@example.com", "old-password")[0]["permissions"] == []
    row = next(iter(store.password_resets.values()))
    row["expires_at"] = utcnow() - timedelta(minutes=1)
    with pytest.raises(ArError, match="expired"):
        confirm_reset(store, token, "new-password-1")
    row["expires_at"] = utcnow() + timedelta(hours=1)
    row["user_id"] = uuid.uuid4()
    with pytest.raises(ArError, match="not valid"):
        confirm_reset(store, token, "new-password-1")
    row["user_id"] = user
    confirm_reset(store, token, "new-password-1")
    assert account.password_hash
    with pytest.raises(ArError, match="not valid"):
        confirm_reset(store, token, "new-password-2")
    with pytest.raises(ArError, match="not valid"):
        confirm_reset(store, "not-a-token", "new-password-2")


def test_rolling_summary_reads_writes_and_refreshes() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    conversation_id = uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": tenant,
        "rolling_summary": "",
    }
    for index in range(6):
        message_id = uuid.uuid4()
        store.messages[message_id] = {
            "id": message_id,
            "conversation_id": conversation_id,
            "created_at": f"2026-01-0{index + 1}T00:00:00Z",
            "role": "user",
            "text": f"line {index}",
        }
    written = write_summary(store, tenant, conversation_id, "  earlier  ")
    assert written["summary"] == "earlier"
    refreshed = refresh_summary(store, tenant, conversation_id)
    assert refreshed["conversationId"] == str(conversation_id)
    assert refreshed["summary"]
    with pytest.raises(NotFoundError):
        read_summary(store, uuid.uuid4(), conversation_id)


def test_cloud_ocr_stays_quiet_when_the_call_fails() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    assert read_cloud(store, tenant, "no_such_engine", b"page") is None
    assert read_cloud(store, tenant, "google_document_ai", b"page") is None

    def fail(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.ConnectError("down")

    assert (
        read_cloud(
            store,
            tenant,
            "google_document_ai",
            b"page",
            transport=httpx.MockTransport(fail),
        )
        is None
    )

    def rejected(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(400, json={"text": "no"})

    assert (
        read_cloud(
            store,
            tenant,
            "azure_document_intelligence",
            b"page",
            transport=httpx.MockTransport(rejected),
        )
        is None
    )

    def empty(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=["not-a-page"])

    assert (
        read_cloud(
            store,
            tenant,
            "aws_textract",
            b"page",
            transport=httpx.MockTransport(empty),
        )
        is None
    )


def test_push_resubscribe_and_a_vapid_secret_marks_delivery() -> None:
    store = demo_store()
    tenant = demo_id("tenant")
    user = demo_id("admin")
    created = subscribe(store, tenant_id=tenant, user_id=user, endpoint="https://push.example/sub")
    again = subscribe(
        store,
        tenant_id=tenant,
        user_id=user,
        endpoint="https://push.example/sub",
        encoding="",
    )
    assert again["id"] == created["id"]
    subscription_id = uuid.UUID(str(created["id"]))
    assert unsubscribe(store, tenant_id=uuid.uuid4(), subscription_id=subscription_id) is False
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    write_named_secret(store, tenant, "web_push_vapid_private", pem)

    def _accepted(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"].startswith("vapid ")
        return httpx.Response(201)

    store.push_transport = httpx.MockTransport(_accepted)  # type: ignore[attr-defined]
    note = notify_user(store, tenant_id=tenant, user_id=user, title="Done", body="ok")
    assert note["push"]["delivered"] == 1
    assert note["email"] is False
    assert unsubscribe(store, tenant_id=tenant, subscription_id=subscription_id) is True
    assert unsubscribe(store, tenant_id=tenant, subscription_id=uuid.uuid4()) is False


def test_grpc_maps_a_task_error_to_status_three() -> None:
    import asyncio

    store = demo_store()
    payload, status = asyncio.run(
        grpc_call(store, {}, "assistant", "a2a.v1.A2AService/GetTask", {})
    )
    assert status == 3
    assert payload["message"]


def test_office_artifacts_have_download_types() -> None:
    assert _mime("chart.png") == "image/png"
    assert _mime("sheet.xlsx").endswith("sheet")
    assert _mime("note.docx").endswith("document")
    assert _mime("brief.pdf") == "application/pdf"
