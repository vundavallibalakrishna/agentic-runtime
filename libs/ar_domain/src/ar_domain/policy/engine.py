"""Live policy decisions for every tool call. Spec: docs/03-specs/09-policy-approvals.md §3."""

import os
import time
import uuid
from typing import TYPE_CHECKING

import httpx

from ar_common.time import utcnow
from ar_domain.approvals.logic import _standing_ok
from ar_domain.audit.memory import remember
from ar_domain.policy.logic import enrich_time, evaluate, fallback
from ar_domain.policy.metrics import DECISIONS, EVAL_SECONDS, FALLBACK
from ar_domain.policy.service import _overrides, _settings, active_rules

if TYPE_CHECKING:
    from typing import Any


def evaluate_call(
    store: Any,
    request: dict[str, object],
    version: dict[str, object],
    tool: dict[str, object],
    server: dict[str, object],
) -> dict[str, object]:
    """Return a policy decision. An empty OPA URL uses the in-process evaluator."""
    started = time.perf_counter()
    tenant_id = request.get("tenant_id")
    rules: list[dict[str, object]] = []
    settings: dict[str, object] = {
        "security": {"require_step_up_for_w3": True},
        "approvals": {"default_ttl_s": 86400},
    }
    if isinstance(tenant_id, uuid.UUID):
        rules = active_rules(store, tenant_id)
        settings = _settings(store, tenant_id)
    policy_input = _input(store, request, version, server, settings)
    url = _url(store)
    used_fallback = False
    if url:
        remote = _ask_opa(url, policy_input, _timeout(store))
        if remote is None:
            used_fallback = True
            FALLBACK.inc()
            result = fallback(policy_input, rules)
        else:
            result = remote
    else:
        result = evaluate(policy_input, rules, settings)
    risk = str(version.get("risk_class") or "R0")
    if _eval_blocked(store, request, risk) and result.get("decision") != "deny":
        result = {
            "decision": "deny",
            "reasons": ["eval runs do not execute writes"],
            "matched_rule_ids": [],
            "approval": None,
        }
    if result.get("decision") == "require_approval" and risk != "W3":
        standing = _take_standing(store, request, tool)
        if standing == "sod_violation":
            remember(
                store,
                tenant_id=tenant_id,
                actor_id=request.get("user_id"),
                action="sod.violation_blocked",
                target_type="tool_call",
                target_id=request.get("model_call_id"),
                detail={"reason": "sod_violation"},
                outcome="failure",
            )
            result = {
                "decision": "deny",
                "reasons": ["sod_violation"],
                "matched_rule_ids": result.get("matched_rule_ids") or [],
                "approval": None,
            }
        elif isinstance(standing, str):
            remember(
                store,
                tenant_id=tenant_id,
                actor_id=request.get("user_id"),
                action="approval.standing_used",
                target_type="standing_approval",
                target_id=standing,
                detail={},
            )
            result = {
                "decision": "allow",
                "reasons": [f"standing_approval:{standing}"],
                "matched_rule_ids": result.get("matched_rule_ids") or [],
                "approval": None,
                "standing_approval_id": standing,
            }
    DECISIONS.labels(decision=str(result.get("decision")), risk=risk).inc()
    EVAL_SECONDS.observe(time.perf_counter() - started)
    if used_fallback:
        result = {**result, "fallback": True}
    return result


def consume_granted(store: Any, request: dict[str, object]) -> str | None:
    """Mark one approved call as used. A mismatch or a second use is invalid."""
    raw = request.get("approval_id")
    try:
        approval_id = raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw))
    except ValueError:
        return "approval_invalid"
    lock = store.approval_lock
    with lock:
        row = store.approvals.get(approval_id)
        if not isinstance(row, dict):
            return "approval_invalid"
        if row.get("status") != "approved" or row.get("consumed_at") is not None:
            return "approval_invalid"
        if str(row.get("args_hash") or "") != str(request.get("args_hash") or ""):
            return "approval_invalid"
        row["consumed_at"] = utcnow()
        row["updated_at"] = row["consumed_at"]
    return None


def _url(store: Any) -> str:
    if hasattr(store, "opa_url"):
        return str(store.opa_url or "")
    return os.environ.get("AR_OPA_URL", "")


def _timeout(store: Any) -> float:
    raw = getattr(store, "opa_timeout_ms", None)
    if raw is None:
        raw = os.environ.get("AR_OPA_TIMEOUT_MS", "200")
    try:
        return max(0.05, int(raw) / 1000)
    except ValueError:
        return 0.2


