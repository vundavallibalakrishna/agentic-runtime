"""Feedback digest and alias-change re-runs. Spec: docs/03-specs/18-observability-eval.md §4."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor


def note_feedback(store: Any, payload: dict[str, object]) -> None:
    """Batch thumbs-down notices. One digest per owner per day, not one per event."""
    tenant = str(payload.get("tenant_id") or "")
    agent = str(payload.get("agent_id") or "")
    owner = str(payload.get("owner_user_id") or payload.get("user_id") or "")
    day = utcnow().date().isoformat()
    key = f"{tenant}:{owner}:{day}"
    bucket = store.feedback_digest.get(key)
    if not isinstance(bucket, dict):
        bucket = {"count": 0, "agent_id": agent, "tenant_id": tenant, "owner": owner, "sent": False}
        store.feedback_digest[key] = bucket
    count = bucket.get("count")
    bucket["count"] = (count if isinstance(count, int) else 0) + 1
    if agent:
        bucket["agent_id"] = agent


def digest_notices(store: Any) -> list[dict[str, object]]:
    """Materialise unsent daily digests and mark them sent."""
    notices: list[dict[str, object]] = []
    for key, bucket in list(store.feedback_digest.items()):
        if not isinstance(bucket, dict) or bucket.get("sent"):
            continue
        raw_count = bucket.get("count")
        count = raw_count if isinstance(raw_count, int) else 0
        if count <= 0:
            continue
        agent = str(bucket.get("agent_id") or "")
        notice = {
            "kind": "eval_completed",
            "title": "Feedback to review",
            "body": f"{count} new ratings are waiting in the evaluation inbox.",
            "link": f"/admin/evals?agent={agent}" if agent else "/admin/evals",
            "user_id": bucket.get("owner") or "",
            "tenant_id": bucket.get("tenant_id") or "",
            "digest_key": key,
        }
        bucket["sent"] = True
        notices.append(notice)
        store.notifications.append(notice)
    return notices


def agents_using_alias(store: Any, tenant_id: uuid.UUID, alias: str) -> list[dict[str, object]]:
    """Published agents whose model alias is exactly ``alias``."""
    found: list[dict[str, object]] = []
    for agent in store.agents.values():
        if not isinstance(agent, dict) or agent.get("tenant_id") != tenant_id:
            continue
        if agent.get("status") != "published":
            continue
        version_id = agent.get("published_version_id")
        version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
        definition = version.get("definition") if isinstance(version, dict) else None
        model = definition.get("model") if isinstance(definition, dict) else None
        if isinstance(model, dict) and str(model.get("alias") or "") == alias:
            found.append(agent)
    return found


def rerun_gated_suites(store: Any, actor: Actor, alias: str) -> list[str]:
    """Start gated suites for published agents that use this alias. Others are left alone."""
    from ar_domain.evals.book import EvalBook  # noqa: PLC0415

    book = EvalBook(store)
    started: list[str] = []
    for agent in agents_using_alias(store, actor.tenant_id, alias):
        agent_id = agent.get("id")
        if not isinstance(agent_id, uuid.UUID):
            continue
        for suite in book.list_suites(actor, agent_id=agent_id):
            gate = suite.get("gate")
            if not isinstance(gate, dict) or not gate.get("required"):
                continue
            suite_id = suite.get("id")
            if not isinstance(suite_id, uuid.UUID):
                continue
            run = book.start_run(
                actor,
                suite_id,
                {
                    "agent_version_ref": "published",
                    "trigger": "schedule",
                    "agent_id": agent_id,
                },
            )
            started.append(str(run["id"]))
    store.domain_events.append(
        {
            "topic": "model_alias.updated",
            "payload": {"alias": alias, "tenant_id": str(actor.tenant_id), "eval_runs": started},
            "at": utcnow().isoformat(),
        }
    )
    return started
