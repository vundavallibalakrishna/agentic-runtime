"""Load Postgres rows back into the process cache."""

import uuid
from typing import TYPE_CHECKING

import orjson
from sqlalchemy import bindparam, text
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
    was_reloading = getattr(store, "reloading", False)
    store.reloading = True  # type: ignore[attr-defined]
    try:
        # A row read from the database is not a change, so it is merged without marking.
        if isinstance(current, dict) and isinstance(value, dict):
            if bucket is getattr(store, "runs", None):
                _merge_live(current, value)
            else:
                current.update(value)
        else:
            bucket[key] = value
    finally:
        store.reloading = was_reloading  # type: ignore[attr-defined]


async def hydrate_tenant(
    store: object,
    engine: AsyncEngine,
    tenant_id: uuid.UUID,
    *,
    session: AsyncSession | None = None,
) -> None:
    """Merge one tenant's durable rows. Memory-only fields stay.

    A request passes its own session so the read runs with ``app.tenant_id`` set.
    """
    if session is not None:
        await _hydrate_all(session, store, tenant_id)
        return
    async with AsyncSession(engine, expire_on_commit=False) as opened:
        await _hydrate_all(opened, store, tenant_id)


async def _hydrate_all(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Load every bucket for one tenant on ``session``."""
    await _settings(session, store, tenant_id)
    await _people(session, store, tenant_id)
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
    from ar_domain.durable.m23 import (  # noqa: PLC0415
        load_data_connections,
        load_model_catalog,
        load_service_connections,
    )

    await load_service_connections(session, store, tenant_id)
    await load_data_connections(session, store, tenant_id)
    from ar_domain.durable.m26 import load_connector_rows  # noqa: PLC0415

    await load_connector_rows(session, store, tenant_id)
    await load_model_catalog(session, store, tenant_id)
    from ar_domain.durable.m24 import load_library  # noqa: PLC0415

    await load_library(session, store, tenant_id)
    await _routines(session, store, tenant_id)
    await _conversations(session, store, tenant_id)
    await _runs(session, store, tenant_id)
    await _messages(session, store, tenant_id)
    from ar_domain.durable.m28 import load_runtime_rows  # noqa: PLC0415

    await load_runtime_rows(session, store, tenant_id)
    from ar_domain.durable.stage9 import load_shared_rows  # noqa: PLC0415

    await load_shared_rows(session, store, tenant_id)
    from ar_domain.durable.m29 import load_exposure  # noqa: PLC0415

    await load_exposure(session, store, tenant_id)
    from ar_domain.durable.m35 import load_durability  # noqa: PLC0415

    await load_durability(session, store, tenant_id)
    await _events(session, store, tenant_id)
    await _channel_integrations(session, store, tenant_id)
    await _channel_identities(session, store, tenant_id)
    await _channel_threads(session, store, tenant_id)
    await _channel_posts(session, store, tenant_id)
    await _usage_events(session, store, tenant_id)
    from ar_domain.tools.seed_tools import ensure_m33b  # noqa: PLC0415

    ensure_m33b(store)


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
        # A setting an administrator changed since this process started applies to this turn.
        await _settings(session, store, tenant_id)
        await _people(session, store, tenant_id)
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
        attached: list[uuid.UUID] = []
        for message in messages:
            body = dict(message)
            body["text"] = _text_of(body.get("content"))
            _merge(store, "messages", body["id"], body)
            attached.extend(_file_ids(body.get("content")))
            if body.get("run_id") == run_id and body.get("role") == "assistant":
                _merge(store, "runs", run_id, {"assistant_message_id": body["id"]})
        from ar_domain.durable.m35 import load_conversation_files  # noqa: PLC0415

        await load_conversation_files(session, store, tenant_id, run["conversation_id"], attached)
        await _tool_calls_for(session, store, tenant_id, run_id)
        await _library_for_files(session, store, tenant_id)
        await _events_for(session, store, run_id, run.get("conversation_id"), run.get("tenant_id"))


async def _tool_calls_for(
    session: AsyncSession, store: object, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> None:
    """A retried activity must see the calls the first attempt already stored."""
    result = await session.execute(
        text("SELECT * FROM tool_calls WHERE tenant_id = :tenant_id AND run_id = :run_id"),
        {"tenant_id": tenant_id, "run_id": run_id},
    )
    for mapping in result.mappings():
        row = dict(mapping)
        _merge(store, "tool_calls", row["id"], row)


async def _library_for_files(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Load library documents whose bytes match files this turn can already see.

    The upload commits the document on the API. The worker used to start the turn
    without that row, so the first read said the document was not found.
    """
    files = getattr(store, "files", None)
    if not isinstance(files, dict):
        return
    hashes = [
        str(row.get("sha256"))
        for row in files.values()
        if isinstance(row, dict) and row.get("tenant_id") == tenant_id and row.get("sha256")
    ]
    if not hashes:
        return
    found = await session.execute(
        text(
            "SELECT * FROM library_documents "
            "WHERE tenant_id = :tenant_id AND content_hash IN :hashes"
        ).bindparams(bindparam("hashes", expanding=True)),
        {"tenant_id": tenant_id, "hashes": hashes},
    )
    for mapping in found.mappings():
        row = dict(mapping)
        for key in ("metadata", "passages", "tables"):
            value = row.get(key)
            if isinstance(value, str):
                row[key] = orjson.loads(value)
        _merge(store, "library_documents", row["id"], row)


def _file_ids(content: object) -> list[uuid.UUID]:
    """The ids of the files a message's content attaches."""
    ids: list[uuid.UUID] = []
    for part in content if isinstance(content, list) else []:
        if not isinstance(part, dict) or part.get("type") != "file":
            continue
        try:
            ids.append(uuid.UUID(str(part.get("file_id"))))
        except ValueError:
            continue
    return ids


async def _usage_events(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Reload the last 400 days of usage so summaries and quotas survive a restart."""
    from ar_domain.usage.logic import UsageRecord, record_usage  # noqa: PLC0415

    usage = getattr(store, "usage", None)
    if not isinstance(usage, dict):
        return
    flushed = getattr(store, "_usage_flushed", None)
    if not isinstance(flushed, set):
        flushed = set()
        store._usage_flushed = flushed  # type: ignore[attr-defined]
    for row in await _rows(
        session,
        "SELECT * FROM usage_events WHERE tenant_id = :tenant_id "
        "AND occurred_at >= now() - interval '400 days' ORDER BY occurred_at",
        tenant_id,
    ):
        item = UsageRecord(
            str(row["tenant_id"]),
            row["occurred_at"],
            str(row["metric"]),
            int(row["quantity"]),
            int(row.get("cost_micros") or 0),
            str(row["dedupe_key"]),
            user_id=_text_or_none(row.get("user_id")),
            team_id=_text_or_none(row.get("team_id")),
            agent_id=_text_or_none(row.get("agent_id")),
            model_alias=str(row.get("model_alias") or ""),
            source=str(row.get("source") or "api"),
            run_id=_text_or_none(row.get("run_id")),
            model_id=_text_or_none(row.get("model_id")),
            tool_id=_text_or_none(row.get("tool_id")),
            routine_id=_text_or_none(row.get("routine_id")),
            api_key_id=_text_or_none(row.get("api_key_id")),
        )
        record_usage(usage, item)
        flushed.add((item.tenant_id, item.dedupe_key))


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


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
    """Make the store's memory of one tenant equal its database rows.

    Another process may have saved a fact or deleted one. A memory the person deleted
    must leave every process, or a worker that still holds it keeps recalling it. Rows
    this process changed and has not saved yet are kept as they are.
    """
    held: set[object] = set()
    for row in await _rows(
        session, "SELECT * FROM memory_facts WHERE tenant_id = :tenant_id", tenant_id
    ):
        if row.get("embedding") is not None:
            row["embedding"] = vector_values(row["embedding"])
        held.add(row["id"])
        _merge(store, "memory_facts", row["id"], row)
    bucket = getattr(store, "memory_facts", None)
    if not isinstance(bucket, TrackedDict):
        return
    gone = [
        key
        for key, value in bucket.items()
        if key not in held
        and key not in bucket.dirty
        and isinstance(value, dict)
        and value.get("tenant_id") == tenant_id
    ]
    for key in gone:
        bucket.evict(key)


async def reload_memory(store: object) -> None:
    """Refresh the memory of the tenant this process serves. A down database changes nothing."""
    engine = getattr(store, "durable_engine", None)
    tenant_id = getattr(getattr(store, "tenant_binding", None), "tenant_id", None)
    if not isinstance(engine, AsyncEngine) or not isinstance(tenant_id, uuid.UUID):
        return
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            await _facts(session, store, tenant_id)
    except Exception:  # noqa: BLE001 — the screen still shows what this process holds
        return


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
        # Tool search keeps its own vectors, made by the tenant's model (tools/search.py).
        body.pop("embedding", None)
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


_ROLES_SQL = (
    "SELECT a.principal_id AS user_id, r.key FROM role_assignments a "
    "JOIN roles r ON r.id = a.role_id "
    "WHERE a.tenant_id = :tenant_id AND a.principal_type = 'user' AND a.scope_type = 'tenant' "
    "UNION "
    "SELECT m.user_id, r.key FROM role_assignments a "
    "JOIN roles r ON r.id = a.role_id "
    "JOIN group_members m ON m.group_id = a.principal_id AND m.tenant_id = a.tenant_id "
    "WHERE a.tenant_id = :tenant_id AND a.principal_type = 'group' AND a.scope_type = 'tenant'"
)


async def _people(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """The tenant's people, their names, status and roles, as the database holds them.

    Policy, approvals and reviews read roles from the store. A person's roles are replaced,
    not merged, so a role taken away in the database is gone here too.
    """
    roles: dict[uuid.UUID, set[str]] = {}
    for row in await _rows(session, _ROLES_SQL, tenant_id):
        roles.setdefault(row["user_id"], set()).add(str(row["key"]))
    buckets = {
        name: getattr(store, name, None)
        for name in ("user_statuses", "display_names", "user_emails", "user_roles")
    }
    for user in await _rows(
        session,
        "SELECT id, email, display_name, status FROM users WHERE tenant_id = :tenant_id",
        tenant_id,
    ):
        values = {
            "user_statuses": user["status"],
            "display_names": str(user["display_name"]),
            "user_emails": str(user["email"]).lower(),
            "user_roles": roles.get(user["id"], set()),
        }
        for name, value in values.items():
            bucket = buckets[name]
            if isinstance(bucket, dict):
                bucket[user["id"]] = value


async def _routines(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.secrets.cached import load_cached_secret  # noqa: PLC0415

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
            # A routine does not run for an owner who has been suspended since.
            await _people(session, store, binding.tenant_id)
            await _routines(session, store, binding.tenant_id)
