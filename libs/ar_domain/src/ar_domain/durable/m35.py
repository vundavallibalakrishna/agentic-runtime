"""Flush and hydrate file bytes, workspace files, jobs and A2A push configs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import bindparam, text

from ar_domain.durability.store import materialise_file
from ar_domain.durable.codec import as_dt, as_int, as_text, as_uuid

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

_JOB_KIND = {"ocr", "pdf", "query", "workspace"}
_JOB_STATUS = {"running", "completed", "interrupted", "failed"}


async def save_durability(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    await _blobs(session, pending.get("file_blobs", []))
    await _workspace(session, pending.get("workspace_files", []))
    await _jobs(session, pending.get("job_progress", []))
    await _push(session, pending.get("a2a_push_configs", []))


async def load_conversation_files(
    session: AsyncSession,
    store: object,
    tenant_id: uuid.UUID,
    conversation_id: object,
    attached: list[uuid.UUID],
) -> None:
    """Bring in the conversation's files this process has not seen yet.

    A file is uploaded through the API and attached to a message, and a tool writes a
    file in the worker. Whichever process serves the next request learns of both here,
    so a turn can read what was attached and a download finds what a turn wrote.
    """
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    held = getattr(store, "files", None)
    if not isinstance(held, dict):
        return
    made = await session.execute(
        text(
            "SELECT id FROM file_blobs "
            "WHERE tenant_id = :tenant_id AND conversation_id = :conversation_id"
        ),
        {"tenant_id": tenant_id, "conversation_id": conversation_id},
    )
    wanted = [*attached, *(row[0] for row in made)]
    missing = [file_id for file_id in dict.fromkeys(wanted) if file_id not in held]
    if not missing:
        return
    found = await session.execute(
        text("SELECT * FROM file_blobs WHERE tenant_id = :tenant_id AND id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"tenant_id": tenant_id, "ids": missing},
    )
    for mapping in found.mappings():
        row = dict(mapping)
        if isinstance(row.get("body"), memoryview):
            row["body"] = row["body"].tobytes()
        _merge(store, "file_blobs", row["id"], row)
        materialise_file(store, row)


async def load_durability(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    queries = (
        "SELECT * FROM file_blobs WHERE tenant_id = :tenant_id",
        "SELECT * FROM workspace_files WHERE tenant_id = :tenant_id",
        "SELECT * FROM job_progress WHERE tenant_id = :tenant_id",
        "SELECT * FROM a2a_push_configs WHERE tenant_id = :tenant_id",
    )
    names = ("file_blobs", "workspace_files", "job_progress", "a2a_push_configs")
    for name, sql in zip(names, queries, strict=True):
        result = await session.execute(text(sql), {"tenant_id": tenant_id})
        for mapping in result.mappings():
            row = dict(mapping)
            if "body" in row and isinstance(row["body"], memoryview):
                row["body"] = row["body"].tobytes()
            _merge(store, name, row["id"], row)
            if name == "file_blobs":
                materialise_file(store, row)


async def _blobs(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO file_blobs (
            id, tenant_id, owner_user_id, conversation_id, run_id, name, mime_type, sha256,
            size_bytes, kind, body, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :owner_user_id, :conversation_id, :run_id, :name, :mime_type, :sha256,
            :size_bytes, :kind, :body, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            mime_type = EXCLUDED.mime_type,
            sha256 = EXCLUDED.sha256,
            size_bytes = EXCLUDED.size_bytes,
            kind = EXCLUDED.kind,
            body = EXCLUDED.body,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        body = _bytes(row.get("body"))
        item_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if item_id is None or tenant_id is None or not body or len(body) > 8 * 1024 * 1024:
            continue
        await session.execute(
            text(sql),
            {
                "id": item_id,
                "tenant_id": tenant_id,
                "owner_user_id": as_uuid(row.get("owner_user_id")),
                "conversation_id": as_uuid(row.get("conversation_id")),
                "run_id": as_uuid(row.get("run_id")),
                "name": as_text(row.get("name"), "file")[:240],
                "mime_type": as_text(row.get("mime_type"), "application/octet-stream")[:200],
                "sha256": as_text(row.get("sha256"))[:80],
                "size_bytes": len(body),
                "kind": as_text(row.get("kind"), "upload")[:40],
                "body": body,
                "created_at": as_dt(row.get("created_at")),
                "updated_at": as_dt(row.get("updated_at")),
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
