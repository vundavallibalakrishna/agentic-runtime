"""Load Postgres rows back into the process cache."""

import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_domain.durable.codec import as_uuid
from ar_domain.durable.tracking import BUCKETS, TrackedDict

if TYPE_CHECKING:
    from typing import Any


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
    bucket[key] = base


async def hydrate_tenant(store: object, engine: AsyncEngine, tenant_id: uuid.UUID) -> None:
    """Merge one tenant's durable rows into the cache. Memory-only fields stay."""
    store.reloading = True  # type: ignore[attr-defined]
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
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
            await _conversations(session, store, tenant_id)
            await _runs(session, store, tenant_id)
            await _messages(session, store, tenant_id)
            await _events(session, store, tenant_id)
    finally:
        store.reloading = False  # type: ignore[attr-defined]
        for name in BUCKETS:
            bucket = getattr(store, name, None)
            if isinstance(bucket, TrackedDict):
                bucket.dirty.clear()


async def reload_run(store: object, run_id: uuid.UUID) -> None:
    """Refresh one run, its messages and its events from Postgres."""
    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        return
    store.reloading = True  # type: ignore[attr-defined]
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            run = (
                await session.execute(text("SELECT * FROM runs WHERE id = :id"), {"id": run_id})
            ).mappings().first()
            if run is None:
                return
            _merge(store, "runs", run_id, dict(run))
            messages = (
                await session.execute(
                    text("SELECT * FROM messages WHERE run_id = :id ORDER BY created_at"),
                    {"id": run_id},
                )
            ).mappings()
            for message in messages:
                body = dict(message)
                body["text"] = _text_of(body.get("content"))
                _merge(store, "messages", body["id"], body)
            await _events_for(session, store, run_id, run.get("conversation_id"),
                run.get("tenant_id"))
    finally:
        store.reloading = False  # type: ignore[attr-defined]
        events = getattr(store, "events", None)
        runs = getattr(store, "runs", None)
        messages = getattr(store, "messages", None)
        for bucket in (events, runs, messages):
            if isinstance(bucket, TrackedDict):
                bucket.dirty.discard(run_id)


async def _rows(session: AsyncSession, sql: str, tenant_id: uuid.UUID) -> list[dict[str, Any]]:
    result = await session.execute(text(sql), {"tenant_id": tenant_id})
    return [dict(row) for row in result.mappings()]


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
    for row in await _rows(session, "SELECT * FROM documents WHERE tenant_id = :tenant_id",
        tenant_id):
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
    store.reloading = True  # type: ignore[attr-defined]
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            document = (
                await session.execute(
                    text("SELECT * FROM documents WHERE id = :id"), {"id": document_id}
                )
            ).mappings().first()
            if document is None:
                return
            body = dict(document)
            _merge(store, "knowledge_documents", document_id, body)
            collection_id = body.get("collection_id")
            if collection_id is not None:
                collection = (
                    await session.execute(
                        text("SELECT * FROM knowledge_collections WHERE id = :id"),
                        {"id": collection_id},
                    )
                ).mappings().first()
                if collection is not None:
                    _merge(store, "knowledge_collections", collection_id, dict(collection))
            chunks = await session.execute(
                text("SELECT * FROM document_chunks WHERE document_id = :id"),
                {"id": document_id},
            )
            for chunk in chunks.mappings():
                row = dict(chunk)
                _merge(store, "document_chunks", row["id"], row)
    finally:
        store.reloading = False  # type: ignore[attr-defined]
        for name in ("knowledge_documents", "knowledge_collections", "document_chunks"):
            bucket = getattr(store, name, None)
            if isinstance(bucket, TrackedDict):
                bucket.dirty.discard(document_id)


async def _facts(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    for row in await _rows(
        session, "SELECT * FROM memory_facts WHERE tenant_id = :tenant_id", tenant_id
    ):
        if row.get("embedding") is not None:
            row["embedding"] = list(row["embedding"])
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
            body["embedding"] = list(body["embedding"])
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
    for row in await _rows(session, "SELECT * FROM messages WHERE tenant_id = :tenant_id",
        tenant_id):
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
            "ts": row["created_at"].isoformat() if hasattr(row.get("created_at"),
                "isoformat") else "",
            "tenant_id": as_uuid(tenant_id) or row.get("tenant_id"),
        }
        for row in events
    ]
    bucket = getattr(store, "events", None)
    if isinstance(bucket, dict):
        bucket[run_id] = shaped
