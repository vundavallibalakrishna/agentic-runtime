"""Routine catalogue. Spec: docs/03-specs/15-routines-triggers.md §5."""

import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import jmespath
import orjson
from pydantic import ValidationError

from ar_common.errors import (
    ArError,
    ConflictError,
    ErrorCode,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from ar_common.ids import new_id
from ar_common.settings import BaseServiceSettings
from ar_common.time import utcnow
from ar_contracts.tenants import PlanLimits
from ar_domain.agents.logic import AgentView, can_see_agent
from ar_domain.audit.memory import remember
from ar_domain.routines.engine import (
    accept_routine_event,
    complete_routine_event,
    pause_for_owner,
    prepare_routine_run,
    release_delivery,
)
from ar_domain.routines.metrics import ACTIVE
from ar_domain.routines.schedule import describe_cron, min_gap_seconds, preview_schedule
from ar_domain.routines.signature import idempotency_key, new_secret, new_token, verify

if TYPE_CHECKING:
    from typing import Any

    from ar_domain.agents.access import Actor

_MAX_PER_USER = 50
_DEFAULT_TENANT = 500
_MIN_INTERVAL_S = 300
_INSTRUCTION_LIMIT = 20_000
_TRIGGERS = {
    "schedule",
    "webhook",
    "channel_event",
    "email",
    "file_arrival",
    "db_change",
    "manual",
}
_WEBHOOK_BODY_LIMIT = 1_048_576
_WEBHOOK_RATE = 60


class RoutineBook:
    """Create and run routines for one tenant."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def list_routines(
        self,
        actor: Actor,
        *,
        query: str = "",
        status: str = "",
        owner: str = "",
        agent_id: uuid.UUID | None = None,
        trigger_type: str = "",
    ) -> list[dict[str, object]]:
        rows = [
            self._summary(row)
            for row in self._rows().values()
            if self._visible(row, actor)
            and self._matches(row, query, status, owner, agent_id, trigger_type, actor)
        ]
        rows.sort(key=lambda item: str(item.get("name")))
        return rows

    def create(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        self._require(actor, "routines:create")
        name = str(body.get("name") or "").strip()
        instructions = str(body.get("instructions") or "")
        trigger = _map(body.get("trigger"))
        trigger_type = str(trigger.get("type") or "")
        if not name or trigger_type not in _TRIGGERS:
            raise ValidationFailedError("name and a known trigger are required")
        if len(instructions) > _INSTRUCTION_LIMIT:
            raise ValidationFailedError("instructions are too long")
        self._check_limits(actor, trigger)
        agent = self._agent(actor, body.get("agent_id"))
        run_as = str(body.get("run_as") or "owner")
        if run_as == "service_account" and not actor.has("routines:manage_all"):
            raise ForbiddenError()
        now = utcnow()
        routine_id = new_id()
        secret = new_secret() if trigger_type == "webhook" else ""
        token = new_token() if trigger_type == "webhook" else ""
        delivery = self._delivery(body.get("delivery"))
        row: dict[str, object] = {
            "id": routine_id,
            "tenant_id": actor.tenant_id,
            "name": name,
            "description": str(body.get("description") or ""),
            "owner_user_id": actor.user_id,
            "owner_name": actor.display_name,
            "run_as": run_as,
            "service_account_id": body.get("service_account_id"),
            "agent_id": agent["id"],
            "agent_name": agent.get("name"),
            "agent_version_id": body.get("agent_version_id"),
            "instructions": instructions,
            "trigger_type": trigger_type,
            "trigger_config": self._trigger_config(_map(trigger)),
            "event_filter": body.get("event_filter"),
            "delivery": delivery,
            "budget": body.get("budget") if isinstance(body.get("budget"), dict) else _budget(),
            "max_runs_per_day": _whole(body.get("max_runs_per_day"), 48),
            "concurrency_policy": str(body.get("concurrency_policy") or "skip"),
            "status": "active",
            "paused_reason": None,
            "temporal_schedule_id": f"routine-{routine_id}" if trigger_type == "schedule" else None,
            "webhook_path_token": token or None,
            "webhook_secret": secret,
            "webhook_secret_previous": "",
            "webhook_secret_previous_until": None,
            "consecutive_failures": 0,
            "last_run_at": None,
            "next_run_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self._sync_schedule(row)
        self._grant_standing(actor, row, delivery)
        self._rows()[routine_id] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.created",
            target_type="routine",
            target_id=routine_id,
            detail={"trigger_type": trigger_type},
        )
        ACTIVE.labels(status="active").inc()
        view = self._detail(row)
        if secret:
            view["webhook"] = {
                "webhook_url": f"/api/v1/hooks/routines/{token}",
                "webhook_secret": secret,
            }
        return view

    def detail(self, actor: Actor, routine_id: uuid.UUID) -> dict[str, object]:
        return self._detail(self._owned(actor, routine_id))

    def patch(
        self, actor: Actor, routine_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._owned(actor, routine_id)
        if "name" in body:
            row["name"] = str(body.get("name") or "").strip()
        if "description" in body:
            row["description"] = str(body.get("description") or "")
        if "instructions" in body:
            row["instructions"] = str(body.get("instructions") or "")
        trigger = _map(body.get("trigger"))
        if trigger:
            row["trigger_type"] = str(trigger.get("type") or row.get("trigger_type"))
            row["trigger_config"] = self._trigger_config(trigger)
            self._check_limits(actor, trigger)
            self._sync_schedule(row)
        if "delivery" in body or "agent_id" in body:
            self._revoke_standing(row)
            if "agent_id" in body:
                agent = self._agent(actor, body.get("agent_id"))
                row["agent_id"] = agent["id"]
                row["agent_name"] = agent.get("name")
            delivery = self._delivery(body.get("delivery", row.get("delivery")))
            row["delivery"] = delivery
            self._grant_standing(actor, row, delivery)
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.updated",
            target_type="routine",
            target_id=routine_id,
            detail={},
        )
        return self._detail(row)

    def delete(self, actor: Actor, routine_id: uuid.UUID) -> None:
        row = self._owned(actor, routine_id)
        self._revoke_standing(row)
        schedules = getattr(self.store, "temporal_schedules", None)
        if isinstance(schedules, dict):
            schedules.pop(str(row.get("temporal_schedule_id") or ""), None)
        self._rows().pop(routine_id, None)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.deleted",
            target_type="routine",
            target_id=routine_id,
            detail={},
        )

    def run_now(
        self, actor: Actor, routine_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._owned(actor, routine_id)
        dry = body.get("test") is True
        extra = str(body.get("input") or "")
        key = str(body.get("idempotency_key") or new_id())
        accepted = accept_routine_event(
            self.store,
            routine_id=routine_id,
            source="manual",
            idempotency_key=key,
            envelope={"type": "manual", "data": {"input": extra}, "dry_run": dry},
        )
        if accepted.get("status") != "accepted":
            raise ConflictError(str(accepted.get("status") or "not accepted"))
        event_id = uuid.UUID(str(accepted["event_id"]))
        prepared = prepare_routine_run(self.store, routine_id, event_id)
        if prepared.get("status") != "ready":
            raise ConflictError(str(prepared.get("reason") or prepared.get("status")))
        run_id = uuid.UUID(str(prepared["run_id"]))
        run = self.store.runs[run_id]
        run["dry_run"] = dry
        run["status"] = "completed"
        run["result_summary"] = extra or str(row.get("instructions") or "")
        complete_routine_event(self.store, event_id)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.run_requested",
            target_type="routine",
            target_id=routine_id,
            detail={"run_id": str(run_id), "test": dry},
        )
        return {"run_id": str(run_id), "conversation_id": prepared["conversation_id"]}

    def pause(self, actor: Actor, routine_id: uuid.UUID) -> dict[str, object]:
        row = self._owned(actor, routine_id)
        row["status"] = "paused"
        row["paused_reason"] = "manual"
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.paused",
            target_type="routine",
            target_id=routine_id,
            detail={},
        )
        return self._detail(row)

    def resume(self, actor: Actor, routine_id: uuid.UUID) -> dict[str, object]:
        row = self._owned(actor, routine_id)
        owner = row.get("owner_user_id")
        statuses = getattr(self.store, "user_statuses", {})
        if isinstance(statuses, dict) and statuses.get(owner, "active") != "active":
            raise ArError(ErrorCode.INVALID_STATE, "owner_reauth_required")
        required_raw = getattr(self.store, "reauth_users", None)
        required: set[object] = required_raw if isinstance(required_raw, set) else set()
        granted: set[object] = (
            self.store.delegation_tokens
            if isinstance(getattr(self.store, "delegation_tokens", None), set)
            else set()
        )
        if isinstance(required, set) and owner in required and owner not in granted:
            raise ArError(ErrorCode.INVALID_STATE, "owner_reauth_required")
        row["status"] = "active"
        row["paused_reason"] = None
        row["consecutive_failures"] = 0
        self._sync_schedule(row)
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.resumed",
            target_type="routine",
            target_id=routine_id,
            detail={},
        )
        return self._detail(row)

    def transfer(
        self, actor: Actor, routine_id: uuid.UUID, new_owner: uuid.UUID
    ) -> dict[str, object]:
        if not actor.has("routines:manage_all"):
            raise ForbiddenError()
        row = self._owned(actor, routine_id, manage=True)
        self._revoke_standing(row)
        row["owner_user_id"] = new_owner
        row["status"] = "needs_review"
        row["paused_reason"] = "transferred"
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.transferred",
            target_type="routine",
            target_id=routine_id,
            detail={"new_owner_user_id": str(new_owner)},
        )
        return self._detail(row)

    def rotate(self, actor: Actor, routine_id: uuid.UUID) -> dict[str, object]:
        row = self._owned(actor, routine_id)
        if row.get("trigger_type") != "webhook":
            raise ValidationFailedError("only a webhook routine has a secret")
        secret = new_secret()
        row["webhook_secret_previous"] = row.get("webhook_secret")
        row["webhook_secret_previous_until"] = utcnow() + timedelta(hours=24)
        row["webhook_secret"] = secret
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="routine.webhook_secret_rotated",
            target_type="routine",
            target_id=routine_id,
            detail={},
        )
        view = self._detail(row)
        view["webhook_secret"] = secret
        return view

    def events(self, actor: Actor, routine_id: uuid.UUID) -> list[dict[str, object]]:
        self._owned(actor, routine_id)
        rows = [
            self._event_view(event)
            for event in self._events().values()
            if event.get("routine_id") == routine_id
        ]
        rows.sort(key=lambda item: str(item.get("received_at")), reverse=True)
        return rows

    def preview(self, body: dict[str, object]) -> dict[str, object]:
        return preview_schedule(str(body.get("cron") or ""), str(body.get("timezone") or "UTC"))

    def accept_webhook(
        self, token: str, body: bytes, header: str, *, idempotency_header: str = ""
    ) -> dict[str, object]:
        if len(body) > _WEBHOOK_BODY_LIMIT:
            raise ArError(ErrorCode.PAYLOAD_TOO_LARGE, "webhook body is too large")
        row = self._by_token(token)
        if row is None:
            raise NotFoundError("unknown token")
        now = int(utcnow().timestamp())
        secrets = [str(row.get("webhook_secret") or "")]
        until = row.get("webhook_secret_previous_until")
        if isinstance(until, datetime) and until > utcnow():
            secrets.append(str(row.get("webhook_secret_previous") or ""))
        if not any(verify(secret, body, header, now=now) for secret in secrets if secret):
            raise ArError(ErrorCode.UNAUTHENTICATED, "bad signature")
        if self._webhook_rate(row):
            raise ArError(ErrorCode.RATE_LIMITED, "rate limited")
        path_value = _path_value(row, body)
        key = idempotency_key(body, path_value=path_value, header=idempotency_header)
        accepted = accept_routine_event(
            self.store,
            routine_id=row["id"],  # type: ignore[arg-type]
            source="webhook",
            idempotency_key=key,
            envelope={"type": "webhook", "data": _json_or_text(body)},
        )
        status = str(accepted.get("status") or "")
        if status == "duplicate":
            raise ConflictError(str(accepted.get("event_id") or ""))
        if status == "rate_limited":
            raise ArError(ErrorCode.RATE_LIMITED, "rate limited")
        if status == "accepted":
            event_id = uuid.UUID(str(accepted["event_id"]))
            prepared = prepare_routine_run(self.store, row["id"], event_id)  # type: ignore[arg-type]
            if prepared.get("status") == "ready":
                run = self.store.runs[uuid.UUID(str(prepared["run_id"]))]
                run["status"] = "completed"
                run["result_summary"] = "Webhook accepted."
                complete_routine_event(self.store, event_id)
        return {"event_id": accepted.get("event_id"), "status": status}

    def accept_channel(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        kind = str(body.get("event") or "channel_event")
        source = "email" if kind == "email" else "slack"
        integration = str(body.get("integration_id") or "")
        external = str(body.get("external_event_id") or body.get("message_id") or "")
        matched = 0
        for row in self._rows().values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if row.get("trigger_type") not in {"channel_event", "email"}:
                continue
            if kind == "email" and row.get("trigger_type") != "email":
                continue
            if kind != "email" and row.get("trigger_type") != "channel_event":
                continue
            accepted = accept_routine_event(
                self.store,
                routine_id=row["id"],  # type: ignore[arg-type]
                source=source,
                idempotency_key=f"{integration}:{external}",
                envelope={"type": kind, "data": body},
            )
            if accepted.get("status") == "accepted":
                matched += 1
        return {"matched": matched}

    def release(self, actor: Actor, approval_id: uuid.UUID) -> dict[str, object]:
        row = self.store.approvals.get(approval_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("approval not found")
        return release_delivery(self.store, approval_id)

    def _check_limits(self, actor: Actor, trigger: dict[str, object]) -> None:
        owned = sum(
            1
            for row in self._rows().values()
            if row.get("tenant_id") == actor.tenant_id and row.get("owner_user_id") == actor.user_id
        )
        tenant_rows = sum(
            1 for row in self._rows().values() if row.get("tenant_id") == actor.tenant_id
        )
        if owned >= _MAX_PER_USER or tenant_rows >= _tenant_cap(self.store, actor.tenant_id):
            raise ArError(ErrorCode.PLAN_LIMIT_REACHED, "routine limit reached")
        if str(trigger.get("type") or "") != "schedule":
            return
        gap = min_gap_seconds(str(trigger.get("cron") or ""), str(trigger.get("timezone") or "UTC"))
        minimum = _min_interval()
        if gap is None:
            raise ValidationFailedError("cron or timezone is invalid")
        if gap < minimum and not actor.has("routines:manage_all"):
            raise ValidationFailedError("the schedule is more frequent than the minimum interval")

    def _grant_standing(
        self, actor: Actor, row: dict[str, object], delivery: list[dict[str, object]]
    ) -> None:
        for target in delivery:
            if target.get("pre_approved") is not True:
                continue
            if not actor.has("approvals:grant_standing") and actor.user_id != row.get(
                "owner_user_id"
            ):
                raise ForbiddenError()
            tool = f"delivery.{target.get('type')}_post"
            if target.get("type") == "email":
                tool = "delivery.email_send"
            standing_id = new_id()
            self.store.standing_approvals[standing_id] = {
                "id": standing_id,
                "tenant_id": actor.tenant_id,
                "granted_by_user_id": actor.user_id,
                "routine_id": row.get("id"),
                "tool_name": tool,
                "expires_at": utcnow() + timedelta(days=90),
                "revoked_at": None,
                "uses": 0,
            }

    def _revoke_standing(self, row: dict[str, object]) -> None:
        for standing in self.store.standing_approvals.values():
            if standing.get("routine_id") == row.get("id") and standing.get("revoked_at") is None:
                standing["revoked_at"] = utcnow()

    def _sync_schedule(self, row: dict[str, object]) -> None:
        schedules = getattr(self.store, "temporal_schedules", None)
        if not isinstance(schedules, dict):
            schedules = {}
            self.store.temporal_schedules = schedules
        if row.get("trigger_type") == "schedule" and row.get("status") == "active":
            schedule_id = str(row.get("temporal_schedule_id") or f"routine-{row.get('id')}")
            row["temporal_schedule_id"] = schedule_id
            config = _map(row.get("trigger_config"))
            schedules[schedule_id] = {
                "cron": config.get("cron"),
                "timezone": config.get("timezone"),
                "overlap": row.get("concurrency_policy"),
            }
        elif (
            row.get("trigger_type") in {"file_arrival", "db_change"}
            and row.get("status") == "active"
        ):
            schedules[f"routine-poll-{row.get('id')}"] = {"interval_s": 60}

    def _summary(self, row: dict[str, object]) -> dict[str, object]:
        config = _map(row.get("trigger_config"))
        summary = (
            describe_cron(str(config.get("cron") or ""), str(config.get("timezone") or "UTC"))
            if row.get("trigger_type") == "schedule"
            else str(row.get("trigger_type") or "")
        )
        last = row.get("last_run_at")
        return {
            "id": str(row.get("id")),
            "name": row.get("name"),
            "description": row.get("description"),
            "owner": {"id": str(row.get("owner_user_id")), "name": row.get("owner_name") or ""},
            "agent": {"id": str(row.get("agent_id")), "name": row.get("agent_name") or ""},
            "trigger_type": row.get("trigger_type"),
            "trigger_summary": summary,
            "status": row.get("status"),
            "paused_reason": row.get("paused_reason"),
            "last_run": None
            if last is None
            else {"id": None, "status": "completed", "at": _iso(last)},
            "next_run_at": _iso(row.get("next_run_at")),
            "consecutive_failures": row.get("consecutive_failures"),
        }

    def _detail(self, row: dict[str, object]) -> dict[str, object]:
        view = self._summary(row)
        config = _map(row.get("trigger_config"))
        fires = (
            preview_schedule(
                str(config.get("cron") or ""), str(config.get("timezone") or "UTC")
            ).get("next")
            if row.get("trigger_type") == "schedule"
            else []
        )
        view.update(
            {
                "instructions": row.get("instructions"),
                "trigger": {
                    "type": row.get("trigger_type"),
                    **{
                        str(key): value
                        for key, value in config.items()
                        if not str(key).startswith("_")
                    },
                },
                "event_filter": row.get("event_filter"),
                "delivery": row.get("delivery"),
                "budget": row.get("budget"),
                "concurrency_policy": row.get("concurrency_policy"),
                "max_runs_per_day": row.get("max_runs_per_day"),
                "webhook_url": (
                    f"/api/v1/hooks/routines/{row.get('webhook_path_token')}"
                    if row.get("webhook_path_token")
                    else None
                ),
                "next_fires": fires,
                "standing_approvals": [
                    str(item.get("id"))
                    for item in self.store.standing_approvals.values()
                    if item.get("routine_id") == row.get("id") and item.get("revoked_at") is None
                ],
            }
        )
        return view

    def _event_view(self, event: dict[str, object]) -> dict[str, object]:
        envelope = _map(event.get("envelope"))
        return {
            "id": str(event.get("id")),
            "source": event.get("source"),
            "status": event.get("status"),
            "received_at": _iso(event.get("received_at")),
            "run_id": None if event.get("run_id") is None else str(event.get("run_id")),
            "envelope_preview": str(envelope.get("type") or "")[:80],
        }

    def _owned(
        self, actor: Actor, routine_id: uuid.UUID, *, manage: bool = False
    ) -> dict[str, object]:
        row = self._rows().get(routine_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("routine not found")
        if manage or actor.has("routines:manage_all") or row.get("owner_user_id") == actor.user_id:
            return row
        raise NotFoundError("routine not found")

    def _visible(self, row: dict[str, object], actor: Actor) -> bool:
        if row.get("tenant_id") != actor.tenant_id:
            return False
        return actor.has("routines:manage_all") or row.get("owner_user_id") == actor.user_id

    def _matches(  # noqa: PLR0917
        self,
        row: dict[str, object],
        query: str,
        status: str,
        owner: str,
        agent_id: uuid.UUID | None,
        trigger_type: str,
        actor: Actor,
    ) -> bool:
        if query and query.lower() not in str(row.get("name") or "").lower():
            return False
        if status and row.get("status") != status:
            return False
        if owner == "me" and row.get("owner_user_id") != actor.user_id:
            return False
        if agent_id is not None and row.get("agent_id") != agent_id:
            return False
        return not trigger_type or row.get("trigger_type") == trigger_type

    def _agent(self, actor: Actor, raw: object) -> dict[str, object]:
        try:
            agent_id = uuid.UUID(str(raw))
        except ValueError as exc:
            raise ValidationFailedError("agent_id is required") from exc
        agent = self.store.agents.get(agent_id)
        if not isinstance(agent, dict) or agent.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("agent not found")
        view = AgentView(
            tenant_id=str(agent["tenant_id"]),
            owner_user_id=None
            if agent.get("owner_user_id") is None
            else str(agent["owner_user_id"]),
            owner_team_id=None
            if agent.get("owner_team_id") is None
            else str(agent["owner_team_id"]),
            visibility=str(agent.get("visibility") or "tenant"),
            status=str(agent.get("status") or "active"),
            disabled=bool(agent.get("disabled")),
        )
        if not can_see_agent(
            view,
            tenant_id=str(actor.tenant_id),
            user_id=str(actor.user_id),
            team_ids=set(actor.team_ids),
            manage_all=actor.has("agents:manage_all"),
        ):
            raise NotFoundError("agent not found")
        return agent

    def _delivery(self, raw: object) -> list[dict[str, object]]:
        if raw is None:
            return [{"type": "conversation"}]
        if not isinstance(raw, list):
            raise ValidationFailedError("delivery must be a list")
        return [item for item in raw if isinstance(item, dict)]

    def _trigger_config(self, trigger: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in trigger.items()
            if key != "type" and isinstance(value, (str, int, float, bool, dict, list))
        }

    def _by_token(self, token: str) -> dict[str, object] | None:
        for row in self._rows().values():
            if row.get("webhook_path_token") == token:
                return row
        return None

    def _webhook_rate(self, row: dict[str, object]) -> bool:
        buckets = getattr(self.store, "rate_buckets", None)
        if not isinstance(buckets, dict):
            buckets = {}
            self.store.rate_buckets = buckets
        key = f"routine-webhook:{row.get('id')}"
        now = utcnow().timestamp()
        hits = [
            item for item in buckets.get(key, []) if isinstance(item, float) and now - item < 60
        ]
        if len(hits) >= _WEBHOOK_RATE:
            buckets[key] = hits
            return True
        hits.append(now)
        buckets[key] = hits
        return False

    def _rows(self) -> dict[uuid.UUID, dict[str, object]]:
        rows = self.store.routines
        return rows if isinstance(rows, dict) else {}

    def _events(self) -> dict[uuid.UUID, dict[str, object]]:
        current = getattr(self.store, "routine_events", None)
        if not isinstance(current, dict):
            current = {}
            self.store.routine_events = current
        return current

    def _require(self, actor: Actor, permission: str) -> None:
        if not actor.has(permission) and not actor.has("routines:manage_all"):
            raise ForbiddenError()


def _map(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _whole(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _budget() -> dict[str, int]:
    return {
        "max_steps": 8,
        "max_tokens": 8000,
        "max_cost_micros": 0,
        "max_wall_clock_s": 300,
        "max_tool_calls": 4,
        "max_parallel_tool_calls": 1,
    }


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _min_interval() -> int:
    return int(BaseServiceSettings().routine_min_interval_s)


def _tenant_cap(store: Any, tenant_id: uuid.UUID) -> int:
    settings = getattr(store, "tenant_settings", None)
    raw = settings.get(tenant_id) if isinstance(settings, dict) else None
    if isinstance(raw, dict) and isinstance(raw.get("plan_limits"), dict):
        try:
            return int(PlanLimits.model_validate(raw["plan_limits"]).max_routines)
        except ValidationError:
            return _DEFAULT_TENANT
    return _DEFAULT_TENANT


def _path_value(row: dict[str, object], body: bytes) -> str:
    config = _map(row.get("trigger_config"))
    path = str(config.get("idempotency_key_path") or "")
    if not path:
        return ""
    try:
        found = jmespath.search(path, orjson.loads(body))
    except orjson.JSONDecodeError:
        return ""
    except ValueError:
        return ""
    except jmespath.exceptions.JMESPathError:
        return ""
    return "" if found is None else str(found)


def _json_or_text(body: bytes) -> object:
    try:
        return orjson.loads(body)
    except orjson.JSONDecodeError:
        return body.decode("utf-8", errors="replace")[:2000]


__all__ = ["RoutineBook", "pause_for_owner"]
