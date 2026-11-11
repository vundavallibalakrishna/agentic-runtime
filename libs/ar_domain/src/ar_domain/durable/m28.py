"""Flush and hydrate tool calls, policies, approvals, sandboxes and human questions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ar_common.time import utcnow
from ar_domain.durable.codec import as_bool, as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

_TOOL_STATUSES = {
    "pending",
    "awaiting_approval",
    "running",
    "succeeded",
    "failed",
    "denied",
    "rejected",
    "expired",
    "cancelled",
}
_DECISIONS = {"allow", "deny", "require_approval"}
_TERMINAL_CALLS = frozenset({"succeeded", "failed", "denied", "rejected", "expired", "cancelled"})


async def save_runtime_rows(
    session: AsyncSession, store: object, pending: dict[str, list[dict[str, Any]]]
) -> dict[uuid.UUID, uuid.UUID]:
    await save_policies(session, pending.get("policies", []), pending.get("policy_versions", []))
    await save_sandbox_templates(session, store, pending.get("sandboxes", []))
    await save_sandboxes(session, pending.get("sandboxes", []))
    adopted = await save_tool_calls(session, pending.get("tool_calls", []))
    await save_approvals(session, pending.get("approvals", []))
    await save_approval_links(session, pending.get("tool_calls", []))
    await save_approval_decisions(session, pending.get("approval_decisions", []))
    await save_human_questions(session, pending.get("human_questions", []))
    return adopted


async def load_runtime_rows(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    await _load(
        session,
        store,
        "tool_calls",
        "SELECT * FROM tool_calls WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session, store, "policies", "SELECT * FROM policies WHERE tenant_id = :tenant_id", tenant_id
    )
    await _load(
        session,
        store,
        "policy_versions",
        "SELECT * FROM policy_versions WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "approvals",
        "SELECT * FROM approvals WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "approval_decisions",
        "SELECT * FROM approval_decisions WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "sandboxes",
        "SELECT * FROM sandboxes WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load(
        session,
        store,
        "human_questions",
        "SELECT * FROM human_questions WHERE tenant_id = :tenant_id",
        tenant_id,
    )
    await _load_templates(session, store)


_TOOL_UPSERT = """
    INSERT INTO tool_calls (
        id, tenant_id, run_id, tool_id, tool_version_id, qualified_name, model_call_id,
        arguments_redacted, args_hash, risk_class, policy_decision, status, idempotency_key,
        result_preview, is_error, error, latency_ms, created_at
    ) VALUES (
        :id, :tenant_id, :run_id, :tool_id, :tool_version_id, :qualified_name, :model_call_id,
        CAST(:arguments_redacted AS jsonb), :args_hash, :risk_class, :policy_decision, :status,
        :idempotency_key, :result_preview, :is_error, CAST(:error AS jsonb), :latency_ms,
        :created_at
    )
    ON CONFLICT (id) DO UPDATE SET
        status = EXCLUDED.status,
        result_preview = EXCLUDED.result_preview,
        is_error = EXCLUDED.is_error,
        error = EXCLUDED.error,
        latency_ms = EXCLUDED.latency_ms,
        idempotency_key = EXCLUDED.idempotency_key
"""

_TOOL_UPDATE = """
    UPDATE tool_calls SET
        status = :status,
        result_preview = :result_preview,
        is_error = :is_error,
        error = CAST(:error AS jsonb),
        latency_ms = :latency_ms
    WHERE id = :id AND tenant_id = :tenant_id
