"""Accept, run and deliver one routine event. Activities call these functions."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import jmespath

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_untrusted
from ar_domain.routines.metrics import DELIVERY, EVENTS, RUNS
from ar_domain.routines.schedule import next_fire
from ar_domain.runs.logic import configured_run_budget
from ar_domain.tools.logic import redact

if TYPE_CHECKING:
    from typing import Any

_ACTIVE = {"queued", "running"}
_RISK = "W2"
_FAILURES_BEFORE_PAUSE = 5
_POLL_LIMIT = 20


def _as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return {}


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return cast("list[object]", value)
    return []


_TOOL_FOR = {
    "slack": "delivery.slack_post",
    "teams": "delivery.teams_post",
    "email": "delivery.email_send",
    "webhook": "delivery.webhook_post",
}


def accept_routine_event(  # noqa: PLR0911
    store: Any,
    *,
    routine_id: uuid.UUID,
    source: str,
    idempotency_key: str,
    envelope: dict[str, object],
) -> dict[str, object]:
    """Insert one event. A repeated key returns the original event."""
    routine = _routine(store, routine_id)
    if routine is None:
        return {"status": "missing"}
    previous = _by_key(store, routine_id, idempotency_key)
    if previous is not None:
        EVENTS.labels(source=source, status="duplicate").inc()
        return {"status": "duplicate", "event_id": str(previous["id"])}
    event = _new_event(store, routine, source, idempotency_key, envelope)
    if not _filter_allows(routine, envelope):
        return _finish(event, "filtered", source)
    if routine.get("status") != "active":
        return _finish(event, "failed", source)
    if _over_cap(store, routine):
        return _finish(event, "rate_limited", source)
    if _blocked_by_concurrency(store, routine):
        finished = _finish(event, "skipped_concurrency", source)
        event["detail"] = {"message": "Skipped because the previous run is still going."}
        return finished
    _count_run(store, routine)
    return _finish(event, "accepted", source)


def prepare_routine_run(
    store: Any, routine_id: uuid.UUID, event_id: uuid.UUID
) -> dict[str, object]:
    """Open the owner's conversation and the run, or pause when the owner cannot run."""
    routine = _routine(store, routine_id)
    event = _event(store, event_id)
    if routine is None or event is None:
        return {"status": "missing"}
    prior = store.runs.get(event.get("run_id"))
    if isinstance(prior, dict):
        message = store.messages.get(prior.get("input_message_id"), {})
        return _ready(store, prior, str(message.get("text") or ""))
    owner = routine.get("owner_user_id")
    statuses = getattr(store, "user_statuses", {})
    status = statuses.get(owner, "active") if isinstance(statuses, dict) else "active"
    if status != "active":
        routine["status"] = "needs_review"
        routine["paused_reason"] = "owner_inactive"
        _notify(store, routine, "routine_needs_review")
        event["status"] = "failed"
        return {"status": "needs_review"}
    if _needs_reauth(store, owner):
        routine["status"] = "paused"
        routine["paused_reason"] = "owner_reauth_required"
        event["status"] = "failed"
        _notify(store, routine, "routine_paused")
        _domain(store, "routine.paused", routine, None)
        return {"status": "paused", "reason": "owner_reauth_required"}
    _conversation, message, run = _open_run(store, routine, event)
    event["run_id"] = run["id"]
    return _ready(store, run, str(message.get("text") or ""))


def turn_payload(store: Any, run: dict[str, object]) -> dict[str, object]:
    """What the worker is given to carry out a routine's run: the same as for a chat turn.

    It holds the step allowance of the run's budget. Without it the turn would get the
    workflow's small default and stop a routine whose agent uses more than a few tools.
    """
    from ar_domain.runs.dispatch import workflow_payload  # noqa: PLC0415

    message = store.messages.get(run.get("input_message_id"), {})
    text = str(message.get("text") or "") if isinstance(message, dict) else ""
    return workflow_payload(store, run, uuid.UUID(str(run["id"])), text)