def _ask_opa(url: str, policy_input: dict[str, object], timeout: float) -> dict[str, object] | None:
    endpoint = url.rstrip("/") + "/v1/data/ar/policy/decision"
    for _attempt in range(2):
        try:
            response = httpx.post(endpoint, json={"input": policy_input}, timeout=timeout)
        except httpx.HTTPError:
            continue
        if response.status_code >= 300:
            continue
        body = response.json()
        result = body.get("result") if isinstance(body, dict) else None
        if isinstance(result, dict) and result.get("decision") in {
            "allow",
            "deny",
            "require_approval",
        }:
            return result
    return None


def _eval_blocked(store: Any, request: dict[str, object], risk: str) -> bool:
    if risk not in {"W2", "W3"}:
        return False
    run_id = request.get("run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    return isinstance(run, dict) and bool(run.get("eval_context"))


def _take_standing(store: Any, request: dict[str, object], tool: dict[str, object]) -> str | None:
    """Consume one standing approval, or ``sod_violation`` when the only match is forbidden."""
    lock = store.approval_lock
    blocked = False
    with lock:
        for row in list(store.standing_approvals.values()):
            if not _standing_ok(store, row, request, tool):
                continue
            if _self_granted(store, row, request):
                blocked = True
                continue
            limit = row.get("max_uses")
            uses = int(row.get("uses") or 0)
            cap = limit if isinstance(limit, int) else 2_147_483_647
            if uses >= cap:
                continue
            row["uses"] = uses + 1
            return str(row["id"])
    if blocked:
        return "sod_violation"
    return None


def _self_granted(store: Any, row: dict[str, object], request: dict[str, object]) -> bool:
    routine_id = row.get("routine_id")
    routine = store.routines.get(routine_id) if isinstance(routine_id, uuid.UUID) else None
    owner = routine.get("owner_user_id") if isinstance(routine, dict) else None
    return owner is not None and str(owner) == str(row.get("granted_by_user_id")) == str(
        request.get("user_id")
    )


def _input(
    store: Any,
    request: dict[str, object],
    version: dict[str, object],
    server: dict[str, object],
    settings: dict[str, object],
) -> dict[str, object]:
    run_id = request.get("run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    agent_id = request.get("agent_id")
    if not isinstance(agent_id, uuid.UUID) and isinstance(run, dict):
        agent_id = run.get("agent_id")
    agent = store.agents.get(agent_id) if isinstance(agent_id, uuid.UUID) else None
    definition: dict[str, object] = {}
    if isinstance(agent, dict):
        published = store.versions.get(agent.get("published_version_id"))
        raw = published.get("definition") if isinstance(published, dict) else {}
        if isinstance(raw, dict):
            definition = raw
    user_id = request.get("user_id")
    groups = store.user_groups.get(user_id, []) if isinstance(user_id, uuid.UUID) else []
    roles = store.user_roles.get(user_id, set()) if isinstance(user_id, uuid.UUID) else set()
    arguments = request.get("arguments") if isinstance(request.get("arguments"), dict) else {}
    return {
        "tenant_id": str(request.get("tenant_id") or ""),
        "tool": {
            "qualified_name": version.get("qualified_name"),
            "name": version.get("name"),
            "server_slug": server.get("slug"),
            "risk_class": version.get("risk_class"),
            "data_classification": version.get("data_classification") or "internal",
            "annotations": version.get("annotations")
            if isinstance(version.get("annotations"), dict)
            else {},
        },
        "agent": {
            "id": "" if not isinstance(agent, dict) else str(agent.get("id")),
            "slug": "" if not isinstance(agent, dict) else str(agent.get("slug") or ""),
            "risk_tier": "medium",
            "overrides": _overrides(definition),
            "owner_user_id": ""
            if not isinstance(agent, dict)
            else str(agent.get("owner_user_id") or ""),
        },
        "run": {
            "id": "" if not isinstance(run, dict) else str(run.get("id")),
            "trigger": "chat" if not isinstance(run, dict) else str(run.get("trigger") or "chat"),
            "channel": "web",
            "depth": 0,
            "routine_id": None if not isinstance(run, dict) else run.get("routine_id"),
        },
        "user": {
            "id": str(user_id or ""),
            "groups": list(groups),
            "teams": [],
            "roles": list(roles),
            "attributes": {},
        },
        "args": arguments,
        "time": enrich_time(utcnow()),
        "settings": settings,
    }
