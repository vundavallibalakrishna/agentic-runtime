"""Load Postgres rows back into the process cache."""

import uuid
from typing import TYPE_CHECKING

import orjson
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_domain.durable.codec import as_uuid, vector_values
from ar_domain.durable.tracking import TrackedDict

if TYPE_CHECKING:
    from typing import Any


async def _channel_integrations(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM channel_integrations WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "channel_integrations", row["id"], row)
        secret_id = row.get("secret_ref_id")
        if isinstance(secret_id, uuid.UUID):
            from ar_domain.secrets.cached import load_cached_secret  # noqa: PLC0415

            value = await load_cached_secret(session, tenant_id, secret_id)
            if value is not None:
                store.secret_values[secret_id] = value  # type: ignore[attr-defined]


async def _channel_identities(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM channel_identities WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "channel_identities", row["id"], row)


async def _channel_threads(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM channel_threads WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "channel_threads", row["id"], row)


async def _channel_posts(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM channel_posts WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "channel_posts", row["id"], row)


def _text_of(content: object) -> str:
    if isinstance(content, list):
        parts = [str(item.get("text") or "") for item in content if isinstance(item, dict)]
        return "".join(parts)
    return ""


def _merge(store: object, name: str, key: object, row: dict[str, Any]) -> None:
    bucket = getattr(store, name, None)
    if not isinstance(bucket, dict):
        return
    current = bucket.get(key)
    base = {str(item): current[item] for item in current} if isinstance(current, dict) else {}
    base.update(row)
    _load(store, bucket, key, base)


_AHEAD = frozenset({"running", "waiting_approval", "waiting_input"})
_DONE = frozenset({"completed", "failed", "cancelled", "budget_exceeded"})


def _merge_live(current: dict[str, object], incoming: dict[str, object]) -> None:
    """Fold a database row into the live run without moving a turn backwards."""
    current_status = str(current.get("status") or "")
    incoming_status = str(incoming.get("status") or "")
    if current_status in _DONE and incoming_status not in _DONE:
        return
    if current_status in _AHEAD and incoming_status == "queued":
        return
    current.update(incoming)


def _load(store: object, bucket: dict[object, object], key: object, value: object) -> None:
    if isinstance(bucket, TrackedDict):
        loading = getattr(store, "_initial_loaded", None)
        if isinstance(loading, dict):
            loading.setdefault(bucket.kind, set()).add(key)
        if key in bucket.dirty:
            return
    current = bucket.get(key)
    if isinstance(current, dict) and isinstance(value, dict):
        if bucket is getattr(store, "runs", None):
            _merge_live(current, value)
        else:
            current.update(value)
        return
    was_reloading = getattr(store, "reloading", False)
    store.reloading = True  # type: ignore[attr-defined]
    try:
        bucket[key] = value
    finally:
        store.reloading = was_reloading  # type: ignore[attr-defined]