def _ready(store: Any, run: dict[str, object], text: str) -> dict[str, object]:
    """The run a routine opened, and what the worker needs to carry it out."""
    return {
        "status": "ready",
        "run_id": str(run["id"]),
        "conversation_id": str(run["conversation_id"]),
        "text": text,
        "workflow": turn_payload(store, run),
    }


def complete_routine_event(
    store: Any, event_id: uuid.UUID, *, run_status: str = "completed"
) -> dict[str, object]:
    """Record the run, deliver, and pause after five failures."""
    event = _event(store, event_id)
    if event is None:
        return {"status": "missing"}
    routine = _routine(store, event["routine_id"])  # type: ignore[arg-type]
    if routine is None:
        return {"status": "missing"}
    run_id = event.get("run_id")
    run = store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
    if isinstance(run, dict) and run.get("status") in {None, "queued", "running"}:
        run["status"] = run_status
        run["ended_at"] = utcnow()
    held = run if isinstance(run, dict) else None
    event["status"] = "started"
    # A failed run has no result, so nothing is sent and nobody is asked to approve it.
    sent = [] if run_status == "failed" else deliver(store, routine, event, held)
    event["detail"] = {"deliveries": sent}
    routine["last_run_at"] = utcnow()
    nxt = _following_fire(routine)
    if nxt is not None:
        routine["next_run_at"] = nxt
    return _settle(store, routine, event, held, run_status)


def _settle(
    store: Any,
    routine: dict[str, object],
    event: dict[str, object],
    run: dict[str, object] | None,
    run_status: str,
) -> dict[str, object]:
    """Close the event once no delivery waits for its owner. A failed send is a failure."""
    deliveries = _deliveries(event)
    waiting = [row for row in deliveries if row.get("result") == "waiting"]
    failed = run_status == "failed" or any(row.get("result") == "failed" for row in deliveries)
    if waiting and run_status != "failed":
        RUNS.labels(status="waiting").inc()
        return {"status": "waiting", "event_id": str(event["id"]), "deliveries": deliveries}
    if failed:
        routine["consecutive_failures"] = _as_int(routine.get("consecutive_failures")) + 1
        if run is not None:
            run["error"] = {"code": "delivery_failed" if run_status != "failed" else "run_failed"}
            run["status"] = "completed" if run_status != "failed" else "failed"
    else:
        routine["consecutive_failures"] = 0
    terminal = "failed" if failed else "completed"
    RUNS.labels(status=terminal).inc()
    _domain(store, "routine.run_completed", routine, run)
    if _as_int(routine.get("consecutive_failures")) >= _FAILURES_BEFORE_PAUSE:
        routine["status"] = "paused"
        routine["paused_reason"] = "too_many_failures"
        _notify(store, routine, "routine_failed")
        _domain(store, "routine.paused", routine, run)
    elif _conversation_only(routine):
        _notify(store, routine, "routine_completed")
    return {"status": terminal, "event_id": str(event["id"]), "deliveries": deliveries}


def _deliveries(event: dict[str, object]) -> list[dict[str, object]]:
    rows = _as_list(_as_dict(event.get("detail")).get("deliveries"))
    return [row for row in rows if isinstance(row, dict)]


