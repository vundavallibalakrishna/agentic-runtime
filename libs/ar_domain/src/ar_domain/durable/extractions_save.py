"""Flush and load ``document_extractions``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from ar_common.time import utcnow
from ar_domain.durable.codec import as_dt, as_json, as_text, as_uuid

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def save_extractions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO document_extractions (
            id, tenant_id, document_id, content_hash, schema_hash, model_alias,
            strategy, fields, result, corrections, approval_id, run_id, status, created_at
        ) VALUES (
            :id, :tenant_id, :document_id, :content_hash, :schema_hash, :model_alias,
            :strategy, CAST(:fields AS jsonb), CAST(:result AS jsonb),
            CAST(:corrections AS jsonb), :approval_id, :run_id, :status, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            fields = EXCLUDED.fields,
            result = EXCLUDED.result,
            corrections = EXCLUDED.corrections,
            approval_id = EXCLUDED.approval_id,
            status = EXCLUDED.status
    """
    for row in rows:
        extraction_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        document_id = as_uuid(row.get("document_id"))
        if extraction_id is None or tenant_id is None or document_id is None:
            continue
        await session.execute(
            text(sql),
            {
                "id": extraction_id,
                "tenant_id": tenant_id,
                "document_id": document_id,
                "content_hash": as_text(row.get("content_hash")),
                "schema_hash": as_text(row.get("schema_hash")),
                "model_alias": as_text(row.get("model_alias")),
                "strategy": as_text(row.get("strategy")),
                "fields": as_json(row.get("fields"), []),
                "result": as_json(row.get("result"), {}),
                "corrections": as_json(row.get("corrections"), []),
                "approval_id": as_uuid(row.get("approval_id")),
                "run_id": as_uuid(row.get("run_id")),
                "status": as_text(row.get("status"), "done"),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def save_settings(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO resource_settings (
            id, tenant_id, resource_type, resource_id, version, "schema",
            document, created_by, created_at
        ) VALUES (
            :id, :tenant_id, :resource_type, :resource_id, :version, CAST(:schema AS jsonb),
            CAST(:document AS jsonb), :created_by, :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for row in rows:
        setting_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if setting_id is None or tenant_id is None:
            continue
        await session.execute(
            text(sql),
            {
                "id": setting_id,
                "tenant_id": tenant_id,
                "resource_type": as_text(row.get("resource_type")),
                "resource_id": as_text(row.get("resource_id")),
                "version": int(row.get("version") or 1),
                "schema": as_json(row.get("schema"), {}),
                "document": as_json(row.get("document"), {}),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )
