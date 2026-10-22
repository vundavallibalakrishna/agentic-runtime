"""Accept, run and deliver one routine event. Activities call these functions."""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import jmespath

from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_common.wrapping import wrap_untrusted
from ar_domain.routines.metrics import DELIVERY, EVENTS, RUNS
from ar_domain.routines.schedule import next_fire

if TYPE_CHECKING:
    from typing import Any

_ACTIVE = {"queued", "running"}
_FAILURES_BEFORE_PAUSE = 5
_POLL_LIMIT = 20
_DEFAULT_BUDGET = {
    "max_steps": 8,
    "max_tokens": 8000,
    "max_cost_micros": 0,
    "max_wall_clock_s": 300,
    "max_tool_calls": 4,
    "max_parallel_tool_calls": 1,
}
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
        return _finish(event, "skipped_concurrency", source)
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
    conversation, message, run = _open_run(store, routine, event)
    event["run_id"] = run["id"]
    return {
        "status": "ready",
        "run_id": str(run["id"]),
        "conversation_id": str(conversation["id"]),
        "text": str(message.get("text") or ""),
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
    deliveries = deliver(store, routine, event, run if isinstance(run, dict) else None)
    waiting = [row for row in deliveries if row.get("result") == "waiting"]
    failed = run_status == "failed" or any(row.get("result") == "failed" for row in deliveries)
    event["status"] = "started"
    event["detail"] = {"deliveries": deliveries}
    routine["last_run_at"] = utcnow()
    nxt = _following_fire(routine)
    if nxt is not None:
        routine["next_run_at"] = nxt
    if waiting and run_status != "failed":
        RUNS.labels(status="waiting").inc()
        return {"status": "waiting", "event_id": str(event["id"]), "deliveries": deliveries}
    if failed:
        routine["consecutive_failures"] = _as_int(routine.get("consecutive_failures")) + 1
        if isinstance(run, dict):
            run["error"] = {"code": "delivery_failed" if run_status != "failed" else "run_failed"}
            run["status"] = "completed" if run_status != "failed" else "failed"
    else:
        routine["consecutive_failures"] = 0
    terminal = "failed" if failed else "completed"
    RUNS.labels(status=terminal).inc()
    _domain(store, "routine.run_completed", routine, run if isinstance(run, dict) else None)
    if _as_int(routine.get("consecutive_failures")) >= _FAILURES_BEFORE_PAUSE:
        routine["status"] = "paused"
        routine["paused_reason"] = "too_many_failures"
        _notify(store, routine, "routine_failed")
        _domain(store, "routine.paused", routine, run if isinstance(run, dict) else None)
    elif _conversation_only(routine):
        _notify(store, routine, "routine_completed")
    return {"status": terminal, "event_id": str(event["id"]), "deliveries": deliveries}


def deliver(
    store: Any,
    routine: dict[str, object],
    event: dict[str, object],
    run: dict[str, object] | None,
) -> list[dict[str, object]]:
    """Post each target, or wait for the owner when it is not pre-approved."""
    outcomes: list[dict[str, object]] = []
    for target in _targets(routine, run):
        kind = str(target.get("type") or "")
        if kind in {"conversation", "file"}:
            continue
        tool = _TOOL_FOR.get(kind)
        if tool is None:
            continue
        call = {"tool": tool, "target": kind, "arguments": _arguments(routine, run, target)}
        if target.get("pre_approved") is True or _standing(store, routine, tool):
            outcomes.append(_post(store, routine, _as_dict(call)))
            continue
        approval_id = new_id()
        store.approvals[approval_id] = {
            "id": approval_id,
            "tenant_id": routine.get("tenant_id"),
            "routine_id": routine.get("id"),
            "event_id": event.get("id"),
            "status": "pending",
            "tool": tool,
            "call": call,
            "delivered": False,
        }
        DELIVERY.labels(target=kind, result="waiting").inc()
        outcomes.append({"target": kind, "result": "waiting", "approval_id": str(approval_id)})
    return outcomes


def release_delivery(store: Any, approval_id: uuid.UUID) -> dict[str, object]:
    """Post a waiting delivery once after the owner approves it."""
    row = store.approvals.get(approval_id)
    if not isinstance(row, dict):
        return {"result": "missing"}
    if row.get("delivered") is True:
        return {"result": "posted", "duplicate": True}
    call = row.get("call")
    routine_id = row.get("routine_id")
    routine = _routine(store, routine_id) if isinstance(routine_id, uuid.UUID) else None
    if not isinstance(call, dict) or routine is None:
        return {"result": "missing"}
    outcome = _post(store, routine, _as_dict(call))
    row["status"] = "approved"
    row["delivered"] = True
    event_id = row.get("event_id")
    event = _event(store, event_id) if isinstance(event_id, uuid.UUID) else None
    if event is not None:
        detail = _as_dict(event.get("detail"))
        rows = _as_list(detail.get("deliveries"))
        rows.append(outcome)
        event["detail"] = {"deliveries": rows}
    return outcome


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
    target = str(call.get("target") or "")
    arguments = _as_dict(call.get("arguments"))
    signed = ""
    if target == "webhook":
        secret = str(arguments.get("secret") or "")
        payload = str(arguments.get("payload") or "")
        signed = hashlib.sha256(f"{secret}.{payload}".encode()).hexdigest()
    posts = getattr(store, "delivery_posts", None)
    if not isinstance(posts, list):
        posts = []
        store.delivery_posts = posts
    posts.append(
        {
            "tool": call.get("tool"),
            "target": target,
            "signed": signed,
            "routine_id": str(routine.get("id") or ""),
        }
    )
    DELIVERY.labels(target=target or "unknown", result="posted").inc()
    return {"target": target, "result": "posted", "signature": signed}


def _arguments(
    routine: dict[str, object], run: dict[str, object] | None, target: dict[str, object]
) -> dict[str, object]:
    text = ""
    if isinstance(run, dict):
        text = str(run.get("result_summary") or "")
    config = _as_dict(target.get("config"))
    return {
        "channel": target.get("channel"),
        "integration": target.get("integration"),
        "text": text,
        "url": config.get("url") or "",
        "secret": config.get("secret") or "",
        "payload": {
            "routine_id": str(routine.get("id")),
            "run_id": "" if run is None else str(run.get("id")),
            "text": text,
        },
    }


def _targets(routine: dict[str, object], run: dict[str, object] | None) -> list[dict[str, object]]:
    raw = routine.get("delivery")
    rows = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    if isinstance(run, dict) and run.get("dry_run") is True:
        return [item for item in rows if item.get("type") == "conversation"]
    return rows


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
    now = utcnow()
    conversation_id = new_id()
    message_id = new_id()
    run_id = new_id()
    envelope = event.get("envelope") if isinstance(event.get("envelope"), dict) else {}
    wrapped = wrap_untrusted(source=str(event.get("source") or "routine"), content=str(envelope))
    text = f"{routine.get('instructions')}\n\n{wrapped}"
    conversation = {
        "id": conversation_id,
        "tenant_id": routine.get("tenant_id"),
        "user_id": routine.get("owner_user_id"),
        "agent_id": routine.get("agent_id"),
        "agent_version_id": routine.get("agent_version_id"),
        "channel": "routine",
        "title": f"{routine.get('name')} · {now.isoformat()}",
        "created_at": now,
    }
    message = {
        "id": message_id,
        "tenant_id": routine.get("tenant_id"),
        "conversation_id": conversation_id,
        "role": "user",
        "text": text,
        "content": [{"type": "text", "text": text}],
        "status": "completed",
        "created_at": now,
    }
    run = {
        "id": run_id,
        "tenant_id": routine.get("tenant_id"),
        "conversation_id": conversation_id,
        "agent_id": routine.get("agent_id"),
        "user_id": routine.get("owner_user_id"),
        "input_message_id": message_id,
        "status": "queued",
        "trigger": "routine",
        "routine_id": routine.get("id"),
        "budget": routine.get("budget") or _DEFAULT_BUDGET,
        "result_summary": "",
        "error": None,
        "dry_run": bool(event.get("dry_run")),
        "created_at": now,
    }
    store.conversations[conversation_id] = conversation
    store.messages[message_id] = message
    store.runs[run_id] = run
    if not isinstance(getattr(store, "events", None), dict):
        store.events = {}
    store.events.setdefault(run_id, [])
    return conversation, message, run


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
    return int(counts.get(key) or 0) >= cap


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
    return event


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