def deliver(
    store: Any,
    routine: dict[str, object],
    event: dict[str, object],
    run: dict[str, object] | None,
) -> list[dict[str, object]]:
    """Send to each target, or ask the owner first when it is not approved in advance."""
    del event
    outcomes: list[dict[str, object]] = []
    quiet = nothing_to_report(store, run)
    for index, target in _targets(routine, run):
        from ar_domain.packs.hooks import review_delivery  # noqa: PLC0415

        if quiet and target.get("when") == REPORT_ONLY and target.get("type") != "conversation":
            # The run said it found nothing to report, and this target wants only reports:
            # it is not sent and nobody is asked to approve it.
            outcomes.append(
                {
                    "target": str(target.get("type") or ""),
                    "result": "skipped",
                    "reason": "The run had nothing to report.",
                }
            )
            continue
        waiting = review_delivery(store, routine, target)
        if waiting is not None:
            outcomes.append(waiting)
            continue
        kind = str(target.get("type") or "")
        tool = _TOOL_FOR.get(kind)
        if tool is None:
            continue
        call: dict[str, object] = {
            "tool": tool,
            "target": kind,
            "index": index,
            "arguments": _arguments(routine, run, target),
        }
        if target.get("pre_approved") is True or _standing(store, routine, tool):
            outcomes.append(_post(store, routine, call))
            continue
        outcomes.append(_hold(store, routine, run, call))
    return outcomes


REPORT_ONLY = "something_to_report"
QUIET_TOOL = "routines.nothing_to_report"


def nothing_to_report(store: Any, run: dict[str, object] | None) -> bool:
    """Whether the run said it found nothing to report.

    The run says so by calling ``routines.nothing_to_report``. The call is a saved row, so
    the worker that delivers reads it wherever the run was carried out; nothing depends on
    how the answer is worded.
    """
    if run is None:
        return False
    calls = getattr(store, "tool_calls", None)
    if not isinstance(calls, dict):
        return False
    return any(
        isinstance(row, dict)
        and str(row.get("run_id")) == str(run.get("id"))
        and row.get("qualified_name") == QUIET_TOOL
        and row.get("status") == "succeeded"
        for row in calls.values()
    )


def is_delivery_tool(name: object) -> bool:
    """True for a tool the runtime calls to deliver a routine's result."""
    return name in _TOOL_FOR.values()


def _hold(
    store: Any, routine: dict[str, object], run: dict[str, object] | None, call: dict[str, object]
) -> dict[str, object]:
    """Ask the routine's owner. The request is a tool call with an approval, like any other."""
    from ar_common.jcs import args_hash  # noqa: PLC0415
    from ar_domain.approvals.logic import render_preview  # noqa: PLC0415
    from ar_domain.approvals.service import ApprovalBook  # noqa: PLC0415
    from ar_domain.policy.metrics import APPROVALS_CREATED  # noqa: PLC0415

    kind = str(call.get("target") or "")
    tool = str(call.get("tool") or "")
    tenant_id = routine.get("tenant_id")
    owner = routine.get("owner_user_id")
    run_id = None if run is None else run.get("id")
    agent_id = routine.get("agent_id") if run is None else run.get("agent_id")
    if not all(isinstance(item, uuid.UUID) for item in (tenant_id, owner, run_id, agent_id)):
        DELIVERY.labels(target=kind or "unknown", result="failed").inc()
        return {
            "target": kind,
            "result": "failed",
            "reason": "There is no run to ask the owner about.",
        }
    arguments = _masked_arguments(store, tenant_id, _as_dict(call.get("arguments")))
    arguments["delivery_index"] = call.get("index")
    digest = args_hash(arguments)  # type: ignore[arg-type]
    call_id = new_id()
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": tenant_id,
        "run_id": run_id,
        "tool_id": None,
        "tool_version_id": None,
        "qualified_name": tool,
        "model_call_id": str(call_id),
        "arguments_redacted": redact(arguments),
        "args_hash": digest,
        "risk_class": _RISK,
        "policy_decision": "require_approval",
        "policy_reasons": ["routine_delivery"],
        "status": "awaiting_approval",
        "idempotency_key": f"{run_id}:{tool}:{call.get('index')}",
        "result_preview": None,
        "is_error": False,
        "error": None,
        "latency_ms": None,
        "created_at": utcnow(),
    }
    approval = ApprovalBook(store).create_pending(
        tenant_id=tenant_id,  # type: ignore[arg-type]
        user_id=owner,  # type: ignore[arg-type]
        run_id=run_id,  # type: ignore[arg-type]
        agent_id=agent_id,  # type: ignore[arg-type]
        tool_call_id=call_id,
        qualified_name=tool,
        risk_class=_RISK,
        args_hash=digest,
        arguments=arguments,
        requirement={"approvers": {"mode": "requester"}},
        reasons=["routine_delivery"],
        preview=render_preview(None, arguments, title=str(routine.get("name") or tool)),
    )
    store.tool_calls[call_id]["approval_id"] = approval["id"]
    APPROVALS_CREATED.labels(risk=_RISK).inc()
    DELIVERY.labels(target=kind or "unknown", result="waiting").inc()
    return {"target": kind, "result": "waiting", "approval_id": str(approval["id"])}


