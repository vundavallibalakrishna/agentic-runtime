"""Persist and load eval suites, cases, runs and results.

The buckets are tracked with the rest of the product. Without these writers a
created suite is audited and then absent from Postgres, so the next request
returns 404.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY

from ar_common.time import utcnow
from ar_domain.durable.codec import as_bool, as_dt, as_int, as_json, as_text, as_uuid

if TYPE_CHECKING:
    import uuid
    from typing import Any

    from sqlalchemy.ext.asyncio import AsyncSession


def _tags(value: object) -> list[str]:
    """Tags as a list. asyncpg binds a list to ``text[]``; a literal string does not."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


async def save_eval_rows(session: AsyncSession, pending: dict[str, list[dict[str, Any]]]) -> None:
    """Write the four eval buckets. Parents before children."""
    await _suites(session, pending.get("eval_suites", []))
    await _cases(session, pending.get("eval_cases", []))
    await _runs(session, pending.get("eval_runs", []))
    await _results(session, pending.get("eval_results", []))


async def load_eval_rows(session: AsyncSession, store: object, tenant_id: uuid.UUID) -> None:
    """Merge one tenant's eval rows into the process cache."""
    from ar_domain.durable.hydrate import _merge, _rows  # noqa: PLC0415

    for bucket, sql in (
        ("eval_suites", "SELECT * FROM eval_suites WHERE tenant_id = :tenant_id"),
        ("eval_cases", "SELECT * FROM eval_cases WHERE tenant_id = :tenant_id"),
        (
            "eval_runs",
            # The agent is the one the run's version belongs to. It is not stored twice.
            "SELECT r.*, v.agent_id FROM eval_runs r "
            "LEFT JOIN agent_versions v ON v.id = r.agent_version_id "
            "WHERE r.tenant_id = :tenant_id",
        ),
        ("eval_results", "SELECT * FROM eval_results WHERE tenant_id = :tenant_id"),
    ):
        for row in await _rows(session, sql, tenant_id):
            _merge(store, bucket, row["id"], row)


