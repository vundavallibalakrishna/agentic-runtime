"""Flush and hydrate file bytes, workspace files, jobs and A2A push configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import bindparam, text

from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

_JOB_KIND = {"ocr", "pdf", "query", "workspace"}
_JOB_STATUS = {"running", "completed", "interrupted", "failed"}


async def save_durability(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    await _files(session, pending.get("files", []))
    await _workspace(session, pending.get("workspace_files", []))
    await _jobs(session, pending.get("job_progress", []))
    await _push(session, pending.get("a2a_push_configs", []))
    await _tool_vectors(session, pending.get("tool_search_vectors", []))


async def _tool_vectors(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO tool_search_vectors (
            id, tenant_id, model_id, text_hash, vector, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :model_id, :text_hash, CAST(:vector AS jsonb),
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            vector = EXCLUDED.vector,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        if row.get("_deleted"):
            continue
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        model_id = as_text(row.get("model_id"))
        text_hash = as_text(row.get("text_hash"))
        vector = row.get("vector")
        if None in {item_id, tenant_id} or not model_id or not text_hash:
            continue
        if not isinstance(vector, list) or not vector:
            continue
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "model_id": model_id,
                "text_hash": text_hash,
                "vector": as_json(vector, []),
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )


async def load_conversation_files(
    session: AsyncSession,
    store: object,
    tenant_id: uuid.UUID,
    conversation_id: object,
    attached: list[uuid.UUID],
) -> None:
    """Bring in the rows of the conversation's files this process has not seen yet.

    A file is uploaded through the API and attached to a message, and a tool writes a
    file in the worker. Whichever process serves the next request learns of both here,
    so a turn can read what was attached and a download finds what a turn wrote. Only
    the rows come in; a file's bytes are fetched from the object store when needed.
    """
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    held = getattr(store, "files", None)
    if not isinstance(held, dict):
        return
    made = await session.execute(
        text(
            "SELECT id FROM files WHERE tenant_id = :tenant_id "
            "AND conversation_id = :conversation_id AND deleted_at IS NULL"
        ),
        {"tenant_id": tenant_id, "conversation_id": conversation_id},
    )
    wanted = [*attached, *(row[0] for row in made)]
    missing = [file_id for file_id in dict.fromkeys(wanted) if file_id not in held]
    if not missing:
        return
    found = await session.execute(
        text("SELECT * FROM files WHERE tenant_id = :tenant_id AND id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"tenant_id": tenant_id, "ids": missing},
    )
    for mapping in found.mappings():
        row = dict(mapping)
        _merge(store, "files", row["id"], row)
    await _legacy_rows(session, store, tenant_id, [item for item in missing if item not in held])


async def _legacy_rows(
    session: AsyncSession, store: object, tenant_id: uuid.UUID, ids: list[uuid.UUID] | None
) -> None:
    """Move files a release before this one kept in ``file_blobs`` to the object store.

    Those bytes are in Postgres and the ``files`` table is empty for them. Here, the one
    place with an async session to read the bytes, each blob is copied to the object store
    and written to ``files``; after the next flush the ``files`` SELECT finds the row and
    this does nothing. The blob row stays until a later revision drops the table. This
    reads a transitional, shrinking set, not every file of the tenant each start
    ([OQ-112](../../../../docs/open-questions.md)).
    """
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415
    from ar_domain.files.logic import object_key  # noqa: PLC0415
    from ar_domain.files.objects import keep_bytes  # noqa: PLC0415

    held = getattr(store, "files", None)
    if not isinstance(held, dict) or ids == []:
        return
    sql = (
        "SELECT id, tenant_id, owner_user_id, conversation_id, run_id, name, mime_type, "
        "sha256, size_bytes, kind, body, created_at FROM file_blobs WHERE tenant_id = :tenant_id"
    )
    params: dict[str, Any] = {"tenant_id": tenant_id}
    statement = text(sql)
    if ids is not None:
        statement = text(sql + " AND id IN :ids").bindparams(bindparam("ids", expanding=True))
        params["ids"] = ids
    found = await session.execute(statement, params)
    for mapping in found.mappings():
        blob = dict(mapping)
        file_id = blob["id"]
        if file_id in held:
            continue
        body = blob.get("body")
        if isinstance(body, memoryview):
            body = body.tobytes()
        if not isinstance(body, bytes):
            continue
        made = blob.get("created_at")
        year = f"{made:%Y}" if made else "0000"
        month = f"{made:%m}" if made else "00"
        kind = str(blob.get("kind") or "upload")
        row = {
            "id": file_id,
            "tenant_id": blob.get("tenant_id"),
            "owner_user_id": blob.get("owner_user_id"),
            "conversation_id": blob.get("conversation_id"),
            "run_id": blob.get("run_id"),
            "kind": kind,
            "name": blob.get("name") or "file",
            "mime_type": blob.get("mime_type") or "application/octet-stream",
            "size_bytes": blob.get("size_bytes") or len(body),
            "sha256": blob.get("sha256"),
            "object_key": object_key(str(tenant_id), kind, year, month, str(file_id)),
            "status": "ready",
            "scan_status": "skipped",
            "preview": {},
            "created_at": made,
            "deleted_at": None,
        }
        keep_bytes(store, row, body)
        _merge(store, "files", file_id, row)
        # Hydrate loads without marking rows dirty; this row is new to ``files`` and must
        # be flushed, so mark it so the next flush writes it.
        dirty = getattr(held, "dirty", None)
        if isinstance(dirty, set):
            dirty.add(file_id)


async def load_durability(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    queries = (
        "SELECT * FROM files WHERE tenant_id = :tenant_id AND deleted_at IS NULL",
        "SELECT * FROM workspace_files WHERE tenant_id = :tenant_id",
        "SELECT * FROM job_progress WHERE tenant_id = :tenant_id",
        "SELECT * FROM a2a_push_configs WHERE tenant_id = :tenant_id",
        "SELECT * FROM tool_search_vectors WHERE tenant_id = :tenant_id",
    )
    names = (
        "files",
        "workspace_files",
        "job_progress",
        "a2a_push_configs",
        "tool_search_vectors",
    )
    for name, sql in zip(names, queries, strict=True):
        result = await session.execute(text(sql), {"tenant_id": tenant_id})
        for mapping in result.mappings():
            row = dict(mapping)
            if "body" in row and isinstance(row["body"], memoryview):
                row["body"] = row["body"].tobytes()
            _merge(store, name, row["id"], row)
    await _legacy_rows(session, store, tenant_id, None)


_FILE_KINDS = frozenset(
    {
        "upload",
        "artifact",
        "tool_result",
        "sandbox_snapshot",
        "knowledge_raw",
        "knowledge_parsed",
        "skill_asset",
        "avatar",
        "export",
        "openapi_spec",
        "eval_dataset",
        "event_payload",
    }
)
_FILE_STATUS = frozenset({"pending_upload", "ready", "quarantined", "deleted"})
_SCAN_STATUS = frozenset({"pending", "clean", "infected", "skipped", "error"})
_CLASSIFICATIONS = frozenset({"public", "internal", "confidential", "restricted"})


async def _files(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """A file's row. Its bytes are in the object store under ``object_key``."""
    sql = """
        INSERT INTO files (
            id, tenant_id, owner_user_id, conversation_id, run_id, kind, name, mime_type,
            size_bytes, sha256, object_key, classification, status, scan_status, preview,
            retention_until, created_at, updated_at, deleted_at
        ) VALUES (
            :id, :tenant_id, :owner_user_id, :conversation_id, :run_id, :kind, :name, :mime_type,
            :size_bytes, :sha256, :object_key, :classification, :status, :scan_status,
            CAST(:preview AS jsonb), :retention_until, :created_at, :updated_at, :deleted_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            mime_type = EXCLUDED.mime_type,
            size_bytes = EXCLUDED.size_bytes,
            sha256 = EXCLUDED.sha256,
            classification = EXCLUDED.classification,
            status = EXCLUDED.status,
            scan_status = EXCLUDED.scan_status,
            preview = EXCLUDED.preview,
            retention_until = EXCLUDED.retention_until,
            updated_at = EXCLUDED.updated_at,
            deleted_at = EXCLUDED.deleted_at
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        key = as_text(row.get("object_key"))
        if item_id is None or tenant_id is None or not key:
            continue
        kind = as_text(row.get("kind"), "upload")
        status = as_text(row.get("status"), "ready")
        scan = as_text(row.get("scan_status"), "skipped")
        classification = as_text(row.get("classification"), "internal")
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "owner_user_id": as_uuid(row.get("owner_user_id")),
                "conversation_id": as_uuid(row.get("conversation_id")),
                "run_id": as_uuid(row.get("run_id")),
                "kind": kind if kind in _FILE_KINDS else "upload",
                "name": as_text(row.get("name"), "file")[:240],
                "mime_type": as_text(row.get("mime_type"), "application/octet-stream")[:200],
                "size_bytes": as_int(row.get("size_bytes")),
                "sha256": as_text(row.get("sha256"))[:80] or None,
                "object_key": key,
                "classification": (
                    classification if classification in _CLASSIFICATIONS else "internal"
                ),
                "status": status if status in _FILE_STATUS else "ready",
                "scan_status": scan if scan in _SCAN_STATUS else "skipped",
                "preview": as_json(row.get("preview"), {}),
                "retention_until": as_dt(row.get("retention_until")),
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")) or as_dt(row.get("created_at")),
                "deleted_at": as_dt(row.get("deleted_at")),
            },
        )


async def _workspace(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO workspace_files (
            id, tenant_id, run_id, path, body, size_bytes, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :run_id, :path, :body, :size_bytes, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            path = EXCLUDED.path,
            body = EXCLUDED.body,
            size_bytes = EXCLUDED.size_bytes,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        body = _bytes(row.get("body"))
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        run_id = as_uuid(row.get("run_id"))
        path = as_text(row.get("path"))
        if None in {item_id, tenant_id, run_id} or not body or not path or ".." in path.split("/"):
            continue
        if len(body) > 2 * 1024 * 1024:
            continue
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "run_id": run_id,
                "path": path[:240],
                "body": body,
                "size_bytes": len(body),
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )


async def _jobs(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO job_progress (
            id, tenant_id, run_id, conversation_id, tool_name, kind, label, completed, total,
            status, detail, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :run_id, :conversation_id, :tool_name, :kind, :label, :completed,
            :total, :status, :detail, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            completed = EXCLUDED.completed,
            total = EXCLUDED.total,
            status = EXCLUDED.status,
            detail = EXCLUDED.detail,
            label = EXCLUDED.label,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        kind = as_text(row.get("kind"))
        status = as_text(row.get("status"), "running")
        if item_id is None or tenant_id is None or kind not in _JOB_KIND:
            continue
        if status not in _JOB_STATUS:
            status = "running"
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "run_id": as_uuid(row.get("run_id")),
                "conversation_id": as_uuid(row.get("conversation_id")),
                "tool_name": as_text(row.get("tool_name"))[:120],
                "kind": kind,
                "label": as_text(row.get("label"), "Job")[:200],
                "completed": as_int(row.get("completed")),
                "total": as_int(row.get("total")),
                "status": status,
                "detail": as_text(row.get("detail"))[:500],
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )


async def _push(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO a2a_push_configs (
            id, tenant_id, task_id, key_id, config_id, url, token, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :task_id, :key_id, :config_id, :url, :token, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            url = EXCLUDED.url,
            token = EXCLUDED.token,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        task_id = as_uuid(row.get("task_id"))
        key_id = as_uuid(row.get("key_id"))
        url = as_text(row.get("url"))
        if None in {item_id, tenant_id, task_id, key_id} or not url:
            continue
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "task_id": task_id,
                "key_id": key_id,
                "config_id": as_text(row.get("config_id"), "default")[:64],
                "url": url[:500],
                "token": as_text(row.get("token"))[:256],
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
            },
        )


def _bytes(value: object) -> bytes:
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return b""