def release_delivery(store: Any, approval_id: uuid.UUID) -> dict[str, object]:
    """Send a delivery its owner approved. A second call sends nothing."""
    row = store.approvals.get(approval_id)
    if not isinstance(row, dict) or not is_delivery_tool(row.get("qualified_name")):
        return {"result": "missing"}
    if row.get("consumed_at") is not None:
        return {"result": "posted", "duplicate": True}
    if row.get("status") != "approved":
        return {"result": "waiting"}
    found = _held_for(store, row)
    if found is None:
        return {"result": "missing"}
    routine, event, run = found
    arguments = _as_dict(row.get("arguments"))
    kind = next((key for key, tool in _TOOL_FOR.items() if tool == row.get("qualified_name")), "")
    outcome = _post(
        store,
        routine,
        {
            "tool": row.get("qualified_name"),
            "target": kind,
            "index": arguments.get("delivery_index"),
            "arguments": arguments,
        },
    )
    row["consumed_at"] = utcnow()
    row["updated_at"] = row["consumed_at"]
    call = store.tool_calls.get(row.get("tool_call_id"))
    if isinstance(call, dict):
        sent = outcome.get("result") == "posted"
        call["status"] = "succeeded" if sent else "failed"
        call["is_error"] = not sent
        call["result_preview"] = "Sent." if sent else str(outcome.get("reason") or "")
    _decided(store, routine, event, run, approval_id, outcome)
    return outcome


def close_delivery(store: Any, approval: dict[str, object]) -> None:
    """Record a delivery its owner refused, withdrew or left to expire. Nothing is sent."""
    found = _held_for(store, approval)
    if found is None:
        return
    routine, event, run = found
    kind = next(
        (key for key, tool in _TOOL_FOR.items() if tool == approval.get("qualified_name")), ""
    )
    status = str(approval.get("status") or "rejected")
    DELIVERY.labels(target=kind or "unknown", result=status).inc()
    call = store.tool_calls.get(approval.get("tool_call_id"))
    if isinstance(call, dict):
        call["status"] = "denied"
    _decided(store, routine, event, run, approval.get("id"), {"target": kind, "result": status})


def _held_for(
    store: Any, approval: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]] | None:
    """The routine, event and run a delivery approval belongs to."""
    run = store.runs.get(approval.get("run_id"))
    if not isinstance(run, dict):
        return None
    routine_id = run.get("routine_id")
    routine = _routine(store, routine_id) if isinstance(routine_id, uuid.UUID) else None
    if routine is None:
        return None
    for event in _events(store).values():
        if event.get("run_id") == run.get("id"):
            return routine, event, run
    return None


def _decided(  # noqa: PLR0917
    store: Any,
    routine: dict[str, object],
    event: dict[str, object],
    run: dict[str, object],
    approval_id: object,
    outcome: dict[str, object],
) -> None:
    """Replace the waiting row with what happened, and close the event when none wait."""
    rows = _deliveries(event)
    for index, item in enumerate(rows):
        if item.get("approval_id") == str(approval_id) and item.get("result") == "waiting":
            rows[index] = {**outcome, "approval_id": str(approval_id)}
            break
    else:
        return
    event["detail"] = {"deliveries": rows}
    if any(item.get("result") == "waiting" for item in rows):
        return
    _settle(store, routine, event, run, "failed" if run.get("status") == "failed" else "completed")


