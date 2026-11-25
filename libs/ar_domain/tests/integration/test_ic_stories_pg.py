"""One Postgres round trip for each use-case story.

Label: integration
"""

from __future__ import annotations

import os
import subprocess
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.approvals.logic import can_decide
from ar_domain.approvals.review_link import decide_review, issue_review_token, link_deadline
from ar_domain.approvals.service import ApprovalBook
from ar_domain.chat.service import ChatService
from ar_domain.config_docs.book import SettingsBook
from ar_domain.documents.library import note_extraction_decision
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.identity.seed import apply
from ar_domain.tools.extensions import dispatch_extensions
from ar_domain.tools.settings_tool import dispatch_settings
from ar_domain.webhooks.book import WebhookBook
from ar_domain.webhooks.delivery import dispatch_public_event

pytestmark = pytest.mark.integration


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def _ready(database_url: str) -> tuple[ChatService, Actor]:
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    await engine.dispose()
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    tenant = store.tenant_binding.tenant_id  # type: ignore[union-attr]
    admin = next(iter(store.tenant_binding.users.values()))  # type: ignore[union-attr]
    store.user_statuses[admin] = "active"
    return store, Actor(tenant, admin, PERMISSION_KEYS, display_name="Admin")


async def _reload(database_url: str) -> ChatService:
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


def _run_and_call(store: ChatService, actor: Actor) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A run and a tool call the approval's foreign keys can point at."""
    agent = store.ensure_assistant(actor.tenant_id, actor.user_id)
    posted = store.create_api_run(
        actor.tenant_id,
        actor.user_id,
        uuid.UUID(str(agent["id"])),
        "review",
        callback_url=None,
        on_behalf_of=None,
        allow_on_behalf=False,
        permissions=["chat:use"],
    )
    run = posted["run"]
    assert isinstance(run, dict)
    run_id = uuid.UUID(str(run["id"]))
    call_id = uuid.uuid4()
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": actor.tenant_id,
        "run_id": run_id,
        "qualified_name": "pack.example",
        "args_hash": "hash-1",
        "status": "awaiting_approval",
        "idempotency_key": f"{run_id}:{call_id}",
        "created_at": utcnow(),
    }
    return run_id, uuid.UUID(str(agent["id"])), call_id


async def test_a_review_link_decision_is_still_there_after_reload(database_url: str) -> None:
    store, actor = await _ready(database_url)
    run_id, agent_id, call_id = _run_and_call(store, actor)
    row = ApprovalBook(store).create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=agent_id,
        tool_call_id=call_id,
        qualified_name="pack.example",
        risk_class="W2",
        args_hash="hash-1",
        arguments={"target_date": "2026-01-02"},
        requirement={"approvers": {"mode": "requester"}, "ttl_s": 3600},
        reasons=["ask"],
        preview={"title": "Send"},
    )
    token = issue_review_token(
        row["id"], actor.tenant_id, actor.user_id, link_deadline(row["expires_at"])
    )
    decide_review(
        store,
        token,
        {"decision": "approve", "args_hash": row["args_hash"]},
        require_session=False,
        session_user_id=None,
    )
    await flush_store(store)
    loaded = await _reload(database_url)
    saved = loaded.approvals[row["id"]]
    assert saved["status"] == "approved"
    assert saved["arguments"]["target_date"] == "2026-01-02"


async def test_a_webhook_delivery_reloads_from_postgres(database_url: str) -> None:
    store, actor = await _ready(database_url)
    WebhookBook(store).create(
        actor.tenant_id,
        actor.user_id,
        f"sink-{uuid.uuid4().hex[:6]}",
        "https://example.com/hook",
        ["run.completed"],
    )
    dispatch_public_event(store, actor.tenant_id, "run.completed", {"run_id": "r1"})
    await flush_store(store)
    loaded = await _reload(database_url)
    assert loaded.webhook_deliveries
    delivery = next(iter(loaded.webhook_deliveries.values()))
    event = loaded.outbox_events[delivery["outbox_event_id"]]
    assert event["topic"] == "run.completed"


