"""Routine credentials rotate immutably and worker reloads preserve pending edits."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

from ar_common.time import utcnow
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.hydrate import _routines
from ar_domain.durable.routines import save_events, save_routines
from ar_domain.durable.tracking import install_tracking


async def test_routine_credentials_are_references_and_event_updates_are_tenant_scoped(monkeypatch):
    tenant, routine, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    secret = "server-signing-value"  # noqa: S105
    save = AsyncMock()
    monkeypatch.setattr("ar_domain.durable.routines.save_cached_secret", save)
    session = SimpleNamespace(execute=AsyncMock())
    row = {
        "id": routine,
        "tenant_id": tenant,
        "owner_user_id": user,
        "name": "Portal event",
        "webhook_secret": secret,
        "webhook_secret_previous": "",
        "webhook_secret_previous_until": None,
    }
    await save_routines(session, [row])
    first = save.call_args.kwargs["secret_id"]
    params = session.execute.call_args.args[0].compile().params
    assert params["webhook_secret_ref_id"] == first
    assert "webhook_secret" not in params
    assert params["tenant_id"] == tenant
    await save_routines(session, [row])
    assert save.call_args.kwargs["secret_id"] == first
    row["webhook_secret"] = "rotated-value"  # noqa: S105
    await save_routines(session, [row])
    assert save.call_args.kwargs["secret_id"] != first
    assert save.call_args.kwargs["tenant_id"] == tenant
    event = {
        "id": uuid.uuid4(),
        "tenant_id": tenant,
        "routine_id": routine,
        "idempotency_key": "one",
        "source": "webhook",
        "envelope": {},
        "status": "started",
        "run_id": uuid.uuid4(),
        "dry_run": True,
    }
    await save_events(session, [event])
    stmt = session.execute.call_args.args[0]
    assert "WHERE routine_events.tenant_id =" in str(stmt)
    assert "dry_run" not in stmt.compile().params
    assert stmt.compile().params["run_id"] == event["run_id"]


async def test_routine_reload_recovers_signing_key_status_and_dry_run_without_dirtying(monkeypatch):
    store = ChatService()
    install_tracking(store)
    tenant, routine, event, secret, user = (uuid.uuid4() for _ in range(5))
    rows = {
        "users": [{"id": user, "status": "suspended"}],
        "routines": [{"id": routine, "name": "Saved", "webhook_secret_ref_id": secret}],
        "routine_events": [{"id": event, "status": "accepted", "envelope": {"dry_run": True}}],
    }

    async def query(session, sql, tenant_id):
        assert tenant_id == tenant
        return rows[sql.split("FROM ")[1].split()[0]]

    monkeypatch.setattr("ar_domain.durable.hydrate._rows", query)
    load = AsyncMock(
        return_value=b'{"current":"signing-value","previous":"old-value","previousUntil":null}'
    )
    monkeypatch.setattr("ar_domain.secrets.cached.load_cached_secret", load)
    await _routines(object(), store, tenant)
    assert store.routines[routine]["webhook_secret"] == "signing-value"  # noqa: S105
    assert store.routine_events[event]["dry_run"] is True
    assert store.user_statuses[user] == "suspended"
    assert not store.routines.dirty
    store.routines[routine]["name"] = "Unsaved edit"
    await _routines(object(), store, tenant)
    assert store.routines[routine]["name"] == "Unsaved edit"
    load.assert_awaited()


async def test_worker_created_run_stream_reloads_without_an_api_dispatch_task(monkeypatch):
    store = ChatService()
    tenant, owner = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, owner, None)
    posted = store.post_message(
        tenant, owner, uuid.UUID(str(conversation["id"])), "update", schedule=False
    )
    run_id = uuid.UUID(str(posted["run"]["id"]))
    store.durable_engine = object()
    reloaded = []

    async def reload(service, key):
        reloaded.append(key)
        service.runs[key]["status"] = "completed"
        service.events[key].append({"seq": 2, "type": "run.completed", "ts": utcnow().isoformat()})

    monkeypatch.setattr("ar_domain.durable.hydrate.reload_run", reload)
    events = [event async for event in store.iter_events(tenant, run_id, 1)]
    assert [event["type"] for event in events] == ["run.completed"]
    assert reloaded == [run_id]
    assert store.subscribers[run_id] == []