def poll_routine_source(store: Any, routine_id: uuid.UUID) -> list[dict[str, object]]:
    """Start at most 20 events from the watermark. Pending rows are the source stand-in."""
    routine = _routine(store, routine_id)
    if routine is None:
        return []
    config = routine.get("trigger_config")
    if not isinstance(config, dict):
        return []
    state = _as_dict(config.get("_state"))
    pending = _as_list(config.get("_pending"))
    started: list[dict[str, object]] = []
    rest: list[object] = []
    for index, change in enumerate(pending):
        if not isinstance(change, dict):
            continue
        if len(started) >= _POLL_LIMIT:
            rest.append(change)
            rest.extend(pending[index + 1 :])
            break
        key = str(change.get("idempotency_key") or "")
        accepted = accept_routine_event(
            store,
            routine_id=routine_id,
            source="s3" if routine.get("trigger_type") == "file_arrival" else "db",
            idempotency_key=key,
            envelope={"type": "poll", "data": change},
        )
        if accepted.get("status") == "accepted":
            event_id = uuid.UUID(str(accepted["event_id"]))
            prepared = prepare_routine_run(store, routine_id, event_id)
            if prepared.get("status") == "ready":
                started.append(complete_routine_event(store, event_id))
        state = {**state, "watermark": str(change.get("updated_at") or change.get("etag") or key)}
    config["_state"] = state
    config["_pending"] = rest
    routine["trigger_config"] = config
    return started


def on_document_changed(store: Any, document: dict[str, object]) -> None:
    """Fan a knowledge change out to file-arrival routines."""
    collection_id = str(document.get("collection_id") or "")
    key = f"{document.get('id')}@{document.get('version_hash')}"
    for routine in _rows(store).values():
        if routine.get("trigger_type") != "file_arrival" or routine.get("status") != "active":
            continue
        config = _as_dict(routine.get("trigger_config"))
        if str(config.get("collection_id") or "") not in {"", collection_id}:
            continue
        accept_routine_event(
            store,
            routine_id=routine["id"],  # type: ignore[arg-type]
            source="s3",
            idempotency_key=key,
            envelope={
                "type": "knowledge.document_changed",
                "data": {"document_id": str(document.get("id"))},
            },
        )


def reconcile_schedules(store: Any) -> dict[str, int]:
    """Repair schedule ids that drifted from the routine rows."""
    recorded = getattr(store, "temporal_schedules", None)
    if not isinstance(recorded, dict):
        recorded = {}
        store.temporal_schedules = recorded
    desired: set[str] = set()
    for routine in _rows(store).values():
        if routine.get("status") != "active":
            continue
        if routine.get("trigger_type") == "schedule":
            desired.add(str(routine.get("temporal_schedule_id") or ""))
        elif routine.get("trigger_type") in {"file_arrival", "db_change"}:
            desired.add(f"routine-poll-{routine.get('id')}")
    desired.discard("")
    missing = [item for item in desired if item not in recorded]
    extra = [item for item in list(recorded) if item not in desired]
    for item in missing:
        recorded[item] = {"id": item}
    for item in extra:
        recorded.pop(item, None)
    return {"repaired": len(missing) + len(extra)}


