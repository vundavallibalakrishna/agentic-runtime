"""Write tracked product rows into the Postgres schema."""

import asyncio
import uuid  # noqa: TC003
from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from ar_common.time import utcnow
from ar_domain.agents.logic import definition_hash
from ar_domain.durable.codec import as_bool, as_dt, as_int, as_json, as_text, as_uuid, as_vector
from ar_domain.durable.routines import save_events, save_routines
from ar_domain.durable.tracking import BUCKETS, TrackedDict

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.audit.actions import AuditAction


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _object_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


async def flush_store(store: object) -> None:
    """Wait for a committed flush, retaining dirty rows if the transaction fails."""
    engine = getattr(store, "durable_engine", None)
    if not isinstance(engine, AsyncEngine):
        return
    lock = getattr(store, "_flush_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        store._flush_lock = lock  # type: ignore[attr-defined]
    async with lock:
        while True:
            store._flush_again = False  # type: ignore[attr-defined]
            await _flush_once(store, engine)
            if not getattr(store, "_flush_again", False):
                break


def schedule_flush(store: object) -> None:
    """Queue a flush on the running loop. Sync callers use this."""
    if getattr(store, "durable_engine", None) is None:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = getattr(store, "_flush_task", None)
    if task is not None and not task.done():
        store._flush_again = True  # type: ignore[attr-defined]
        return

    async def _run() -> None:
        await flush_store(store)
        if getattr(store, "_flush_again", False):
            await flush_store(store)

    store._flush_task = loop.create_task(_run())  # type: ignore[attr-defined]


async def _flush_once(store: object, engine: AsyncEngine) -> None:
    pending = _snapshot(store)
    audit_log = getattr(store, "audit_log", [])
    audit_end = len(audit_log)
    audit_start = getattr(store, "_durable_audit_index", 0)
    audits = [
        row for row in audit_log[audit_start:audit_end] if row.get("target_type") == "routine"
    ]
    if not any(pending.values()) and not audits:
        return
    original = {name: list(rows) for name, rows in pending.items()}
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
            await _deletions(session, pending)
            await _agents(session, pending["agents"])
            await _versions(session, pending["versions"])
            await _skills(session, pending["skills"])
            await _skill_versions(session, pending["skill_versions"])
            await _collections(session, pending["knowledge_collections"])
            await _sources(session, pending["knowledge_sources"])
            await _documents(session, pending["knowledge_documents"])
            await _chunks(session, pending["document_chunks"])
            await _facts(session, pending["memory_facts"])
            await _tool_servers(session, pending["tool_servers"])
            await _tool_server_versions(session, pending["tool_server_versions"])
            await _tools(session, pending["tool_defs"])
            await _tool_versions(session, pending["tool_versions"])
            await save_routines(session, pending["routines"])
            await _conversations(session, pending["conversations"])
            await _runs(session, store, pending["runs"])
            await _messages(session, pending["messages"])
            await save_events(session, pending["routine_events"])
            await _link_runs(session, pending["runs"], pending["conversations"])
            await _events(session, store, pending["events"])
            await _channel_integrations(session, pending["channel_integrations"], store)
            await _channel_identities(session, pending["channel_identities"])
            await _channel_threads(session, pending["channel_threads"])
            await _channel_posts(session, pending["channel_posts"])
            await _routine_audits(session, audits)
    except BaseException:
        # The transaction rolled back; a retry must include every original row.
        for name, rows in original.items():
            bucket = getattr(store, name, None)
            if isinstance(bucket, TrackedDict):
                bucket.dirty.update(row.get("id", row.get("_key")) for row in rows)
        raise
    store._durable_audit_index = audit_end  # type: ignore[attr-defined]
    for name, rows in original.items():
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            for row in rows:
                if row.get("_deleted"):
                    bucket.deleted.pop(row["id"], None)


async def _deletions(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    tables = {
        "versions": "agent_versions",
        "knowledge_documents": "documents",
        "tool_defs": "tools",
        "events": "run_events",
    }
    for bucket, rows in reversed(list(pending.items())):
        table = tables.get(bucket, bucket)
        # Both identifiers come exclusively from the fixed BUCKETS catalogue.
        for row in rows:
            if row.get("_deleted") and row.get("tenant_id") is not None:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE id = :id AND tenant_id = :tenant_id"),  # noqa: S608
                    {"id": row["id"], "tenant_id": row["tenant_id"]},
                )
        pending[bucket] = [row for row in rows if not row.get("_deleted")]


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _snapshot(store: object) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = {}
    for name in BUCKETS:
        bucket = getattr(store, name, None)
        rows: list[dict[str, Any]] = []
        if isinstance(bucket, TrackedDict):
            keys = list(bucket.dirty)
            bucket.dirty.clear()
            for key in keys:
                value = bucket.get(key)
                deleted = bucket.deleted.get(key)
                if key not in bucket and isinstance(deleted, dict):
                    rows.append(
                        {"id": key, "tenant_id": deleted.get("tenant_id"), "_deleted": True}
                    )
                elif isinstance(value, dict):
                    rows.append({str(item): _plain(value[item]) for item in value})
                elif isinstance(value, list):
                    rows.append(
                        {
                            "_key": key,
                            "_events": [_plain(item) for item in value if isinstance(item, dict)],
                        }
                    )
        found[name] = rows
    return found


async def _one(session: AsyncSession, sql: str, params: dict[str, object]) -> None:
    await session.execute(text(sql), params)


def _parents_first(rows: list[dict[str, Any]], parent_key: str) -> list[dict[str, Any]]:
    """Insert parent rows before children regardless of dirty-set iteration order."""
    pending = {row.get("id"): row for row in rows}
    ordered: list[dict[str, Any]] = []
    while pending:
        ready = [key for key, row in pending.items() if row.get(parent_key) not in pending]
        if not ready:
            raise ValueError("durable rows contain a parent cycle")
        ordered.extend(pending.pop(key) for key in ready)
    return ordered


async def _agents(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO agents (
            id, tenant_id, slug, name, description, owner_user_id, owner_team_id,
            visibility, status, disabled_at, disabled_reason, risk_tier,
            draft_version_id, published_version_id, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :description, :owner_user_id, :owner_team_id,
            :visibility, :status, :disabled_at, :disabled_reason, :risk_tier,
            :draft_version_id, :published_version_id, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            visibility = EXCLUDED.visibility,
            status = EXCLUDED.status,
            disabled_at = EXCLUDED.disabled_at,
            disabled_reason = EXCLUDED.disabled_reason,
            risk_tier = EXCLUDED.risk_tier,
            draft_version_id = EXCLUDED.draft_version_id,
            published_version_id = EXCLUDED.published_version_id,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        agent_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if agent_id is None or tenant_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": agent_id,
                "tenant_id": tenant_id,
                "slug": as_text(row.get("slug"), "agent"),
                "name": as_text(row.get("name"), "Agent"),
                "description": as_text(row.get("description")),
                "owner_user_id": as_uuid(row.get("owner_user_id")),
                "owner_team_id": as_uuid(row.get("owner_team_id")),
                "visibility": as_text(row.get("visibility"), "tenant"),
                "status": as_text(row.get("status"), "draft"),
                "disabled_at": as_dt(row.get("disabled_at")),
                "disabled_reason": row.get("disabled_reason"),
                "risk_tier": as_text(row.get("risk_tier"), "low"),
                "draft_version_id": as_uuid(row.get("draft_version_id")),
                "published_version_id": as_uuid(row.get("published_version_id")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _versions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO agent_versions (
            id, tenant_id, agent_id, version, state, definition, definition_hash,
            change_note, created_by, created_at, updated_at, published_at, published_by
        ) VALUES (
            :id, :tenant_id, :agent_id, :version, :state, CAST(:definition AS jsonb),
            :definition_hash, :change_note, :created_by, :created_at, :updated_at,
            :published_at, :published_by
        )
        ON CONFLICT (id) DO UPDATE SET
            state = EXCLUDED.state,
            definition = EXCLUDED.definition,
            definition_hash = EXCLUDED.definition_hash,
            change_note = EXCLUDED.change_note,
            published_at = EXCLUDED.published_at,
            published_by = EXCLUDED.published_by,
            updated_at = EXCLUDED.updated_at
        WHERE agent_versions.state IS DISTINCT FROM 'published'
    """
    for row in rows:
        version_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        agent_id = as_uuid(row.get("agent_id"))
        definition = _object_dict(row.get("definition"))
        if version_id is None or tenant_id is None or agent_id is None:
            continue
        now = utcnow()
        digest = as_text(row.get("definition_hash")) or definition_hash(definition)
        await _one(
            session,
            sql,
            {
                "id": version_id,
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "version": as_int(row.get("version"), 1),
                "state": as_text(row.get("state"), "draft"),
                "definition": as_json(definition, {}),
                "definition_hash": digest,
                "change_note": as_text(row.get("change_note")),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
                "published_at": as_dt(row.get("published_at")),
                "published_by": as_uuid(row.get("published_by")),
            },
        )


async def _skills(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO skills (
            id, tenant_id, slug, name, description, owner_user_id, owner_team_id,
            visibility, status, published_version_id, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :description, :owner_user_id, :owner_team_id,
            :visibility, :status, :published_version_id, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            visibility = EXCLUDED.visibility,
            status = EXCLUDED.status,
            published_version_id = EXCLUDED.published_version_id,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        skill_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if skill_id is None or tenant_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": skill_id,
                "tenant_id": tenant_id,
                "slug": as_text(row.get("slug")),
                "name": as_text(row.get("name")),
                "description": as_text(row.get("description"))[:500],
                "owner_user_id": as_uuid(row.get("owner_user_id")),
                "owner_team_id": as_uuid(row.get("owner_team_id")),
                "visibility": as_text(row.get("visibility"), "tenant"),
                "status": as_text(row.get("status"), "draft"),
                "published_version_id": as_uuid(row.get("published_version_id")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _skill_versions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO skill_versions (
            id, tenant_id, skill_id, version, instructions_md, assets, required_tools,
            hash, created_by, created_at
        ) VALUES (
            :id, :tenant_id, :skill_id, :version, :instructions_md,
            CAST(:assets AS jsonb), :required_tools, :hash, :created_by, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            instructions_md = EXCLUDED.instructions_md,
            assets = EXCLUDED.assets,
            required_tools = EXCLUDED.required_tools,
            hash = EXCLUDED.hash
        WHERE skill_versions.version = 0
    """
    for row in rows:
        version_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        skill_id = as_uuid(row.get("skill_id"))
        if version_id is None or tenant_id is None or skill_id is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": version_id,
                "tenant_id": tenant_id,
                "skill_id": skill_id,
                "version": as_int(row.get("version")),
                "instructions_md": as_text(row.get("instructions_md"))[:50000],
                "assets": as_json(row.get("assets"), []),
                "required_tools": _strings(row.get("required_tools")),
                "hash": as_text(row.get("hash"), "0"),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _collections(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO knowledge_collections (
            id, tenant_id, slug, name, description, owner_team_id, visibility, acl_mode,
            sensitivity, classification, embedding_alias, index_version, store_backend,
            store_collection, text_search_config, chunking, stats, created_by, created_at,
                updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :description, :owner_team_id, :visibility, :acl_mode,
            :sensitivity, :classification, :embedding_alias, :index_version, :store_backend,
            :store_collection, :text_search_config, CAST(:chunking AS jsonb), CAST(:stats AS jsonb),
            :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            visibility = EXCLUDED.visibility,
            stats = EXCLUDED.stats,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        collection_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if collection_id is None or tenant_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": collection_id,
                "tenant_id": tenant_id,
                "slug": as_text(row.get("slug"), "library"),
                "name": as_text(row.get("name"), "Library"),
                "description": as_text(row.get("description")),
                "owner_team_id": as_uuid(row.get("owner_team_id")),
                "visibility": as_text(row.get("visibility"), "tenant"),
                "acl_mode": as_text(row.get("acl_mode"), "source"),
                "sensitivity": as_text(row.get("sensitivity"), "normal"),
                "classification": as_text(row.get("classification"), "internal"),
                "embedding_alias": as_text(row.get("embedding_alias"), "embed"),
                "index_version": as_int(row.get("index_version"), 1),
                "store_backend": as_text(row.get("store_backend"), "pgvector"),
                "store_collection": as_text(
                    row.get("store_collection"), f"col-{collection_id.hex[:8]}"
                ),
                "text_search_config": as_text(row.get("text_search_config"), "simple"),
                "chunking": as_json(row.get("chunking"), {"target_tokens": 512, "overlap_pct": 12}),
                "stats": as_json(row.get("stats"), {}),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _sources(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO knowledge_sources (
            id, tenant_id, collection_id, name, kind, config, status, cursor, created_by,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :collection_id, :name, :kind, CAST(:config AS jsonb), :status,
            CAST(:cursor AS jsonb), :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            config = EXCLUDED.config,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        source_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        collection_id = as_uuid(row.get("collection_id"))
        if source_id is None or tenant_id is None or collection_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": source_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "name": as_text(row.get("name"), "Upload"),
                "kind": as_text(row.get("kind"), "upload"),
                "config": as_json(row.get("config"), {}),
                "status": as_text(row.get("status"), "active"),
                "cursor": as_json(row.get("cursor"), {}),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _documents(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO documents (
            id, tenant_id, collection_id, source_id, external_id, uri, title, mime_type,
            version_hash, size_bytes, classification, acl_principals, acl_hash, summary,
            status, error, indexed_at, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :collection_id, :source_id, :external_id, :uri, :title, :mime_type,
            :version_hash, :size_bytes, :classification, :acl_principals, :acl_hash, :summary,
            :status, :error, :indexed_at, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            version_hash = EXCLUDED.version_hash,
            status = EXCLUDED.status,
            summary = EXCLUDED.summary,
            error = EXCLUDED.error,
            indexed_at = EXCLUDED.indexed_at,
            acl_principals = EXCLUDED.acl_principals,
            acl_hash = EXCLUDED.acl_hash,
            classification = EXCLUDED.classification,
            size_bytes = EXCLUDED.size_bytes,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        document_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        collection_id = as_uuid(row.get("collection_id"))
        source_id = as_uuid(row.get("source_id"))
        if None in {document_id, tenant_id, collection_id, source_id}:
            continue
        principals = _strings(row.get("acl_principals"))
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": document_id,
                "tenant_id": tenant_id,
                "collection_id": collection_id,
                "source_id": source_id,
                "external_id": as_text(row.get("external_id"), str(document_id)),
                "uri": as_text(row.get("uri"), f"upload://{document_id}"),
                "title": as_text(row.get("title"), "Document"),
                "mime_type": as_text(row.get("mime_type"), "text/markdown"),
                "version_hash": as_text(row.get("version_hash"), "0"),
                "size_bytes": as_int(row.get("size_bytes")),
                "classification": as_text(row.get("classification"), "internal"),
                "acl_principals": principals,
                "acl_hash": as_text(row.get("acl_hash")),
                "summary": as_text(row.get("summary")),
                "status": _document_status(as_text(row.get("status"), "pending")),
                "error": row.get("error") if isinstance(row.get("error"), str) else None,
                "indexed_at": as_dt(row.get("indexed_at")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


def _document_status(status: str) -> str:
    allowed = {"pending", "parsing", "embedding", "indexed", "failed", "deleted"}
    return status if status in allowed else "pending"


async def _chunks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO document_chunks (
            id, tenant_id, document_id, ordinal, text, context_prefix, heading_path,
            page_from, page_to, token_count, index_version, created_at
        ) VALUES (
            :id, :tenant_id, :document_id, :ordinal, :text, :context_prefix, :heading_path,
            :page_from, :page_to, :token_count, :index_version, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            text = EXCLUDED.text,
            context_prefix = EXCLUDED.context_prefix,
            token_count = EXCLUDED.token_count,
            index_version = EXCLUDED.index_version
    """
    for row in rows:
        chunk_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        document_id = as_uuid(row.get("document_id"))
        if None in {chunk_id, tenant_id, document_id}:
            continue
        headings = _strings(row.get("heading_path"))
        await _one(
            session,
            sql,
            {
                "id": chunk_id,
                "tenant_id": tenant_id,
                "document_id": document_id,
                "ordinal": as_int(row.get("ordinal")),
                "text": as_text(row.get("text"), ""),
                "context_prefix": as_text(row.get("context_prefix"), ""),
                "heading_path": headings,
                "page_from": row.get("page_from")
                if isinstance(row.get("page_from"), int)
                else None,
                "page_to": row.get("page_to") if isinstance(row.get("page_to"), int) else None,
                "token_count": as_int(row.get("token_count")),
                "index_version": as_int(row.get("index_version"), 1),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _facts(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO memory_facts (
            id, tenant_id, scope, user_id, agent_id, team_id, content, category,
            embedding, source_kind, source_ref, trust_level, confidence, status,
            recall_count, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :scope, :user_id, :agent_id, :team_id, :content, :category,
            CAST(:embedding AS vector), :source_kind, CAST(:source_ref AS jsonb),
            :trust_level, :confidence, :status, :recall_count, :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            status = EXCLUDED.status,
            recall_count = EXCLUDED.recall_count,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        fact_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if fact_id is None or tenant_id is None:
            continue
        now = utcnow()
        confidence = row.get("confidence")
        score = float(confidence) if isinstance(confidence, (int, float)) else 1.0
        await _one(
            session,
            sql,
            {
                "id": fact_id,
                "tenant_id": tenant_id,
                "scope": as_text(row.get("scope"), "user"),
                "user_id": as_uuid(row.get("user_id")),
                "agent_id": as_uuid(row.get("agent_id")),
                "team_id": as_uuid(row.get("team_id")),
                "content": as_text(row.get("content"))[:1000],
                "category": as_text(row.get("category"), "fact"),
                "embedding": as_vector(row.get("embedding")),
                "source_kind": as_text(row.get("source_kind"), "explicit"),
                "source_ref": as_json(row.get("source_ref"), {}),
                "trust_level": as_text(row.get("trust_level"), "high"),
                "confidence": max(0.0, min(1.0, score)),
                "status": as_text(row.get("status"), "active"),
                "recall_count": as_int(row.get("recall_count")),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _tool_servers(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO tool_servers (
            id, tenant_id, slug, name, description, kind, owner_user_id, status,
            disabled_at, disabled_reason, current_version_id, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :description, :kind, :owner_user_id, :status,
            :disabled_at, :disabled_reason, :current_version_id, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            current_version_id = EXCLUDED.current_version_id,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        server_id = as_uuid(row.get("id"))
        if server_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": server_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "slug": as_text(row.get("slug")),
                "name": as_text(row.get("name"), "Tools"),
                "description": as_text(row.get("description")),
                "kind": as_text(row.get("kind"), "builtin"),
                "owner_user_id": as_uuid(row.get("owner_user_id")),
                "status": as_text(row.get("status"), "approved"),
                "disabled_at": as_dt(row.get("disabled_at")),
                "disabled_reason": row.get("disabled_reason")
                if isinstance(row.get("disabled_reason"), str)
                else None,
                "current_version_id": as_uuid(row.get("current_version_id")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _tool_server_versions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO tool_server_versions (
            id, tenant_id, tool_server_id, version, endpoint_url, config, auth_mode,
            manifest, manifest_hash, review_status, review_notes, created_by, created_at
        ) VALUES (
            :id, :tenant_id, :tool_server_id, :version, :endpoint_url, CAST(:config AS jsonb),
            :auth_mode, CAST(:manifest AS jsonb), :manifest_hash, :review_status, :review_notes,
            :created_by, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            endpoint_url = EXCLUDED.endpoint_url,
            manifest = EXCLUDED.manifest,
            review_status = EXCLUDED.review_status
    """
    for row in rows:
        version_id = as_uuid(row.get("id"))
        server_id = as_uuid(row.get("tool_server_id"))
        if version_id is None or server_id is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": version_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "tool_server_id": server_id,
                "version": as_text(row.get("version"), "1.0.0"),
                "endpoint_url": as_text(row.get("endpoint_url")) or None,
                "config": as_json(row.get("config"), {}),
                "auth_mode": as_text(row.get("auth_mode"), "none"),
                "manifest": as_json(row.get("manifest"), {}),
                "manifest_hash": as_text(row.get("manifest_hash")),
                "review_status": as_text(row.get("review_status"), "approved"),
                "review_notes": as_text(row.get("review_notes")),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _tools(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO tools (
            id, tenant_id, tool_server_id, name, qualified_name, disabled_at, disabled_reason,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :tool_server_id, :name, :qualified_name, :disabled_at,
            :disabled_reason, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            qualified_name = EXCLUDED.qualified_name,
            disabled_at = EXCLUDED.disabled_at,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        tool_id = as_uuid(row.get("id"))
        server_id = as_uuid(row.get("tool_server_id"))
        if tool_id is None or server_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": tool_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "tool_server_id": server_id,
                "name": as_text(row.get("name"), "tool"),
                "qualified_name": as_text(
                    row.get("qualified_name"), as_text(row.get("name"), "tool")
                ),
                "disabled_at": as_dt(row.get("disabled_at")),
                "disabled_reason": row.get("disabled_reason")
                if isinstance(row.get("disabled_reason"), str)
                else None,
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _tool_versions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO tool_versions (
            id, tenant_id, tool_id, tool_server_version_id, title, description, description_hash,
            input_schema, annotations, risk_class, data_classification, timeout_s,
            rate_limit_per_minute, max_result_bytes, idempotent, approval_preview, embedding,
                created_at
        ) VALUES (
            :id, :tenant_id, :tool_id, :tool_server_version_id, :title, :description,
                :description_hash,
            CAST(:input_schema AS jsonb), CAST(:annotations AS jsonb), :risk_class,
                :data_classification,
            :timeout_s, :rate_limit_per_minute, :max_result_bytes, :idempotent,
            CAST(:approval_preview AS jsonb), CAST(:embedding AS vector), :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for row in rows:
        version_id = as_uuid(row.get("id"))
        tool_id = as_uuid(row.get("tool_id"))
        server_version = as_uuid(row.get("tool_server_version_id"))
        if version_id is None or tool_id is None or server_version is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": version_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "tool_id": tool_id,
                "tool_server_version_id": server_version,
                "title": as_text(row.get("title")),
                "description": as_text(row.get("description"), "Tool"),
                "description_hash": as_text(row.get("description_hash"), "0"),
                "input_schema": as_json(row.get("input_schema"), {}),
                "annotations": as_json(row.get("annotations"), {}),
                "risk_class": as_text(row.get("risk_class"), "R0"),
                "data_classification": as_text(row.get("data_classification"), "internal"),
                "timeout_s": as_int(row.get("timeout_s"), 60),
                "rate_limit_per_minute": as_int(row.get("rate_limit_per_minute"), 60),
                "max_result_bytes": as_int(row.get("max_result_bytes"), 65536),
                "idempotent": as_bool(row.get("idempotent")),
                "approval_preview": as_json(row.get("approval_preview"), {}),
                "embedding": as_vector(row.get("embedding")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _conversations(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO conversations (
            id, tenant_id, user_id, agent_id, agent_version_id, channel, title, status,
            pinned, is_preview, rolling_summary, plan, loaded_skills, active_run_id,
            created_at, updated_at, deleted_at
        ) VALUES (
            :id, :tenant_id, :user_id, :agent_id, :agent_version_id, :channel, :title, :status,
            :pinned, :is_preview, :rolling_summary, CAST(:plan AS jsonb),
                CAST(:loaded_skills AS jsonb),
            NULL, :created_at, :updated_at, :deleted_at
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            status = EXCLUDED.status,
            pinned = EXCLUDED.pinned,
            rolling_summary = EXCLUDED.rolling_summary,
            plan = EXCLUDED.plan,
            loaded_skills = EXCLUDED.loaded_skills,
            agent_version_id = EXCLUDED.agent_version_id,
            updated_at = EXCLUDED.updated_at,
            deleted_at = EXCLUDED.deleted_at
    """
    for row in rows:
        conversation_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        user_id = as_uuid(row.get("user_id"))
        agent_id = as_uuid(row.get("agent_id"))
        if None in {conversation_id, tenant_id, user_id, agent_id}:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": conversation_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "agent_version_id": as_uuid(row.get("agent_version_id")),
                "channel": as_text(row.get("channel"), "web"),
                "title": as_text(row.get("title"), "New chat"),
                "status": as_text(row.get("status"), "active"),
                "pinned": as_bool(row.get("pinned")),
                "is_preview": as_bool(row.get("is_preview")),
                "rolling_summary": as_text(row.get("rolling_summary")),
                "plan": as_json(row.get("plan"), []),
                "loaded_skills": as_json(row.get("loaded_skills"), []),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
                "deleted_at": as_dt(row.get("deleted_at")),
            },
        )


def _version_id(store: object, row: dict[str, Any]) -> uuid.UUID | None:
    found = as_uuid(row.get("agent_version_id"))
    if found is not None:
        return found
    agent_id = as_uuid(row.get("agent_id"))
    agents = getattr(store, "agents", None)
    agent = agents.get(agent_id) if isinstance(agents, dict) and agent_id is not None else None
    if not isinstance(agent, dict):
        return None
    return as_uuid(agent.get("published_version_id")) or as_uuid(agent.get("draft_version_id"))


async def _runs(session: AsyncSession, store: object, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO runs (
            id, tenant_id, conversation_id, agent_id, agent_version_id, parent_run_id,
            root_run_id, depth, trigger, routine_id, user_id, initiator_type, initiator_id,
            input_message_id, status, temporal_workflow_id, budget, callback_url, usage,
            result_summary, error, started_at, ended_at, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :conversation_id, :agent_id, :agent_version_id, :parent_run_id,
            :root_run_id, :depth, :trigger, :routine_id, :user_id, :initiator_type, :initiator_id,
            NULL, :status, :temporal_workflow_id, CAST(:budget AS jsonb), :callback_url,
            CAST(:usage AS jsonb), :result_summary, CAST(:error AS jsonb), :started_at, :ended_at,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            usage = EXCLUDED.usage,
            result_summary = EXCLUDED.result_summary,
            error = EXCLUDED.error,
            started_at = EXCLUDED.started_at,
            ended_at = EXCLUDED.ended_at,
            updated_at = EXCLUDED.updated_at
    """
    for row in _parents_first(rows, "parent_run_id"):
        run_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        agent_id = as_uuid(row.get("agent_id"))
        version_id = _version_id(store, row)
        user_id = as_uuid(row.get("user_id"))
        if None in {run_id, tenant_id, agent_id, version_id, user_id}:
            continue
        now = utcnow()
        trigger = as_text(row.get("trigger"), "chat")
        await _one(
            session,
            sql,
            {
                "id": run_id,
                "tenant_id": tenant_id,
                "conversation_id": as_uuid(row.get("conversation_id")),
                "agent_id": agent_id,
                "agent_version_id": version_id,
                "parent_run_id": as_uuid(row.get("parent_run_id")),
                "root_run_id": as_uuid(row.get("root_run_id")) or run_id,
                "depth": as_int(row.get("depth")),
                "trigger": trigger,
                "routine_id": as_uuid(row.get("routine_id")),
                "user_id": user_id,
                "initiator_type": as_text(
                    row.get("initiator_type"), "routine" if trigger == "routine" else "user"
                ),
                "initiator_id": as_uuid(row.get("initiator_id")) or user_id,
                "status": as_text(row.get("status"), "queued"),
                "temporal_workflow_id": as_text(row.get("temporal_workflow_id"), f"run-{run_id}"),
                "budget": as_json(row.get("budget"), {}),
                "callback_url": row.get("callback_url")
                if isinstance(row.get("callback_url"), str)
                else None,
                "usage": as_json(row.get("usage"), {}),
                "result_summary": row.get("result_summary")
                if isinstance(row.get("result_summary"), str)
                else None,
                "error": as_json(row.get("error"), {})
                if isinstance(row.get("error"), dict)
                else None,
                "started_at": as_dt(row.get("started_at")),
                "ended_at": as_dt(row.get("ended_at")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _messages(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO messages (
            id, tenant_id, conversation_id, run_id, parent_message_id, role, content, status,
            is_active_branch, author_user_id, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :conversation_id, :run_id, :parent_message_id, :role,
            CAST(:content AS jsonb), :status, :is_active_branch, :author_user_id, :created_at,
                :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            content = EXCLUDED.content,
            status = EXCLUDED.status,
            updated_at = EXCLUDED.updated_at
    """
    for row in _parents_first(rows, "parent_message_id"):
        message_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        conversation_id = as_uuid(row.get("conversation_id"))
        if None in {message_id, tenant_id, conversation_id}:
            continue
        content = row.get("content")
        if not isinstance(content, list):
            content = [{"type": "text", "text": as_text(row.get("text"))}]
        elif row.get("role") == "assistant" and isinstance(row.get("text"), str):
            # Streaming updates text before the final content array is assembled.
            content = [
                {"type": "text", "text": row["text"]},
                *(
                    part
                    for part in content
                    if not isinstance(part, dict) or part.get("type") != "text"
                ),
            ]
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": message_id,
                "tenant_id": tenant_id,
                "conversation_id": conversation_id,
                "run_id": as_uuid(row.get("run_id")),
                "parent_message_id": as_uuid(row.get("parent_message_id")),
                "role": as_text(row.get("role"), "user"),
                "content": as_json(content, []),
                "status": as_text(row.get("status"), "completed"),
                "is_active_branch": as_bool(row.get("is_active_branch", True)),
                "author_user_id": as_uuid(row.get("author_user_id")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _link_runs(
    session: AsyncSession,
    runs: list[dict[str, Any]],
    conversations: list[dict[str, Any]],
) -> None:
    for row in runs:
        run_id = as_uuid(row.get("id"))
        message_id = as_uuid(row.get("input_message_id"))
        if run_id is None or message_id is None:
            continue
        await _one(
            session,
            "UPDATE runs SET input_message_id = :message_id WHERE id = :id",
            {"id": run_id, "message_id": message_id},
        )
    for row in conversations:
        conversation_id = as_uuid(row.get("id"))
        run_id = as_uuid(row.get("active_run_id"))
        if conversation_id is None:
            continue
        await _one(
            session,
            "UPDATE conversations SET active_run_id = :run_id WHERE id = :id",
            {"id": conversation_id, "run_id": run_id},
        )


def _run_tenant(store: object, run_id: uuid.UUID) -> uuid.UUID | None:
    runs = getattr(store, "runs", None)
    run = runs.get(run_id) if isinstance(runs, dict) else None
    if not isinstance(run, dict):
        return None
    return as_uuid(run.get("tenant_id"))


async def _events(session: AsyncSession, store: object, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO run_events (tenant_id, run_id, seq, type, data, created_at)
        VALUES (:tenant_id, :run_id, :seq, :type, CAST(:data AS jsonb), :created_at)
        ON CONFLICT (run_id, seq) DO NOTHING
    """
    for bundle in rows:
        events = bundle.get("_events")
        if not isinstance(events, list):
            continue
        for event in events:
            if not isinstance(event, dict):
                continue
            run_id = as_uuid(event.get("run_id")) or as_uuid(bundle.get("_key"))
            if run_id is None:
                continue
            data = event.get("data") if isinstance(event.get("data"), dict) else {}
            tenant_id = as_uuid(event.get("tenant_id")) or _run_tenant(store, run_id)
            if tenant_id is None:
                continue
            await _one(
                session,
                sql,
                {
                    "tenant_id": tenant_id,
                    "run_id": run_id,
                    "seq": as_int(event.get("seq"), 1),
                    "type": as_text(event.get("type"), "run.queued"),
                    "data": as_json(data, {}),
                    "created_at": as_dt(event.get("ts")) or utcnow(),
                },
            )


async def _channel_integrations(
    session: AsyncSession, rows: list[dict[str, Any]], store: object
) -> None:
    sql = """
        INSERT INTO channel_integrations (
            id, tenant_id, kind, name, config, secret_ref_id, default_agent_id,
            agent_routing, status, status_detail, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :kind, :name, CAST(:config AS jsonb), :secret_ref_id,
            :default_agent_id, CAST(:agent_routing AS jsonb), :status, :status_detail,
            :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            config = EXCLUDED.config,
            secret_ref_id = EXCLUDED.secret_ref_id,
            default_agent_id = EXCLUDED.default_agent_id,
            agent_routing = EXCLUDED.agent_routing,
            status = EXCLUDED.status,
            status_detail = EXCLUDED.status_detail,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        integration_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if integration_id is None or tenant_id is None:
            continue
        from ar_domain.secrets.cached import save_cached_secret  # noqa: PLC0415

        secret_id = as_uuid(row.get("secret_ref_id"))
        value = getattr(store, "secret_values", {}).get(secret_id)
        if secret_id is not None and isinstance(value, bytes):
            await save_cached_secret(
                session,
                tenant_id=tenant_id,
                secret_id=secret_id,
                value=value,
                user_id=as_uuid(row.get("created_by")),
            )
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": integration_id,
                "tenant_id": tenant_id,
                "kind": as_text(row.get("kind"), "slack"),
                "secret_ref_id": secret_id,
                "name": as_text(row.get("name"), "Channel"),
                "config": as_json(row.get("config"), {}),
                "default_agent_id": as_uuid(row.get("default_agent_id")),
                "agent_routing": as_json(row.get("agent_routing"), []),
                "status": as_text(row.get("status"), "active"),
                "status_detail": as_text(row.get("status_detail"), ""),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _channel_identities(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO channel_identities (
            id, tenant_id, integration_id, external_user_id, user_id,
            match_method, verified_at, created_at
        ) VALUES (
            :id, :tenant_id, :integration_id, :external_user_id, :user_id,
            :match_method, :verified_at, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            match_method = EXCLUDED.match_method,
            verified_at = EXCLUDED.verified_at
    """
    for row in rows:
        identity_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        integration_id = as_uuid(row.get("integration_id"))
        user_id = as_uuid(row.get("user_id"))
        if None in {identity_id, tenant_id, integration_id, user_id}:
            continue
        await _one(
            session,
            sql,
            {
                "id": identity_id,
                "tenant_id": tenant_id,
                "integration_id": integration_id,
                "external_user_id": as_text(row.get("external_user_id")),
                "user_id": user_id,
                "match_method": as_text(row.get("match_method"), "manual_link"),
                "verified_at": as_dt(row.get("verified_at")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _channel_threads(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO channel_threads (
            id, tenant_id, integration_id, external_channel_id, external_thread_id,
            conversation_id, created_at
        ) VALUES (
            :id, :tenant_id, :integration_id, :external_channel_id, :external_thread_id,
            :conversation_id, :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for row in rows:
        thread_id = as_uuid(row.get("id"))
        if thread_id is None or as_uuid(row.get("conversation_id")) is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": thread_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "integration_id": as_uuid(row.get("integration_id")),
                "external_channel_id": as_text(row.get("external_channel_id")),
                "external_thread_id": as_text(row.get("external_thread_id")),
                "conversation_id": as_uuid(row.get("conversation_id")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def _channel_posts(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO channel_posts (
            id, tenant_id, integration_id, thread_id, direction, kind,
            external_message_id, body, status, detail, created_at
        ) VALUES (
            :id, :tenant_id, :integration_id, :thread_id, :direction, :kind,
            :external_message_id, :body, :status, CAST(:detail AS jsonb), :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for row in rows:
        post_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if post_id is None or tenant_id is None:
            continue
        await _one(
            session,
            sql,
            {
                "id": post_id,
                "tenant_id": tenant_id,
                "integration_id": as_uuid(row.get("integration_id")),
                "thread_id": as_uuid(row.get("thread_id")),
                "direction": as_text(row.get("direction"), "outbound"),
                "kind": as_text(row.get("kind"), "slack"),
                "external_message_id": as_text(row.get("external_message_id")),
                "body": as_text(row.get("body")),
                "status": as_text(row.get("status"), "posted"),
                "detail": as_json(row.get("detail"), {}),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


def mark_all_dirty(store: object) -> None:
    """Flush the catalogue that is already in memory."""
    for name in BUCKETS:
        bucket = getattr(store, name, None)
        if isinstance(bucket, TrackedDict):
            bucket.dirty.update(bucket.keys())


def event_tenant(store: object, run_id: uuid.UUID) -> None:
    """Stamp tenant_id onto events so the flush can satisfy the column."""
    runs = getattr(store, "runs", {})
    events = getattr(store, "events", {})
    run = runs.get(run_id) if isinstance(runs, dict) else None
    rows = events.get(run_id) if isinstance(events, dict) else None
    if not isinstance(run, dict) or not isinstance(rows, list):
        return
    tenant_id = run.get("tenant_id")
    for event in rows:
        if isinstance(event, dict) and "tenant_id" not in event:
            event["tenant_id"] = tenant_id


async def _routine_audits(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    from typing import cast  # noqa: PLC0415

    from ar_domain.audit.service import record  # noqa: PLC0415

    for row in rows:
        tenant_id = as_uuid(row.get("tenant_id"))
        if tenant_id is not None:
            await record(
                session,
                tenant_id=tenant_id,
                actor_type="user",
                actor_id=str(row["actor_id"]),
                action=cast("AuditAction", row["action"]),
                target_type="routine",
                target_id=str(row["target_id"]),
                detail=row.get("detail") or {},
            )