"""


async def save_tool_calls(
    session: AsyncSession, rows: list[dict[str, Any]]
) -> dict[uuid.UUID, uuid.UUID]:
    """Insert tool calls. A retry with the same idempotency key adopts the stored row.

    The primary key is the row id. The logical identity is ``(tenant_id,
    idempotency_key)``. A second attempt mints a new id for the same call; that
    must not abort the transaction. A finished call keeps the result it stored.
    """
    adopted: dict[uuid.UUID, uuid.UUID] = {}
    for row in rows:
        call_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        run_id = as_uuid(row.get("run_id"))
        if call_id is None or tenant_id is None or run_id is None:
            continue
        present = await session.execute(
            text("SELECT 1 FROM runs WHERE id = :id"),
            {"id": run_id},
        )
        if present.first() is None:
            # The console used to keep a run that flush cannot store. Inserting
            # the call anyway aborts the transaction and then every later save.
            continue
        params = _tool_params(row, call_id, tenant_id, run_id)
        existing = await _tool_by_key(session, tenant_id, str(params["idempotency_key"]))
        if existing is not None and existing != call_id:
            adopted[call_id] = existing[0]
            if existing[1] not in _TERMINAL_CALLS:
                params["id"] = existing[0]
                await session.execute(text(_TOOL_UPDATE), params)
            continue
        await _insert_tool_call(session, params, adopted)
    return adopted


def _tool_params(
    row: dict[str, Any], call_id: uuid.UUID, tenant_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    decision = as_text(row.get("policy_decision"), "allow")
    if decision not in _DECISIONS:
        decision = "allow"
    status = as_text(row.get("status"), "pending")
    if status not in _TOOL_STATUSES:
        status = "failed"
    error = row.get("error") if isinstance(row.get("error"), dict) else None
    return {
        "id": call_id,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "tool_id": as_uuid(row.get("tool_id")),
        "tool_version_id": as_uuid(row.get("tool_version_id")),
        "qualified_name": as_text(row.get("qualified_name"), "tool"),
        "model_call_id": as_text(row.get("model_call_id"), str(call_id)),
        "arguments_redacted": as_json(row.get("arguments_redacted"), {}),
        "args_hash": as_text(row.get("args_hash"), "0"),
        "risk_class": as_text(row.get("risk_class"), "R0"),
        "policy_decision": decision,
        "status": status,
        "idempotency_key": as_text(row.get("idempotency_key"), f"{run_id}:{call_id}"),
        "result_preview": row.get("result_preview")
        if isinstance(row.get("result_preview"), str)
        else None,
        "is_error": as_bool(row.get("is_error")),
        "error": as_json(error, {}) if error is not None else None,
        "latency_ms": row.get("latency_ms") if isinstance(row.get("latency_ms"), int) else None,
        "created_at": as_dt(row.get("created_at")) or utcnow(),
    }


async def _tool_by_key(
    session: AsyncSession, tenant_id: uuid.UUID, key: str
) -> tuple[uuid.UUID, str] | None:
    found = await session.execute(
        text(
            "SELECT id, status FROM tool_calls "
            "WHERE tenant_id = :tenant_id AND idempotency_key = :key"
        ),
        {"tenant_id": tenant_id, "key": key},
    )
    row = _first_mapping(found)
    if row is None or row.get("id") is None:
        return None
    call_id = as_uuid(row.get("id"))
    if call_id is None:
        return None
    return call_id, as_text(row.get("status"), "")


async def _insert_tool_call(
    session: AsyncSession, params: dict[str, Any], adopted: dict[uuid.UUID, uuid.UUID]
) -> None:
    nested = getattr(session, "begin_nested", None)

    async def _write() -> None:
        await session.execute(text(_TOOL_UPSERT), params)

    if not callable(nested):
        await _write()
        return
    try:
        async with nested():
            await _write()
    except IntegrityError:
        existing = await _tool_by_key(session, params["tenant_id"], str(params["idempotency_key"]))
        if existing is None:
            raise
        adopted[params["id"]] = existing[0]


def _first_mapping(result: object) -> dict[str, Any] | None:
    """The first row from a SQLAlchemy result or a test double that returns a list."""
    mappings = getattr(result, "mappings", None)
    if not callable(mappings):
        return None
    rows = mappings()
    if isinstance(rows, list):
        return dict(rows[0]) if rows else None
    first = rows.first() if hasattr(rows, "first") else None
    if first is None:
        return None
    return dict(first)


async def save_approval_links(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        call_id = as_uuid(row.get("id"))
        approval_id = as_uuid(row.get("approval_id"))
        if call_id is None or approval_id is None:
            continue
        present = await session.execute(
            text("SELECT 1 FROM approvals WHERE id = :id"),
            {"id": approval_id},
        )
        if present.first() is None:
            continue
        await session.execute(
            text("UPDATE tool_calls SET approval_id = :approval_id WHERE id = :id"),
            {"id": call_id, "approval_id": approval_id},
        )


async def save_approvals(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO approvals (
            id, tenant_id, tool_call_id, run_id, requested_for_user_id, agent_id, qualified_name,
            risk_class, status, args_hash, arguments, preview, justification, approver_rule,
            required_approvals, step_up_required, expires_at, decided_at, consumed_at,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :tool_call_id, :run_id, :requested_for_user_id, :agent_id,
            :qualified_name, :risk_class, :status, :args_hash, CAST(:arguments AS jsonb),
            CAST(:preview AS jsonb), :justification, CAST(:approver_rule AS jsonb),
            :required_approvals, :step_up_required, :expires_at, :decided_at, :consumed_at,
            :created_at, :updated_at
        )
        ON CONFLICT (tool_call_id) DO UPDATE SET
            status = EXCLUDED.status,
            decided_at = EXCLUDED.decided_at,
            consumed_at = EXCLUDED.consumed_at,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        approval_id = as_uuid(row.get("id"))
        if None in {
            approval_id,
            as_uuid(row.get("tenant_id")),
            as_uuid(row.get("tool_call_id")),
            as_uuid(row.get("run_id")),
            as_uuid(row.get("requested_for_user_id")),
            as_uuid(row.get("agent_id")),
        }:
            continue
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": approval_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "tool_call_id": as_uuid(row.get("tool_call_id")),
                "run_id": as_uuid(row.get("run_id")),
                "requested_for_user_id": as_uuid(row.get("requested_for_user_id")),
                "agent_id": as_uuid(row.get("agent_id")),
                "qualified_name": as_text(row.get("qualified_name"), "tool"),
                "risk_class": as_text(row.get("risk_class"), "W2"),
                "status": as_text(row.get("status"), "pending"),
                "args_hash": as_text(row.get("args_hash"), "0"),
                "arguments": as_json(row.get("arguments"), {}),
                "preview": as_json(row.get("preview"), {}),
                "justification": as_text(row.get("justification")),
                "approver_rule": as_json(row.get("approver_rule"), {"mode": "requester"}),
                "required_approvals": max(1, min(5, as_int(row.get("required_approvals"), 1))),
                "step_up_required": as_bool(row.get("step_up_required")),
                "expires_at": as_dt(row.get("expires_at")) or now,
                "decided_at": as_dt(row.get("decided_at")),
                "consumed_at": as_dt(row.get("consumed_at")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_approval_decisions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO approval_decisions (
            id, tenant_id, approval_id, approver_user_id, decision, args_hash, comment,
            step_up_verified, channel, created_at
        ) VALUES (
            :id, :tenant_id, :approval_id, :approver_user_id, :decision, :args_hash, :comment,
            :step_up_verified, :channel, :created_at
        )
        ON CONFLICT (approval_id, approver_user_id) DO NOTHING
    """
    for row in rows:
        if None in {
            as_uuid(row.get("id")),
            as_uuid(row.get("tenant_id")),
            as_uuid(row.get("approval_id")),
            as_uuid(row.get("approver_user_id")),
        }:
            continue
        decision = as_text(row.get("decision"), "approve")
        if decision not in {"approve", "reject"}:
            continue
        channel = as_text(row.get("channel"), "web")
        if channel not in {"web", "slack", "teams", "email", "api"}:
            channel = "web"
        await session.execute(
            text(sql),
            {
                "id": as_uuid(row.get("id")),
                "tenant_id": as_uuid(row.get("tenant_id")),
                "approval_id": as_uuid(row.get("approval_id")),
                "approver_user_id": as_uuid(row.get("approver_user_id")),
                "decision": decision,
                "args_hash": as_text(row.get("args_hash"), "0"),
                "comment": as_text(row.get("comment")),
                "step_up_verified": as_bool(row.get("step_up_verified")),
                "channel": channel,
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )


async def save_policies(
    session: AsyncSession, policies: list[dict[str, Any]], versions: list[dict[str, Any]]
) -> None:
    policy_sql = """
        INSERT INTO policies (
            id, tenant_id, name, description, kind, status, priority, active_version_id,
            created_by, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :name, :description, :kind, :status, :priority, NULL,
            :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            status = EXCLUDED.status,
            priority = EXCLUDED.priority,
            updated_at = EXCLUDED.updated_at
    """
    for row in policies:
        if as_uuid(row.get("id")) is None or as_uuid(row.get("tenant_id")) is None:
            continue
        now = utcnow()
        await session.execute(
            text(policy_sql),
            {
                "id": as_uuid(row.get("id")),
                "tenant_id": as_uuid(row.get("tenant_id")),
                "name": as_text(row.get("name"), "policy"),
                "description": as_text(row.get("description")),
                "kind": "rego" if row.get("kind") == "rego" else "rules",
                "status": as_text(row.get("status"), "draft"),
                "priority": as_int(row.get("priority"), 100),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )
    version_sql = """
        INSERT INTO policy_versions (
            id, tenant_id, policy_id, version, document, rego, hash, created_by, created_at
        ) VALUES (
            :id, :tenant_id, :policy_id, :version, CAST(:document AS jsonb), :rego, :hash,
            :created_by, :created_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for row in versions:
        if None in {
            as_uuid(row.get("id")),
            as_uuid(row.get("tenant_id")),
            as_uuid(row.get("policy_id")),
        }:
            continue
        document = row.get("document") if isinstance(row.get("document"), dict) else None
        rego = row.get("rego") if isinstance(row.get("rego"), str) and row.get("rego") else None
        if document is None and rego is None:
            document = {}
        if document is not None and rego is not None:
            rego = None
        await session.execute(
            text(version_sql),
            {
                "id": as_uuid(row.get("id")),
                "tenant_id": as_uuid(row.get("tenant_id")),
                "policy_id": as_uuid(row.get("policy_id")),
                "version": as_int(row.get("version"), 1),
                "document": as_json(document, {}) if document is not None else None,
                "rego": rego,
                "hash": as_text(row.get("hash"), "0"),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or utcnow(),
            },
        )
    for row in policies:
        policy_id = as_uuid(row.get("id"))
        version_id = as_uuid(row.get("active_version_id"))
        if policy_id is None or version_id is None:
            continue
        await session.execute(
            text("UPDATE policies SET active_version_id = :version_id WHERE id = :id"),
            {"id": policy_id, "version_id": version_id},
        )


async def save_sandbox_templates(
    session: AsyncSession, store: object, sandboxes: list[dict[str, Any]]
) -> None:
    needed = {as_uuid(row.get("template_id")) for row in sandboxes}
    templates = getattr(store, "sandbox_templates", {})
    if not isinstance(templates, dict):
        return
    sql = """
        INSERT INTO sandbox_templates (
            id, tenant_id, slug, name, image_ref, runtime_class, allow_browser, allow_packages,
            egress_allowlist, max_classification, status, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :slug, :name, :image_ref, :runtime_class, :allow_browser,
            :allow_packages, :egress_allowlist, :max_classification, :status, :created_at,
            :updated_at
        )
        ON CONFLICT (id) DO NOTHING
    """
    for key, row in templates.items():
        template_id = as_uuid(row.get("id") if isinstance(row, dict) else key)
        if template_id not in needed or not isinstance(row, dict):
            continue
        now = utcnow()
        runtime = as_text(row.get("runtime_class"), "gvisor")
        if runtime not in {"gvisor", "kata", "runc_dev"}:
            runtime = "gvisor"
        await session.execute(
            text(sql),
            {
                "id": template_id,
                "tenant_id": as_uuid(row.get("tenant_id")),
                "slug": as_text(row.get("slug"), "default"),
                "name": as_text(row.get("name"), "Default"),
                "image_ref": as_text(row.get("image_ref"), ""),
                "runtime_class": runtime,
                "allow_browser": as_bool(row.get("allow_browser")),
                "allow_packages": as_bool(row.get("allow_packages")),
                "egress_allowlist": [str(item) for item in row.get("egress_allowlist") or []]
                if isinstance(row.get("egress_allowlist"), list)
                else [],
                "max_classification": as_text(row.get("max_classification"), "confidential"),
                "status": "active",
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_sandboxes(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO sandboxes (
            id, tenant_id, template_id, scope, scope_key, conversation_id, agent_id, user_id,
            status, driver, driver_ref, endpoint_url, auth_token_hash, workspace_volume,
            cpu_seconds, last_active_at, started_at, terminated_at, error, created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :template_id, :scope, :scope_key, :conversation_id, :agent_id,
            :user_id,
            :status, :driver, :driver_ref, :endpoint_url, :auth_token_hash, :workspace_volume,
            :cpu_seconds, :last_active_at, :started_at, :terminated_at, :error, :created_at,
            :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            driver = EXCLUDED.driver,
            driver_ref = COALESCE(EXCLUDED.driver_ref, sandboxes.driver_ref),
            endpoint_url = CASE
                WHEN EXCLUDED.status IN ('terminated', 'failed') THEN NULL
                ELSE COALESCE(EXCLUDED.endpoint_url, sandboxes.endpoint_url)
            END,
            auth_token_hash = COALESCE(EXCLUDED.auth_token_hash, sandboxes.auth_token_hash),
            workspace_volume = EXCLUDED.workspace_volume,
            cpu_seconds = GREATEST(EXCLUDED.cpu_seconds, sandboxes.cpu_seconds),
            last_active_at = EXCLUDED.last_active_at,
            terminated_at = EXCLUDED.terminated_at,
            error = EXCLUDED.error,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        if None in {
            as_uuid(row.get("id")),
            as_uuid(row.get("tenant_id")),
            as_uuid(row.get("template_id")),
        }:
            continue
        scope = as_text(row.get("scope"), "conversation")
        if scope not in {"conversation", "agent_user", "agent"}:
            scope = "conversation"
        driver = as_text(row.get("driver"), "docker")
        if driver not in {"docker", "kubernetes"}:
            driver = "docker"
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": as_uuid(row.get("id")),
                "tenant_id": as_uuid(row.get("tenant_id")),
                "template_id": as_uuid(row.get("template_id")),
                "scope": scope,
                "scope_key": as_text(row.get("scope_key"), f"conv:{row.get('id')}"),
                "conversation_id": as_uuid(row.get("conversation_id")),
                "agent_id": as_uuid(row.get("agent_id")),
                "user_id": as_uuid(row.get("user_id")),
                "status": as_text(row.get("status"), "ready"),
                "driver": driver,
                "driver_ref": row.get("driver_ref")
                if isinstance(row.get("driver_ref"), str)
                else None,
                "endpoint_url": row.get("endpoint_url")
                if isinstance(row.get("endpoint_url"), str)
                else None,
                "auth_token_hash": row.get("auth_token_hash")
                if isinstance(row.get("auth_token_hash"), str)
                else None,
                "workspace_volume": row.get("workspace_volume")
                if isinstance(row.get("workspace_volume"), str)
                else None,
                "cpu_seconds": as_int(row.get("cpu_seconds")),
                "last_active_at": as_dt(row.get("last_active_at")) or now,
                "started_at": as_dt(row.get("started_at")),
                "terminated_at": as_dt(row.get("terminated_at")),
                "error": row.get("error") if isinstance(row.get("error"), str) else None,
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def save_human_questions(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO human_questions (
            id, tenant_id, run_id, requested_by_user_id, assignee_user_id, kind, question,
            options, answer, status, call_id, created_at, answered_at, updated_at
        ) VALUES (
            :id, :tenant_id, :run_id, :requested_by_user_id, :assignee_user_id, :kind, :question,
            CAST(:options AS jsonb), :answer, :status, :call_id, :created_at, :answered_at,
            :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            answer = EXCLUDED.answer,
            status = EXCLUDED.status,
            answered_at = EXCLUDED.answered_at,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        if None in {
            as_uuid(row.get("id")),
            as_uuid(row.get("tenant_id")),
            as_uuid(row.get("run_id")),
            as_uuid(row.get("requested_by_user_id")),
            as_uuid(row.get("assignee_user_id")),
        }:
            continue
        kind = "approval" if row.get("kind") == "approval" else "question"
        status = as_text(row.get("status"), "pending")
        if status not in {"pending", "answered", "cancelled"}:
            status = "pending"
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": as_uuid(row.get("id")),
                "tenant_id": as_uuid(row.get("tenant_id")),
                "run_id": as_uuid(row.get("run_id")),
                "requested_by_user_id": as_uuid(row.get("requested_by_user_id")),
                "assignee_user_id": as_uuid(row.get("assignee_user_id")),
                "kind": kind,
                "question": as_text(row.get("question"), "Question"),
                "options": as_json(row.get("options"), []),
                "answer": row.get("answer") if isinstance(row.get("answer"), str) else None,
                "status": status,
                "call_id": as_text(row.get("call_id")),
                "created_at": as_dt(row.get("created_at")) or now,
                "answered_at": as_dt(row.get("answered_at")),
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _load(
    session: AsyncSession, store: object, bucket: str, sql: str, tenant_id: uuid.UUID
) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    result = await session.execute(text(sql), {"tenant_id": tenant_id})
    for row in result.mappings():
        body = dict(row)
        _merge(store, bucket, body["id"], body)


async def _load_templates(session: AsyncSession, store: object) -> None:
    from ar_domain.durable.hydrate import _merge  # noqa: PLC0415

    result = await session.execute(text("SELECT * FROM sandbox_templates WHERE tenant_id IS NULL"))
    for row in result.mappings():
        body = dict(row)
        _merge(store, "sandbox_templates", body["id"], body)