async def _suites(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO eval_suites (
            id, tenant_id, agent_id, name, description, kind, gate, created_by,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :agent_id, :name, :description, :kind, CAST(:gate AS jsonb),
            :created_by, :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            agent_id = EXCLUDED.agent_id,
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            kind = EXCLUDED.kind,
            gate = EXCLUDED.gate,
            updated_at = EXCLUDED.updated_at
    """
    for row in rows:
        suite_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        if suite_id is None or tenant_id is None:
            continue
        kind = as_text(row.get("kind"), "functional")
        if kind not in {"functional", "retrieval", "safety", "red_team"}:
            kind = "functional"
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": suite_id,
                "tenant_id": tenant_id,
                "agent_id": as_uuid(row.get("agent_id")),
                "name": as_text(row.get("name"), "suite"),
                "description": as_text(row.get("description"), ""),
                "kind": kind,
                "gate": as_json(row.get("gate"), {}),
                "created_by": as_uuid(row.get("created_by")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _cases(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO eval_cases (
            id, tenant_id, suite_id, name, input, assertions, tool_mocks, tags,
            created_at, updated_at
        ) VALUES (
            :id, :tenant_id, :suite_id, :name, CAST(:input AS jsonb),
            CAST(:assertions AS jsonb), CAST(:tool_mocks AS jsonb), :tags,
            :created_at, :updated_at
        )
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            input = EXCLUDED.input,
            assertions = EXCLUDED.assertions,
            tool_mocks = EXCLUDED.tool_mocks,
            tags = EXCLUDED.tags,
            updated_at = EXCLUDED.updated_at
    """
    statement = text(sql).bindparams(bindparam("tags", type_=ARRAY(String())))
    for row in rows:
        case_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        suite_id = as_uuid(row.get("suite_id"))
        if None in {case_id, tenant_id, suite_id}:
            continue
        now = utcnow()
        await session.execute(
            statement,
            {
                "id": case_id,
                "tenant_id": tenant_id,
                "suite_id": suite_id,
                "name": as_text(row.get("name"), "case"),
                "input": as_json(row.get("input"), {}),
                "assertions": as_json(row.get("assertions"), []),
                "tool_mocks": as_json(row.get("tool_mocks"), []),
                "tags": _tags(row.get("tags")),
                "created_at": as_dt(row.get("created_at")) or now,
                "updated_at": as_dt(row.get("updated_at")) or now,
            },
        )


async def _runs(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO eval_runs (
            id, tenant_id, suite_id, agent_version_id, model_alias_override, status,
            summary, baseline_eval_run_id, temporal_workflow_id, triggered_by, trigger,
            tags, mock_all_tools, started_at, finished_at, created_at
        ) VALUES (
            :id, :tenant_id, :suite_id, :agent_version_id, :model_alias_override, :status,
            CAST(:summary AS jsonb), :baseline_eval_run_id, :temporal_workflow_id,
            :triggered_by, :trigger, :tags, :mock_all_tools, :started_at, :finished_at,
            :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            status = EXCLUDED.status,
            summary = EXCLUDED.summary,
            model_alias_override = EXCLUDED.model_alias_override,
            started_at = EXCLUDED.started_at,
            finished_at = EXCLUDED.finished_at
    """
    for row in rows:
        run_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        suite_id = as_uuid(row.get("suite_id"))
        if None in {run_id, tenant_id, suite_id}:
            continue
        status = as_text(row.get("status"), "queued")
        if status not in {"queued", "running", "completed", "failed", "cancelled"}:
            status = "queued"
        trigger = as_text(row.get("trigger"), "manual")
        if trigger not in {"manual", "publish_gate", "schedule", "ci"}:
            trigger = "manual"
        now = utcnow()
        tags = row.get("tags")
        await session.execute(
            text(sql),
            {
                "id": run_id,
                "tenant_id": tenant_id,
                "suite_id": suite_id,
                "agent_version_id": as_uuid(row.get("agent_version_id")),
                "model_alias_override": row.get("model_alias_override")
                if isinstance(row.get("model_alias_override"), str)
                else None,
                "status": status,
                "summary": as_json(row.get("summary"), {}),
                "baseline_eval_run_id": as_uuid(row.get("baseline_eval_run_id")),
                "temporal_workflow_id": as_text(row.get("temporal_workflow_id"), f"eval-{run_id}"),
                "triggered_by": as_uuid(row.get("triggered_by")),
                "trigger": trigger,
                "tags": [str(item) for item in tags] if isinstance(tags, list) else [],
                "mock_all_tools": row.get("mock_all_tools") is True,
                "started_at": as_dt(row.get("started_at")),
                "finished_at": as_dt(row.get("finished_at")),
                "created_at": as_dt(row.get("created_at")) or now,
            },
        )


async def _results(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    sql = """
        INSERT INTO eval_results (
            id, tenant_id, eval_run_id, case_id, run_id, passed, scores, output_text,
            latency_ms, cost_micros, created_at
        ) VALUES (
            :id, :tenant_id, :eval_run_id, :case_id, :run_id, :passed, CAST(:scores AS jsonb),
            :output_text, :latency_ms, :cost_micros, :created_at
        )
        ON CONFLICT (id) DO UPDATE SET
            passed = EXCLUDED.passed,
            scores = EXCLUDED.scores,
            output_text = EXCLUDED.output_text,
            latency_ms = EXCLUDED.latency_ms,
            cost_micros = EXCLUDED.cost_micros
    """
    for row in rows:
        result_id = as_uuid(row.get("id"))
        tenant_id = as_uuid(row.get("tenant_id"))
        eval_run_id = as_uuid(row.get("eval_run_id"))
        case_id = as_uuid(row.get("case_id"))
        if None in {result_id, tenant_id, eval_run_id, case_id}:
            continue
        now = utcnow()
        await session.execute(
            text(sql),
            {
                "id": result_id,
                "tenant_id": tenant_id,
                "eval_run_id": eval_run_id,
                "case_id": case_id,
                "run_id": as_uuid(row.get("run_id")),
                "passed": as_bool(row.get("passed")),
                "scores": as_json(row.get("scores"), {}),
                "output_text": as_text(row.get("output_text"), ""),
                "latency_ms": as_int(row.get("latency_ms"))
                if isinstance(row.get("latency_ms"), int)
                else None,
                "cost_micros": as_int(row.get("cost_micros")),
                "created_at": as_dt(row.get("created_at")) or now,
            },
        )