async def hydrate_tenant(store: object, engine: AsyncEngine, tenant_id: uuid.UUID) -> None:
    """Merge one tenant's durable rows into the cache. Memory-only fields stay."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await _settings(session, store, tenant_id)
        await _agents(session, store, tenant_id)
        await _versions(session, store, tenant_id)
        await _skills(session, store, tenant_id)
        await _skill_versions(session, store, tenant_id)
        await _collections(session, store, tenant_id)
        await _sources(session, store, tenant_id)
        await _documents(session, store, tenant_id)
        await _chunks(session, store, tenant_id)
        await _facts(session, store, tenant_id)
        await _tools(session, store, tenant_id)
        await _routines(session, store, tenant_id)
        await _conversations(session, store, tenant_id)
        await _runs(session, store, tenant_id)
        await _messages(session, store, tenant_id)
        await _events(session, store, tenant_id)
        await _channel_integrations(session, store, tenant_id)
        await _channel_identities(session, store, tenant_id)
        await _channel_threads(session, store, tenant_id)
        await _channel_posts(session, store, tenant_id)


async def reload_run(store: object, run_id: uuid.UUID) -> None:
    """Refresh one run, its messages and its events from Postgres."""
    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        return
    async with AsyncSession(engine, expire_on_commit=False) as session:
        run = (
            (await session.execute(text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}))
            .mappings()
            .first()
        )
        if run is None:
            return
        _merge(store, "runs", run_id, dict(run))
        tenant_id = run["tenant_id"]
        await _conversations(session, store, tenant_id)
        await _agents(session, store, tenant_id)
        await _versions(session, store, tenant_id)
        await _skills(session, store, tenant_id)
        await _skill_versions(session, store, tenant_id)
        await _facts(session, store, tenant_id)
        await _tools(session, store, tenant_id)
        messages = (
            await session.execute(
                text(
                    "SELECT * FROM messages WHERE conversation_id = :id "
                    "AND tenant_id = :tenant_id ORDER BY created_at"
                ),
                {"id": run["conversation_id"], "tenant_id": tenant_id},
            )
        ).mappings()
        for message in messages:
            body = dict(message)
            body["text"] = _text_of(body.get("content"))
            _merge(store, "messages", body["id"], body)
            if body.get("run_id") == run_id and body.get("role") == "assistant":
                _merge(store, "runs", run_id, {"assistant_message_id": body["id"]})
        await _events_for(session, store, run_id, run.get("conversation_id"), run.get("tenant_id"))


async def _rows(session: AsyncSession, sql: str, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), {"tenant_id": tenant_id})
    return [dict(row) for row in result.mappings()]


async def _settings(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    result = await session.execute(
        text("SELECT settings FROM tenants WHERE id = :tenant_id"), {"tenant_id": tenant_id}
    )
    row = result.mappings().first()
    settings = row.get("settings") if row is not None else None
    if isinstance(settings, dict):
        store.tenant_settings[tenant_id] = settings  # type: ignore[attr-defined]


async def _agents(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(session, "SELECT * FROM agents WHERE tenant_id = :tenant_id", tenant_id):
        row["disabled"] = row.get("disabled_at") is not None
        _merge(store, "agents", row["id"], row)


async def _versions(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM agent_versions WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "versions", row["id"], row)


async def _skills(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(session, "SELECT * FROM skills WHERE tenant_id = :tenant_id", tenant_id):
        _merge(store, "skills", row["id"], row)


async def _skill_versions(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM skill_versions WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "skill_versions", row["id"], row)


async def _collections(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM knowledge_collections WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "knowledge_collections", row["id"], row)


async def _sources(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM knowledge_sources WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "knowledge_sources", row["id"], row)


async def _documents(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM documents WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "knowledge_documents", row["id"], row)


async def _chunks(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM document_chunks WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "document_chunks", row["id"], row)


async def reload_document(store: object, document_id: uuid.UUID) -> None:
    """Refresh one document and its collection after the ingest worker finishes."""
    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        return
    async with AsyncSession(engine, expire_on_commit=False) as session:
        document = (
            (
                await session.execute(
                    text("SELECT * FROM documents WHERE id = :id"), {"id": document_id}
                )
            )
            .mappings()
            .first()
        )
        if document is None:
            return
        body = dict(document)
        _merge(store, "knowledge_documents", document_id, body)
        collection_id = body.get("collection_id")
        if collection_id is not None:
            collection = (
                (
                    await session.execute(
                        text("SELECT * FROM knowledge_collections WHERE id = :id"),
                        {"id": collection_id},
                    )
                )
                .mappings()
                .first()
            )
            if collection is not None:
                _merge(store, "knowledge_collections", collection_id, dict(collection))
        chunks = await session.execute(
            text("SELECT * FROM document_chunks WHERE document_id = :id"),
            {"id": document_id},
        )
        for chunk in chunks.mappings():
            row = dict(chunk)
            _merge(store, "document_chunks", row["id"], row)


async def _facts(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM memory_facts WHERE tenant_id = :tenant_id", tenant_id
    ):
        if row.get("embedding") is not None:
            row["embedding"] = vector_values(row["embedding"])
        _merge(store, "memory_facts", row["id"], row)


async def _tools(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    servers = await session.execute(
        text("SELECT * FROM tool_servers WHERE tenant_id = :tenant_id OR tenant_id IS NULL"),
        {"tenant_id": tenant_id},
    )
    for row in servers.mappings():
        _merge(store, "tool_servers", row["id"], dict(row))
    versions = await session.execute(
        text(
            "SELECT * FROM tool_server_versions WHERE tenant_id = :tenant_id OR tenant_id IS NULL"
        ),
        {"tenant_id": tenant_id},
    )
    for row in versions.mappings():
        _merge(store, "tool_server_versions", row["id"], dict(row))
    tools = await session.execute(
        text("SELECT * FROM tools WHERE tenant_id = :tenant_id OR tenant_id IS NULL"),
        {"tenant_id": tenant_id},
    )
    for row in tools.mappings():
        _merge(store, "tool_defs", row["id"], dict(row))
    tool_versions = await session.execute(
        text("SELECT * FROM tool_versions WHERE tenant_id = :tenant_id OR tenant_id IS NULL"),
        {"tenant_id": tenant_id},
    )
    for row in tool_versions.mappings():
        body = dict(row)
        if body.get("embedding") is not None:
            body["embedding"] = vector_values(body["embedding"])
        _merge(store, "tool_versions", body["id"], body)


async def _conversations(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM conversations WHERE tenant_id = :tenant_id", tenant_id
    ):
        _merge(store, "conversations", row["id"], row)


async def _runs(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(session, "SELECT * FROM runs WHERE tenant_id = :tenant_id", tenant_id):
        _merge(store, "runs", row["id"], row)


async def _messages(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM messages WHERE tenant_id = :tenant_id", tenant_id
    ):
        row["text"] = _text_of(row.get("content"))
        _merge(store, "messages", row["id"], row)


async def _events(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    result = await session.execute(
        text(
            "SELECT run_id, seq, type, data, created_at, tenant_id FROM run_events "
            "WHERE tenant_id = :tenant_id ORDER BY run_id, seq"
        ),
        {"tenant_id": tenant_id},
    )
    grouped: dict[uuid.UUID, list[dict[str, Any]]] = {}
    for row in result.mappings():
        grouped.setdefault(row["run_id"], []).append(dict(row))
    for run_id, events in grouped.items():
        await _events_for(session, store, run_id, None, tenant_id, events=events)


async def _events_for(  # noqa: PLR0917 - the event row needs the run, conversation and tenant
    session: AsyncSession,
    store: object,
    run_id: uuid.UUID,
    conversation_id: object,
    tenant_id: object,
    events: list[dict[str, Any]] | None = None,
) -> None:
    if events is None:
        result = await session.execute(
            text(
                "SELECT seq, type, data, created_at, tenant_id FROM run_events "
                "WHERE run_id = :id ORDER BY seq"
            ),
            {"id": run_id},
        )
        events = [dict(row) for row in result.mappings()]
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if conversation_id is None and isinstance(run, dict):
        conversation_id = run.get("conversation_id")
    shaped = [
        {
            "id": f"{run_id}:{row['seq']}",
            "seq": row["seq"],
            "type": row["type"],
            "run_id": str(run_id),
            "conversation_id": "" if conversation_id is None else str(conversation_id),
            "data": row.get("data") or {},
            "ts": row["created_at"].isoformat()
            if hasattr(row.get("created_at"), "isoformat")
            else "",
            "tenant_id": as_uuid(tenant_id) or row.get("tenant_id"),
        }
        for row in events
    ]
    bucket = getattr(store, "events", None)
    if isinstance(bucket, dict):
        _load(store, bucket, run_id, shaped)


async def _routines(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.secrets.cached import load_cached_secret  # noqa: PLC0415

    statuses = getattr(store, "user_statuses", None)
    if isinstance(statuses, dict):
        for user in await _rows(
            session, "SELECT id, status FROM users WHERE tenant_id = :tenant_id", tenant_id
        ):
            statuses[user["id"]] = user["status"]
    for row in await _rows(
        session, "SELECT * FROM routines WHERE tenant_id = :tenant_id", tenant_id
    ):
        secret_id = row.get("webhook_secret_ref_id")
        if isinstance(secret_id, uuid.UUID):
            value = await load_cached_secret(session, tenant_id, secret_id)
            if value is not None:
                saved = orjson.loads(value)
                row["webhook_secret"] = saved["current"]
                row["webhook_secret_previous"] = saved.get("previous", "")
                from ar_domain.durable.codec import as_dt  # noqa: PLC0415

                row["webhook_secret_previous_until"] = as_dt(saved.get("previousUntil"))
        _merge(store, "routines", row["id"], row)
    for row in await _rows(
        session, "SELECT * FROM routine_events WHERE tenant_id = :tenant_id", tenant_id
    ):
        envelope = row.get("envelope")
        row["dry_run"] = bool(envelope.get("dry_run")) if isinstance(envelope, dict) else False
        _merge(store, "routine_events", row["id"], row)


async def reload_routines(store: object) -> None:
    from ar_domain.durable.bind import binding_from  # noqa: PLC0415

    binding = binding_from(store)
    engine = getattr(store, "durable_engine", None)
    if binding is not None and isinstance(engine, AsyncEngine):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await _routines(session, store, binding.tenant_id)