async def test_an_extraction_correction_reloads(database_url: str) -> None:
    store, actor = await _ready(database_url)
    run_id, agent_id, call_id = _run_and_call(store, actor)
    approval = ApprovalBook(store).create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=agent_id,
        tool_call_id=call_id,
        qualified_name="documents.review_extraction",
        risk_class="W2",
        args_hash="hash",
        arguments={"report_date": "old"},
        requirement={"approvers": {"mode": "requester"}, "ttl_s": 3600},
        reasons=["ask"],
        preview={"title": "Extract"},
    )
    extraction_id = uuid.uuid4()
    store.document_extractions[extraction_id] = {
        "id": extraction_id,
        "tenant_id": actor.tenant_id,
        "document_id": uuid.uuid4(),
        "content_hash": "abc",
        "schema_hash": "def",
        "model_alias": "reasoning",
        "strategy": "single",
        "fields": [],
        "result": {"report_date": "old"},
        "corrections": [],
        "approval_id": approval["id"],
        "run_id": approval["run_id"],
        "created_at": approval["created_at"],
    }
    approval["status"] = "approved"
    approval["arguments"] = {"report_date": "new"}
    note_extraction_decision(store, approval)
    await flush_store(store)
    loaded = await _reload(database_url)
    saved = loaded.document_extractions[extraction_id]
    assert saved["result"]["report_date"] == "new"
    assert saved["corrections"][0]["diff"][0]["after"] == "new"


async def test_settings_versions_reload(database_url: str) -> None:
    store, actor = await _ready(database_url)
    schema = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}},
        "additionalProperties": False,
    }
    wider = {
        "type": "object",
        "properties": {"limit": {"type": "integer"}, "note": {"type": "string"}},
        "additionalProperties": False,
    }
    book = SettingsBook(store)
    book.save(actor.tenant_id, actor.user_id, "agent", "scan", schema, {"limit": 1})
    book.save(actor.tenant_id, actor.user_id, "agent", "scan", wider, {"limit": 1, "note": "a"})
    await flush_store(store)
    loaded = await _reload(database_url)
    read = dispatch_settings(
        loaded,
        "read",
        {"_tenant_id": actor.tenant_id, "resourceType": "agent", "resourceId": "scan"},
    )
    assert read["structured"]["version"] == 2
    assert read["structured"]["document"]["note"] == "a"


async def test_scenario_versions_and_four_eyes_reload(database_url: str) -> None:
    store, actor = await _ready(database_url)
    first = dispatch_extensions(
        store,
        "put",
        {
            "_tenant_id": actor.tenant_id,
            "packId": "scenario_runs",
            "bucket": "runs",
            "payload": {"n": 1},
            "reason": "first",
        },
    )
    dispatch_extensions(
        store,
        "put",
        {
            "_tenant_id": actor.tenant_id,
            "id": first["structured"]["id"],
            "packId": "scenario_runs",
            "bucket": "runs",
            "payload": {"n": 2},
            "reason": "revised",
        },
    )
    run_id, agent_id, call_id = _run_and_call(store, actor)
    approval = ApprovalBook(store).create_pending(
        tenant_id=actor.tenant_id,
        user_id=actor.user_id,
        run_id=run_id,
        agent_id=agent_id,
        tool_call_id=call_id,
        qualified_name="extensions.compare",
        risk_class="W2",
        args_hash="hash",
        arguments={"n": 1},
        requirement={
            "approvers": {"mode": "group", "groups": ["approvers"]},
            "four_eyes": True,
            "ttl_s": 3600,
        },
        reasons=["results"],
        preview={"title": "Results"},
    )
    store.user_groups[actor.user_id] = ["approvers"]
    assert can_decide(store, actor, approval) is False
    await flush_store(store)
    loaded = await _reload(database_url)
    row_id = uuid.UUID(str(first["structured"]["id"]))
    assert loaded.extension_rows[row_id]["version"] == 2
    assert loaded.extension_rows[row_id]["reason"] == "revised"
    loaded.user_groups[actor.user_id] = ["approvers"]
    assert can_decide(loaded, actor, loaded.approvals[approval["id"]]) is False
