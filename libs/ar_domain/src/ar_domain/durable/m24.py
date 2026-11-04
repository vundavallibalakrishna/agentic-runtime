"""Flush and hydrate the document library."""

from __future__ import annotations

from typing import TYPE_CHECKING

import orjson
from sqlalchemy import text

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession


def _json_value(value: object, default: object) -> object:
    if isinstance(value, str):
        try:
            parsed = orjson.loads(value)
        except orjson.JSONDecodeError:
            return default
        return parsed
    if isinstance(value, (dict, list)):
        return value
    return default


async def _one(session: AsyncSession, sql: str, params: dict[str, object]) -> None:
    await session.execute(text(sql), params)


async def save_library_documents(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO library_documents (
            id, tenant_id, owner_user_id, title, filename, media_type, source, source_ref,
            content_hash, size_bytes, status, error_code, error_message, page_count,
            metadata, passages, tables, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :owner_user_id, :title, :filename, :media_type, :source, :source_ref,
            :content_hash, :size_bytes, :status, :error_code, :error_message, :page_count,
            CAST(:metadata AS jsonb), CAST(:passages AS jsonb), CAST(:tables AS jsonb),
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            title = EXCLUDED.title,
            status = EXCLUDED.status,
            error_code = EXCLUDED.error_code,
            error_message = EXCLUDED.error_message,
            page_count = EXCLUDED.page_count,
            metadata = EXCLUDED.metadata,
            passages = EXCLUDED.passages,
            tables = EXCLUDED.tables,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        document_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        owner_id = as_uuid(row.get("owner_user_id"))
        if document_id is None or tenant_id is None or owner_id is None:
            continue
        now = utcnow()
        await _one(
            session,
            sql,
            {
                "id": document_id,
                "tenant_id": tenant_id,
                "owner_user_id": owner_id,
                "title": as_text(row.get("title"), "Document"),
                "filename": as_text(row.get("filename"), "upload"),
                "media_type": as_text(row.get("media_type"), "text/plain"),
                "source": as_text(row.get("source"), "upload"),
                "source_ref": as_text(row.get("source_ref")),
                "content_hash": as_text(row.get("content_hash")),
                "size_bytes": as_int(row.get("size_bytes")),
                "status": as_text(row.get("status"), "ready"),
                "error_code": row.get("error_code"),
                "error_message": row.get("error_message"),
                "page_count": as_int(row.get("page_count")),
                "metadata": as_json(row.get("metadata"), {}),
                "passages": as_json(row.get("passages"), []),
                "tables": as_json(row.get("tables"), []),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_document_checks(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO document_checks (
            id, tenant_id, document_id, standard_document_id, label, rows, created_by,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :document_id, :standard_document_id, :label, CAST(:rows AS jsonb),
            :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            label = EXCLUDED.label,
            rows = EXCLUDED.rows,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        await _child(
            session,
            sql,
            row,
            {
                "document_id": as_uuid(row.get("document_id")),
                "standard_document_id": as_uuid(row.get("standard_document_id")),
                "label": as_text(row.get("label"), "Check"),
                "rows": as_json(row.get("rows"), {}),
            },
        )


async def save_document_comparisons(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO document_comparisons (
            id, tenant_id, left_id, right_id, changes, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :left_id, :right_id, CAST(:changes AS jsonb), :created_by,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            changes = EXCLUDED.changes,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        left_id = as_uuid(row.get("left_id"))
        right_id = as_uuid(row.get("right_id"))
        if left_id is None or right_id is None:
            continue
        await _child(
            session,
            sql,
            row,
            {"left_id": left_id, "right_id": right_id, "changes": as_json(row.get("changes"), {})},
        )


async def save_document_rewrites(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO document_rewrites (
            id, tenant_id, document_id, anchor, passage_anchors, instruction, original,
            proposed, hunks, status, created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :document_id, :anchor, CAST(:passage_anchors AS jsonb), :instruction,
            :original, :proposed, CAST(:hunks AS jsonb), :status, :created_by, :created_at,
            :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            hunks = EXCLUDED.hunks,
            status = EXCLUDED.status,
            proposed = EXCLUDED.proposed,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        document_id = as_uuid(row.get("document_id"))
        if document_id is None:
            continue
        await _child(
            session,
            sql,
            row,
            {
                "document_id": document_id,
                "anchor": as_text(row.get("anchor")),
                "passage_anchors": as_json(row.get("passage_anchors"), []),
                "instruction": as_text(row.get("instruction")),
                "original": as_text(row.get("original")),
                "proposed": as_text(row.get("proposed")),
                "hunks": as_json(row.get("hunks"), []),
                "status": as_text(row.get("status"), "proposed"),
            },
        )


async def _child(
    session: AsyncSession, sql: str, row: dict[str, Any], extra: dict[str, object]
) -> None:
    item_id = as_uuid(row.get("id"))
    tenant_id = as_uuid(row.get("tenant_id"))
    if item_id is None or tenant_id is None:
        return
    now = utcnow()
    params: dict[str, object] = {
        "id": item_id,
        "tenant_id": tenant_id,
        "created_by": as_uuid(row.get("created_by")),
        "created_at": as_dt(row.get("created_at")) or now,
        "updated_at": as_dt(row.get("updated_at")) or now,
    }
    params.update(extra)
    await _one(session, sql, params)


async def load_library(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    from ar_domain.durable.hydrate import _merge, _rows  # noqa: PLC0415

    documents = await _rows(
        session, "SELECT * FROM library_documents WHERE tenant_id = :tenant_id", tenant_id
    )
    for row in documents:
        row["metadata"] = _json_value(row.get("metadata"), {})
        row["passages"] = _json_value(row.get("passages"), [])
        row["tables"] = _json_value(row.get("tables"), [])
        _merge(store, "library_documents", row["id"], row)
    checks = await _rows(
        session, "SELECT * FROM document_checks WHERE tenant_id = :tenant_id", tenant_id
    )
    for row in checks:
        row["rows"] = _json_value(row.get("rows"), {})
        _merge(store, "document_checks", row["id"], row)
    comparisons = await _rows(
        session, "SELECT * FROM document_comparisons WHERE tenant_id = :tenant_id", tenant_id
    )
    for row in comparisons:
        row["changes"] = _json_value(row.get("changes"), {})
        _merge(store, "document_comparisons", row["id"], row)
    rewrites = await _rows(
        session, "SELECT * FROM document_rewrites WHERE tenant_id = :tenant_id", tenant_id
    )
    for row in rewrites:
        row["passage_anchors"] = _json_value(row.get("passage_anchors"), [])
        row["hunks"] = _json_value(row.get("hunks"), [])
        _merge(store, "document_rewrites", row["id"], row)