def pause_for_owner(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """Pause active routines when their owner is suspended."""
    if not hasattr(store, "routines"):
        return 0
    statuses = getattr(store, "user_statuses", None)
    if isinstance(statuses, dict):
        statuses[user_id] = "suspended"
    paused = 0
    for routine in _rows(store).values():
        if routine.get("tenant_id") != tenant_id or routine.get("owner_user_id") != user_id:
            continue
        if routine.get("status") != "active":
            continue
        routine["status"] = "paused"
        routine["paused_reason"] = "owner_suspended"
        paused += 1
    return paused


def _post(store: Any, routine: dict[str, object], call: dict[str, object]) -> dict[str, object]:
    """Check policy, send once, and record what was sent or why it was not."""
    from ar_domain.channels.posts import policy_decision, record_channel_post  # noqa: PLC0415
    from ar_domain.routines.outbound import send  # noqa: PLC0415

    target = str(call.get("target") or "")
    tool = str(call.get("tool") or "")
    tenant_id = routine.get("tenant_id")
    arguments = _masked_arguments(store, tenant_id, _as_dict(call.get("arguments")))
    if policy_decision(store, tenant_id, tool) == "deny":
        DELIVERY.labels(target=target or "unknown", result="denied").inc()
        return {"target": target, "result": "denied"}
    post_id = new_id()
    sent = send(
        store,
        tenant_id,
        target,
        arguments,
        secret=_target_secret(store, routine, call.get("index")),
        delivery_id=str(post_id),
    )
    result = str(sent.get("result") or "failed")
    reason = str(sent.get("reason") or "")
    record_channel_post(
        store,
        post_id=post_id,
        tenant_id=tenant_id,
        kind=target or "webhook",
        body=str(arguments.get("text") or ""),
        external_message_id=str(sent.get("external_message_id") or ""),
        status=result,
        detail={"tool": tool, "routine_id": str(routine.get("id") or ""), "reason": reason},
    )
    DELIVERY.labels(target=target or "unknown", result=result).inc()
    outcome: dict[str, object] = {"target": target, "result": result, "post_id": str(post_id)}
    if reason:
        outcome["reason"] = reason
    return outcome


def _target_secret(store: Any, routine: dict[str, object], index: object) -> str:
    """The signing secret of one delivery target. It is kept as a secret, by name."""
    from ar_domain.tools.named_secrets import read_named_secret  # noqa: PLC0415

    raw = routine.get("delivery")
    rows = raw if isinstance(raw, list) else []
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(rows):
        return ""
    name = str(_as_dict(_as_dict(rows[index]).get("config")).get("secret_name") or "")
    return read_named_secret(store, routine.get("tenant_id"), name) or ""


def _masked_arguments(
    store: Any, tenant_id: object, arguments: dict[str, object]
) -> dict[str, object]:
    """Mask the text that a delivery sends outside the tenant. The signature covers it."""
    from ar_domain.security.guardrails import mask_leaving  # noqa: PLC0415

    owner = tenant_id if isinstance(tenant_id, uuid.UUID) else None
    masked = dict(arguments)
    text = masked.get("text")
    if isinstance(text, str):
        masked["text"] = mask_leaving(store, owner, text)
    payload = masked.get("payload")
    if isinstance(payload, dict):
        body = dict(payload)
        inner = body.get("text")
        if isinstance(inner, str):
            body["text"] = mask_leaving(store, owner, inner)
        masked["payload"] = body
    return masked


def _arguments(
    routine: dict[str, object], run: dict[str, object] | None, target: dict[str, object]
) -> dict[str, object]:
    """What one target is sent. A secret is never part of it."""
    text = "" if run is None else str(run.get("result_summary") or "")
    config = _as_dict(target.get("config"))
    kind = str(target.get("type") or "")
    if kind == "email":
        return {
            "integration": target.get("integration"),
            "to": str(config.get("to") or target.get("channel") or ""),
            "subject": str(config.get("subject") or routine.get("name") or ""),
            "text": text,
        }
    if kind == "webhook":
        return {
            "url": str(config.get("url") or ""),
            "text": text,
            "payload": {
                "routine_id": str(routine.get("id")),
                "run_id": "" if run is None else str(run.get("id")),
                "conversation_id": "" if run is None else str(run.get("conversation_id") or ""),
                "status": "" if run is None else str(run.get("status") or ""),
                "text": text,
            },
        }
    return {
        "integration": target.get("integration"),
        "channel": target.get("channel"),
        "text": text,
    }


def _targets(
    routine: dict[str, object], run: dict[str, object] | None
) -> list[tuple[int, dict[str, object]]]:
    """Each delivery target with its place in the routine's list. A dry run sends nothing out."""
    raw = routine.get("delivery")
    rows = raw if isinstance(raw, list) else []
    found = [(index, item) for index, item in enumerate(rows) if isinstance(item, dict)]
    if run is not None and run.get("dry_run") is True:
        return [pair for pair in found if pair[1].get("type") == "conversation"]
    return found


def _standing(store: Any, routine: dict[str, object], tool: str) -> bool:
    for row in store.standing_approvals.values():
        if row.get("revoked_at") is not None:
            continue
        if row.get("routine_id") != routine.get("id"):
            continue
        if row.get("tool_name") == tool:
            return True
    return False


def _open_run(
    store: Any, routine: dict[str, object], event: dict[str, object]
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    envelope = event.get("envelope") if isinstance(event.get("envelope"), dict) else {}
    wrapped = wrap_untrusted(source=str(event.get("source") or "routine"), content=str(envelope))
    text = f"{routine.get('instructions')}\n\n{wrapped}"
    tenant_id = uuid.UUID(str(routine["tenant_id"]))
    owner_id = uuid.UUID(str(routine["owner_user_id"]))
    created = store.create_conversation(tenant_id, owner_id, routine["agent_id"])
    conversation_id = uuid.UUID(str(created["id"]))
    conversation = store.conversations[conversation_id]
    conversation["channel"] = "routine"
    conversation["title"] = f"{routine.get('name')} · {utcnow().isoformat()}"
    if routine.get("agent_version_id"):
        conversation["agent_version_id"] = routine["agent_version_id"]
    posted = store.post_message(tenant_id, owner_id, conversation_id, text, schedule=False)
    run = store.runs[uuid.UUID(str(posted["run"]["id"]))]
    run["trigger"] = "routine"
    run["routine_id"] = routine["id"]
    # The run carries the routine's budget, which `read_budget` applies as a ceiling.
    run["budget"] = routine.get("budget") or configured_run_budget()
    run["dry_run"] = bool(event.get("dry_run"))
    return conversation, store.messages[run["input_message_id"]], run


def _filter_allows(routine: dict[str, object], envelope: dict[str, object]) -> bool:
    expression = routine.get("event_filter")
    if not isinstance(expression, str) or not expression.strip():
        return True
    try:
        found = jmespath.search(expression, envelope)
    except jmespath.exceptions.JMESPathError:
        return False
    if found:  # noqa: SIM103 - jmespath returns Any, and bool() is not a bool to mypy
        return True
    return False


def _over_cap(store: Any, routine: dict[str, object]) -> bool:
    cap = _as_int(routine.get("max_runs_per_day"), 48)
    key = f"{routine.get('id')}:{datetime.now(UTC).strftime('%Y%m%d')}"
    counts = getattr(store, "routine_daily", None)
    if not isinstance(counts, dict):
        counts = {}
        store.routine_daily = counts
    today = utcnow().date()
    persisted = sum(
        1
        for event in _events(store).values()
        if event.get("routine_id") == routine["id"]
        and event.get("status") in {"accepted", "started"}
        and isinstance(received := event.get("received_at"), datetime)
        and received.date() == today
    )
    # The newly accepted event is already in the cache but has not consumed a slot.
    return max(int(counts.get(key) or 0), 0, persisted - 1) >= cap


def _count_run(store: Any, routine: dict[str, object]) -> None:
    key = f"{routine.get('id')}:{datetime.now(UTC).strftime('%Y%m%d')}"
    counts = store.routine_daily
    counts[key] = int(counts.get(key) or 0) + 1


def _blocked_by_concurrency(store: Any, routine: dict[str, object]) -> bool:
    policy = str(routine.get("concurrency_policy") or "skip")
    if policy == "allow":
        return False
    active = _active_runs(store, routine.get("id"))
    if policy == "skip":
        return active > 0
    waiting = sum(
        1
        for event in _events(store).values()
        if event.get("routine_id") == routine.get("id") and event.get("status") == "accepted"
    )
    return active > 0 and waiting > 0


def _active_runs(store: Any, routine_id: object) -> int:
    return sum(
        1
        for run in store.runs.values()
        if isinstance(run, dict)
        and run.get("routine_id") == routine_id
        and run.get("status") in _ACTIVE
    )


def _needs_reauth(store: Any, owner: object) -> bool:
    required = getattr(store, "reauth_users", None)
    granted = getattr(store, "delegation_tokens", None)
    if not isinstance(required, set) or owner not in required:
        return False
    return not isinstance(granted, set) or owner not in granted


def _following_fire(routine: dict[str, object]) -> datetime | None:
    if routine.get("trigger_type") != "schedule":
        return None
    config = routine.get("trigger_config")
    if not isinstance(config, dict):
        return None
    return next_fire(str(config.get("cron") or ""), str(config.get("timezone") or "UTC"))


def _conversation_only(routine: dict[str, object]) -> bool:
    raw = routine.get("delivery")
    rows = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    return all(item.get("type") in {None, "conversation", "file"} for item in rows)


def _new_event(
    store: Any,
    routine: dict[str, object],
    source: str,
    idempotency_key: str,
    envelope: dict[str, object],
) -> dict[str, object]:
    event_id = new_id()
    event = {
        "id": event_id,
        "tenant_id": routine.get("tenant_id"),
        "routine_id": routine.get("id"),
        "idempotency_key": idempotency_key,
        "source": source,
        "envelope": envelope,
        "status": "accepted",
        "run_id": None,
        "received_at": utcnow(),
        "dry_run": bool(envelope.get("dry_run")),
        "detail": {},
    }
    _events(store)[event_id] = event
    return _events(store)[event_id]


def _finish(event: dict[str, object], status: str, source: str) -> dict[str, object]:
    event["status"] = status
    EVENTS.labels(source=source, status=status).inc()
    return {"status": status, "event_id": str(event["id"])}


def _notify(store: Any, routine: dict[str, object], kind: str) -> None:
    notes = getattr(store, "notifications", None)
    if isinstance(notes, list):
        notes.append(
            {
                "kind": kind,
                "routine_id": str(routine.get("id")),
                "owner_user_id": str(routine.get("owner_user_id")),
            }
        )


def _domain(
    store: Any, name: str, routine: dict[str, object], run: dict[str, object] | None
) -> None:
    events = getattr(store, "domain_events", None)
    if isinstance(events, list):
        events.append(
            {
                "type": name,
                "routine_id": str(routine.get("id")),
                "run_id": "" if run is None else str(run.get("id")),
                "status": "" if run is None else str(run.get("status") or ""),
            }
        )


def _routine(store: Any, routine_id: uuid.UUID) -> dict[str, object] | None:
    row = _rows(store).get(routine_id)
    return row if isinstance(row, dict) else None


def _event(store: Any, event_id: uuid.UUID) -> dict[str, object] | None:
    row = _events(store).get(event_id)
    return row if isinstance(row, dict) else None


def _by_key(store: Any, routine_id: uuid.UUID, key: str) -> dict[str, object] | None:
    for event in _events(store).values():
        if event.get("routine_id") == routine_id and event.get("idempotency_key") == key:
            return event
    return None


def _rows(store: Any) -> dict[uuid.UUID, dict[str, object]]:
    current = getattr(store, "routines", None)
    if not isinstance(current, dict):
        current = {}
        store.routines = current
    return current


def _events(store: Any) -> dict[uuid.UUID, dict[str, object]]:
    current = getattr(store, "routine_events", None)
    if not isinstance(current, dict):
        current = {}
        store.routine_events = current
    return current
