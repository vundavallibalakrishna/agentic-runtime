"""Continuous control monitoring. A failing fixture opens a finding."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

import orjson

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.records.memory import blobs
from ar_domain.routines.book import RoutineBook
from ar_pack_grc.connectors.registry import SERVERS, evidence_rows, invoke
from ar_pack_grc.evidence_links import create_link
from ar_pack_grc.findings import create_finding
from ar_pack_grc.tests import create_test, record_result

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

AWS_TOOL = "list_config_rules"
AWS_SLUG = "grc_aws"


def run_test(
    store: Any,
    actor: Actor,
    test_id: uuid.UUID,
    *,
    run_id: uuid.UUID | None = None,
    slug: str = AWS_SLUG,
    tool_name: str = AWS_TOOL,
    link: bool = True,
) -> dict[str, Any]:
    """Collect one connector tool, record the outcome, and open a finding on fail."""
    from ar_pack_grc.access import one  # noqa: PLC0415

    test = one(store, "grc_control_tests", actor, test_id)
    spec = next(item for item in SERVERS if item.slug == slug)
    captured = invoke(
        store,
        spec,
        tool_name,
        {"_tenant_id": str(actor.tenant_id), "_user_id": str(actor.user_id)},
    )
    structured = captured.get("structured")
    raw_items = structured.get("items") if isinstance(structured, dict) else None
    items = raw_items if isinstance(raw_items, list) else []
    evidence_ids = [
        str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")
    ]
    if link:
        for evidence_id in evidence_ids:
            create_link(
                store,
                actor,
                {
                    "control_id": str(test["control_id"]),
                    "evidence_item_id": evidence_id,
                    "freshness_days": int(test.get("freshness_days") or 90),
                },
            )
    outcome = judge(store, evidence_ids)
    current = run_id or new_id()
    result = record_result(
        store,
        actor,
        {
            "test_id": str(test_id),
            "outcome": outcome,
            "summary": str(test.get("procedure") or ""),
            "evidence_item_ids": evidence_ids,
            "run_id": str(current),
        },
    )
    finding = None
    if outcome == "fail":
        finding = create_finding(
            store,
            actor,
            {
                "title": f"{test.get('key')} failed",
                "severity": "high",
                "control_id": str(test["control_id"]),
                "evidence_item_id": evidence_ids[0] if evidence_ids else None,
            },
        )
    ensure_routine(store, actor)
    return {
        "run_id": str(current),
        "outcome": outcome,
        "result": result,
        "finding": finding,
        "evidence_item_ids": evidence_ids,
    }


def judge(store: Any, evidence_ids: list[str]) -> str:
    """Fail when a kept page reports a control as not compliant. No pages is an error."""
    if not evidence_ids:
        return "error"
    failed = False
    for raw in evidence_ids:
        try:
            item_id = uuid.UUID(raw)
        except ValueError:
            continue
        data = blobs(store, "evidence").get(item_id)
        if not isinstance(data, bytes):
            continue
        try:
            payload = orjson.loads(data)
        except orjson.JSONDecodeError:
            continue
        if _noncompliant(payload):
            failed = True
    return "fail" if failed else "pass"


def ensure_routine(store: Any, actor: Actor) -> dict[str, Any]:
    """Install grc-ccm. Delivery is empty because the activity writes the result."""
    for row in store.routines.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("name") == "grc-ccm":
            return cast("dict[str, Any]", row)
    agent = _agent(store, actor)
    created = RoutineBook(store).create(
        actor,
        {
            "name": "grc-ccm",
            "description": "Runs control tests and records the outcome.",
            "instructions": "Record the result. Open a finding when the test fails.",
            "agent_id": str(agent["id"]),
            "trigger": {"type": "schedule", "cron": "0 6 * * *", "timezone": "UTC"},
            "delivery": [],
        },
    )
    saved = store.routines[uuid.UUID(str(created["id"]))]
    return cast("dict[str, Any]", saved)


def seed_monitoring(store: Any, actor: Actor) -> dict[str, Any] | None:
    """One failing AWS fixture for the dev tenant. Evidence is captured and left unlinked."""
    from ar_pack_grc.access import owned  # noqa: PLC0415

    controls = owned(store, "grc_controls", actor)
    if not controls:
        return None
    existing = [
        row for row in owned(store, "grc_control_tests", actor) if row.get("key") == "aws-config"
    ]
    if existing:
        return {"test_id": str(existing[0]["id"])}
    created = create_test(
        store,
        actor,
        {
            "control_id": str(controls[0]["id"]),
            "key": "aws-config",
            "procedure": "Fail when an AWS Config rule is not compliant.",
            "schedule": "0 6 * * *",
            "freshness_days": 30,
        },
    )
    return run_test(store, actor, uuid.UUID(str(created["id"])), link=False)


def _agent(store: Any, actor: Actor) -> dict[str, Any]:
    for row in store.agents.values():
        if row.get("tenant_id") == actor.tenant_id and row.get("slug") == "control-tester":
            return cast("dict[str, Any]", row)
    agent_id = new_id()
    now = utcnow()
    agent = {
        "id": agent_id,
        "tenant_id": actor.tenant_id,
        "slug": "control-tester",
        "name": "Control tester",
        "description": "Runs one control test and records the outcome.",
        "owner_user_id": actor.user_id,
        "owner_team_id": None,
        "visibility": "tenant",
        "status": "published",
        "disabled": False,
        "risk_tier": "medium",
        "draft_version_id": None,
        "published_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    store.agents[agent_id] = agent
    return cast("dict[str, Any]", agent)


def _noncompliant(value: object) -> bool:
    if isinstance(value, dict):
        if value.get("compliant") is False:
            return True
        status = str(value.get("status") or "").lower()
        if status in {"fail", "failed", "non_compliant"}:
            return True
        return any(_noncompliant(item) for item in value.values())
    if isinstance(value, list):
        return any(_noncompliant(item) for item in value)
    return False


def collected_sources(store: Any, actor: Actor) -> list[str]:
    names = {
        str(row.get("source_system") or "")
        for row in evidence_rows(store, actor)
        if row.get("source_system")
    }
    return sorted(names)
