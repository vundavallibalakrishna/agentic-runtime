"""Approvals and standing approvals. Spec: docs/03-specs/09-policy-approvals.md §5-7."""

import uuid
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ConflictError, ForbiddenError, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.approvals.errors import StepUpRequiredError
from ar_domain.approvals.logic import can_decide, can_view, is_approver, render_preview
from ar_domain.audit.memory import remember
from ar_domain.policy.service import _settings
from ar_domain.rows import as_datetime, as_dict, as_int, as_list, as_uuid

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_MAX_NOTIFY = 50


class ApprovalBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def list_items(
        self,
        actor: Actor,
        *,
        scope: str,
        status: str | None,
        agent_id: uuid.UUID | None,
        risk_class: str | None,
    ) -> list[dict[str, object]]:
        if scope == "all" and "approvals:read_all" not in actor.permissions:
            raise ForbiddenError()
        rows: list[dict[str, object]] = []
        for row in self.store.approvals.values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if status and row.get("status") != status:
                continue
            if agent_id is not None and row.get("agent_id") != agent_id:
                continue
            if risk_class and row.get("risk_class") != risk_class:
                continue
            if scope == "requested" and row.get("requested_for_user_id") != actor.user_id:
                continue
            if scope == "to_decide" and not can_decide(self.store, actor, row):
                continue
            rows.append(self.summary(row))
        rows.sort(key=lambda item: str(item["created_at"]), reverse=True)
        return rows

    def get(self, actor: Actor, approval_id: uuid.UUID) -> dict[str, object]:
        row = self._require(actor, approval_id)
        eligible = (
            can_decide(self.store, actor, row)
            or is_approver(self.store, actor, row)
            or "approvals:read_all" in actor.permissions
        )
        if not can_view(actor, row, eligible=eligible):
            raise NotFoundError("approval not found")
        return self.detail(actor, row, reveal=eligible or "approvals:read_all" in actor.permissions)

    def decide(
        self,
        actor: Actor,
        approval_id: uuid.UUID,
        body: dict[str, object],
        *,
        stepped_up: bool,
    ) -> dict[str, object]:
        row = self._require(actor, approval_id)
        if not can_decide(self.store, actor, row):
            raise ForbiddenError("you cannot decide this approval")
        from ar_domain.approvals.sod import SodBook  # noqa: PLC0415

        SodBook(self.store).assert_approval(actor, row, decision=str(body.get("decision") or ""))
        self._fresh(row)
        if str(body.get("args_hash") or "") != str(row.get("args_hash")):
            raise ConflictError("args_changed")
        if row.get("step_up_required") and not stepped_up:
            raise StepUpRequiredError()
        if actor.auth_method == "api_key" and row.get("step_up_required"):
            raise StepUpRequiredError()
        choice = str(body.get("decision") or "")
        if choice not in {"approve", "reject"}:
            raise ValidationFailedError("decision must be approve or reject")
        edited = body.get("arguments")
        if isinstance(edited, dict) and choice == "approve":
            return self._edit(actor, row, edited, str(body.get("comment") or ""))
        self._record_decision(actor, row, choice, str(body.get("comment") or ""), stepped_up)
        if choice == "reject":
            self._terminal(row, "rejected", actor, "web")
        else:
            received = self._received(row)
            if received >= as_int(row.get("required_approvals"), 1):
                self._terminal(row, "approved", actor, "web")
        if row["status"] in {"approved", "rejected"}:
            from ar_domain.tools.resume import settle_approval  # noqa: PLC0415

            settle_approval(self.store, row)
        return self.detail(actor, row, reveal=True)

    def cancel(self, actor: Actor, approval_id: uuid.UUID) -> dict[str, object]:
        row = self._require(actor, approval_id)
        if (
            row.get("requested_for_user_id") != actor.user_id
            and "tenant:manage" not in actor.permissions
        ):
            raise ForbiddenError("only the requester can cancel")
        if row.get("status") != "pending":
            raise ConflictError("only a pending approval can be cancelled")
        self._terminal(row, "cancelled", actor, "web")
        from ar_domain.tools.resume import settle_approval  # noqa: PLC0415

        settle_approval(self.store, row)
        return self.detail(actor, row, reveal=True)

    def expire_due(self, now: object | None = None) -> int:
        from ar_common.time import utcnow as clock  # noqa: PLC0415

        moment = now or clock()
        count = 0
        for row in self.store.approvals.values():
            if row.get("status") != "pending":
                continue
            expires = row.get("expires_at")
            if expires is not None and expires <= moment:
                row["status"] = "expired"
                row["decided_at"] = moment
                row["updated_at"] = moment
                remember(
                    self.store,
                    tenant_id=row.get("tenant_id"),
                    actor_id="system",
                    action="approval.expired",
                    target_type="approval",
                    target_id=row["id"],
                    detail={},
                )
                _observe(row, "expired", "timer")
                from ar_domain.tools.resume import settle_approval  # noqa: PLC0415

                settle_approval(self.store, row)
                count += 1
        return count

    def expire_one(self, approval_id: uuid.UUID) -> None:
        """Expire one pending approval. A second call is a no-op."""
        row = self.store.approvals.get(approval_id)
        if not isinstance(row, dict) or row.get("status") != "pending":
            return
        moment = utcnow()
        row["status"] = "expired"
        row["decided_at"] = moment
        row["updated_at"] = moment
        remember(
            self.store,
            tenant_id=row.get("tenant_id"),
            actor_id="system",
            action="approval.expired",
            target_type="approval",
            target_id=row["id"],
            detail={},
        )
        _observe(row, "expired", "timer")
        from ar_domain.tools.resume import settle_approval  # noqa: PLC0415

        settle_approval(self.store, row)

    def cancel_one(self, approval_id: uuid.UUID) -> None:
        """Cancel one pending approval. A second call is a no-op."""
        row = self.store.approvals.get(approval_id)
        if not isinstance(row, dict) or row.get("status") != "pending":
            return
        moment = utcnow()
        row["status"] = "cancelled"
        row["decided_at"] = moment
        row["updated_at"] = moment
        remember(
            self.store,
            tenant_id=row.get("tenant_id"),
            actor_id="system",
            action="approval.cancelled",
            target_type="approval",
            target_id=row["id"],
            detail={},
        )
        _observe(row, "cancelled", "timer")
        from ar_domain.tools.resume import settle_approval  # noqa: PLC0415

        settle_approval(self.store, row)

    def create_pending(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        run_id: uuid.UUID | None,
        agent_id: uuid.UUID | None,
        tool_call_id: uuid.UUID,
        qualified_name: str,
        risk_class: str,
        args_hash: str,
        arguments: dict[str, object],
        requirement: dict[str, object],
        reasons: list[str],
        preview: dict[str, object],
    ) -> dict[str, object]:
        approval_id = new_id()
        now = utcnow()
        ttl = as_int(requirement.get("ttl_s"), 86400)
        approvers = requirement.get("approvers")
        row: dict[str, object] = {
            "id": approval_id,
            "tenant_id": tenant_id,
            "tool_call_id": tool_call_id,
            "run_id": run_id,
            "requested_for_user_id": user_id,
            "agent_id": agent_id,
            "qualified_name": qualified_name,
            "risk_class": risk_class,
            "status": "pending",
            "args_hash": args_hash,
            "arguments": arguments,
            "preview": preview,
            "justification": "",
            "approver_rule": approvers if isinstance(approvers, dict) else {"mode": "requester"},
            "required_approvals": as_int(requirement.get("required_approvals"), 1),
            "four_eyes": bool(requirement.get("four_eyes")),
            "step_up_required": bool(requirement.get("step_up")),
            "policy_reasons": reasons,
            "expires_at": now + timedelta(seconds=ttl),
            "decided_at": None,
            "consumed_at": None,
            "created_at": now,
            "updated_at": now,
        }
        self.store.approvals[approval_id] = row
        self.store.domain_events.append(
            {
                "topic": "approval.requested",
                "payload": {
                    "approval_id": str(approval_id),
                    "run_id": None if run_id is None else str(run_id),
                    "tool_call_id": str(tool_call_id),
                    "qualified_name": qualified_name,
                    "approver_user_ids": self._approver_ids(row)[:_MAX_NOTIFY],
                },
                "at": now.isoformat(),
            }
        )
        remember(
            self.store,
            tenant_id=tenant_id,
            actor_id=user_id,
            action="approval.requested",
            target_type="approval",
            target_id=approval_id,
            detail={"risk_class": risk_class, "args_hash": args_hash},
        )
        self._notify(row)
        return row

    def list_standing(self, actor: Actor) -> list[dict[str, object]]:
        manage = "tenant:manage" in actor.permissions
        if "approvals:grant_standing" not in actor.permissions and not manage:
            raise ForbiddenError()
        rows = []
        for row in self.store.standing_approvals.values():
            if row.get("tenant_id") != actor.tenant_id:
                continue
            if not manage and row.get("granted_by_user_id") != actor.user_id:
                continue
            rows.append(self._standing_view(row))
        return rows

    def grant_standing(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        if "approvals:grant_standing" not in actor.permissions:
            raise ForbiddenError()
        tool_id = _uuid(body.get("tool_id"), "tool")
        tool = self.store.tool_defs.get(tool_id)
        if not isinstance(tool, dict) or tool.get("tenant_id") not in {None, actor.tenant_id}:
            raise NotFoundError("tool not found")
        version = _current_version(self.store, tool)
        if isinstance(version, dict) and version.get("risk_class") == "W3":
            raise ValidationFailedError("standing approvals are not allowed for W3 tools")
        agent_id = _optional_uuid(body.get("agent_id"))
        routine_id = _optional_uuid(body.get("routine_id"))
        if agent_id is None and routine_id is None:
            raise ValidationFailedError("an agent or a routine is required")
        from ar_domain.approvals.sod import SodBook  # noqa: PLC0415

        SodBook(self.store).assert_standing(actor, routine_id)
        expires = as_datetime(body.get("expires_at"))
        if expires is None:
            raise ValidationFailedError("expires_at is required")
        if expires > utcnow() + timedelta(days=90):
            raise ValidationFailedError("a standing approval lasts at most 90 days")
        row = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "granted_by_user_id": actor.user_id,
            "agent_id": agent_id,
            "routine_id": routine_id,
            "tool_id": tool_id,
            "argument_constraints": body.get("argument_constraints")
            if isinstance(body.get("argument_constraints"), list)
            else [],
            "max_uses": body.get("max_uses") if isinstance(body.get("max_uses"), int) else None,
            "uses": 0,
            "expires_at": expires,
            "revoked_at": None,
            "created_at": utcnow(),
        }
        self.store.standing_approvals[row["id"]] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="standing_approval.created",
            target_type="standing_approval",
            target_id=row["id"],
            detail={"tool_id": str(tool_id)},
        )
        return self._standing_view(row)

    def revoke_standing(self, actor: Actor, standing_id: uuid.UUID) -> dict[str, object]:
        row = self.store.standing_approvals.get(standing_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("standing approval not found")
        if (
            row.get("granted_by_user_id") != actor.user_id
            and "tenant:manage" not in actor.permissions
        ):
            raise ForbiddenError()
        row["revoked_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="standing_approval.revoked",
            target_type="standing_approval",
            target_id=standing_id,
            detail={},
        )
        return self._standing_view(row)

    def summary(self, row: dict[str, object]) -> dict[str, object]:
        agent = self.store.agents.get(row.get("agent_id"))
        run = self.store.runs.get(row.get("run_id"))
        preview = as_dict(row.get("preview"))
        return {
            "id": row["id"],
            "status": row["status"],
            "qualified_name": row["qualified_name"],
            "risk_class": row["risk_class"],
            "args_hash": row.get("args_hash"),
            "agent": {
                "id": None if not isinstance(agent, dict) else agent.get("id"),
                "name": "" if not isinstance(agent, dict) else agent.get("name"),
            },
            "requested_for": {
                "id": row.get("requested_for_user_id"),
                "display_name": _name(self.store, row.get("requested_for_user_id")),
            },
            "preview": {"title": preview.get("title"), "summary": preview.get("summary")},
            "approvals_received": self._received(row),
            "required_approvals": row.get("required_approvals"),
            "expires_at": row.get("expires_at"),
            "created_at": row.get("created_at"),
            "conversation_id": None if not isinstance(run, dict) else run.get("conversation_id"),
            "run_id": row.get("run_id"),
        }

    def detail(self, actor: Actor, row: dict[str, object], *, reveal: bool) -> dict[str, object]:
        body = self.summary(row)
        version = _version_for(self.store, str(row.get("qualified_name")))
        body.update(
            {
                "arguments": row.get("arguments") if reveal else None,
                "args_hash": row.get("args_hash"),
                "preview": row.get("preview"),
                "justification": row.get("justification"),
                "policy_reasons": row.get("policy_reasons"),
                "approver_rule": row.get("approver_rule"),
                "four_eyes": row.get("four_eyes"),
                "step_up_required": row.get("step_up_required"),
                "decisions": self._decisions(row),
                "tool": {
                    "description": "" if version is None else version.get("description"),
                    "input_schema": {} if version is None else version.get("input_schema"),
                },
                "can_decide": can_decide(self.store, actor, row),
            }
        )
        return body

    def _edit(
        self, actor: Actor, row: dict[str, object], arguments: dict[str, object], comment: str
    ) -> dict[str, object]:
        from ar_domain.tools.logic import call_args_hash  # noqa: PLC0415

        self._record_decision(actor, row, "reject", comment or "edited", True)
        self._terminal(row, "rejected", actor, "web")
        version = _version_for(self.store, str(row.get("qualified_name")))
        version_id = "" if version is None else str(version.get("id"))
        digest = call_args_hash(version_id, arguments)
        tool = self.store.tool_defs.get(version.get("tool_id")) if isinstance(version, dict) else {}
        preview = render_preview(
            version.get("approval_preview") if isinstance(version, dict) else None,
            arguments,
            title=str(row.get("qualified_name")),
        )
        run_raw = row.get("run_id")
        agent_raw = row.get("agent_id")
        approvals = as_dict(_settings(self.store, as_uuid(row.get("tenant_id"))).get("approvals"))
        created = self.create_pending(
            tenant_id=as_uuid(row.get("tenant_id")),
            user_id=as_uuid(row.get("requested_for_user_id")),
            run_id=run_raw if isinstance(run_raw, uuid.UUID) else None,
            agent_id=agent_raw if isinstance(agent_raw, uuid.UUID) else None,
            tool_call_id=as_uuid(row.get("tool_call_id")),
            qualified_name=str(row.get("qualified_name")),
            risk_class=str(row.get("risk_class")),
            args_hash=digest,
            arguments=arguments,
            requirement={
                "approvers": row.get("approver_rule"),
                "required_approvals": row.get("required_approvals"),
                "four_eyes": row.get("four_eyes"),
                "step_up": row.get("step_up_required"),
                "ttl_s": as_int(approvals.get("default_ttl_s"), 86400),
            },
            reasons=[str(item) for item in as_list(row.get("policy_reasons"))],
            preview=preview,
        )
        del tool
        run_id = row.get("run_id")
        run = self.store.runs.get(run_id) if isinstance(run_id, uuid.UUID) else None
        pending = run.get("pending_approval") if isinstance(run, dict) else None
        if isinstance(pending, dict):
            pending["approval_id"] = created["id"]
            pending["arguments"] = arguments
            pending["args_hash"] = digest
        return self.detail(actor, created, reveal=True)

    def _record_decision(
        self,
        actor: Actor,
        row: dict[str, object],
        choice: str,
        comment: str,
        stepped_up: bool,  # noqa: FBT001
    ) -> None:
        for existing in self.store.approval_decisions.values():
            if (
                existing.get("approval_id") == row["id"]
                and existing.get("approver_user_id") == actor.user_id
            ):
                raise ConflictError("you already decided this approval")
        decision_id = new_id()
        self.store.approval_decisions[decision_id] = {
            "id": decision_id,
            "tenant_id": actor.tenant_id,
            "approval_id": row["id"],
            "approver_user_id": actor.user_id,
            "decision": choice,
            "args_hash": row["args_hash"],
            "comment": comment,
            "step_up_verified": stepped_up,
            "channel": "web",
            "created_at": utcnow(),
        }

    def _terminal(self, row: dict[str, object], status: str, actor: Actor, channel: str) -> None:
        row["status"] = status
        row["decided_at"] = utcnow()
        row["updated_at"] = row["decided_at"]
        action = "approval.cancelled" if status == "cancelled" else "approval.decided"
        remember(
            self.store,
            tenant_id=row.get("tenant_id"),
            actor_id=actor.user_id,
            action=action,
            target_type="approval",
            target_id=row["id"],
            detail={"status": status, "channel": channel, "args_hash": row.get("args_hash")},
        )
        _observe(row, status, channel)
        self.store.domain_events.append(
            {
                "topic": "approval.decided",
                "payload": {
                    "approval_id": str(row["id"]),
                    "run_id": None if row.get("run_id") is None else str(row.get("run_id")),
                    "status": status,
                },
                "at": (as_datetime(row.get("decided_at")) or utcnow()).isoformat(),
            }
        )

    def _received(self, row: dict[str, object]) -> int:
        return sum(
            1
            for item in self.store.approval_decisions.values()
            if item.get("approval_id") == row["id"] and item.get("decision") == "approve"
        )

    def _decisions(self, row: dict[str, object]) -> list[dict[str, object]]:
        found = [
            {
                "approver": {
                    "id": item.get("approver_user_id"),
                    "display_name": _name(self.store, item.get("approver_user_id")),
                },
                "decision": item.get("decision"),
                "comment": item.get("comment"),
                "channel": item.get("channel"),
                "created_at": item.get("created_at"),
            }
            for item in self.store.approval_decisions.values()
            if item.get("approval_id") == row["id"]
        ]
        found.sort(key=lambda item: str(item["created_at"]))
        return found

    def _fresh(self, row: dict[str, object]) -> None:
        if row.get("status") != "pending":
            raise ConflictError("approval is not pending")
        expires = as_datetime(row.get("expires_at"))
        if expires is not None and expires <= utcnow():
            row["status"] = "expired"
            raise ConflictError("approval has expired")

    def _require(self, actor: Actor, approval_id: uuid.UUID) -> dict[str, object]:
        row = self.store.approvals.get(approval_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("approval not found")
        return row

    def _notify(self, row: dict[str, object]) -> None:
        title = f"Approval needed for {row.get('qualified_name')}"
        for user_id in self._approver_ids(row)[:_MAX_NOTIFY]:
            self.store.notifications.append(
                {
                    "id": str(new_id()),
                    "tenant_id": str(row.get("tenant_id")),
                    "user_id": user_id,
                    "kind": "approval_requested",
                    "title": title,
                    "body": str(as_dict(row.get("preview")).get("summary") or ""),
                    "link": f"/approvals/{row['id']}",
                    "read": False,
                }
            )

    def _approver_ids(self, row: dict[str, object]) -> list[str]:
        rule = row.get("approver_rule")
        mode = rule.get("mode") if isinstance(rule, dict) else "requester"
        if mode == "requester":
            return [str(row.get("requested_for_user_id"))]
        if mode == "users" and isinstance(rule, dict):
            return [str(item) for item in rule.get("users") or []]
        if mode == "group" and isinstance(rule, dict):
            names = {str(item) for item in rule.get("groups") or []}
            return [
                str(user_id)
                for user_id, groups in self.store.user_groups.items()
                if names.intersection(groups)
            ]
        if mode == "agent_owner":
            agent = self.store.agents.get(row.get("agent_id"))
            if isinstance(agent, dict) and agent.get("owner_user_id") is not None:
                return [str(agent["owner_user_id"])]
        return []

    def _standing_view(self, row: dict[str, object]) -> dict[str, object]:
        agent = self.store.agents.get(row.get("agent_id"))
        tool = self.store.tool_defs.get(row.get("tool_id"))
        return {
            "id": row["id"],
            "agent": None
            if not isinstance(agent, dict)
            else {"id": agent.get("id"), "name": agent.get("name")},
            "routine": None if row.get("routine_id") is None else {"id": row.get("routine_id")},
            "tool": {
                "id": row.get("tool_id"),
                "name": "" if not isinstance(tool, dict) else tool.get("name"),
            },
            "argument_constraints": row.get("argument_constraints"),
            "max_uses": row.get("max_uses"),
            "uses": row.get("uses"),
            "expires_at": row.get("expires_at"),
            "revoked_at": row.get("revoked_at"),
            "granted_by": row.get("granted_by_user_id"),
        }


def _observe(row: dict[str, object], status: str, channel: str) -> None:
    from ar_domain.policy.metrics import APPROVALS_RESOLVED, DECISION_SECONDS  # noqa: PLC0415

    APPROVALS_RESOLVED.labels(status=status, channel=channel).inc()
    created = row.get("created_at")
    decided = row.get("decided_at")
    started = as_datetime(created)
    finished = as_datetime(decided)
    if started is not None and finished is not None:
        DECISION_SECONDS.observe(max(0.0, finished.timestamp() - started.timestamp()))


def _uuid(value: object, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except ValueError as exc:
        raise ValidationFailedError(f"{label} id is required") from exc


def _optional_uuid(value: object) -> uuid.UUID | None:
    if not value:
        return None
    return _uuid(value, "id")


def _name(store: Any, user_id: object) -> str:
    names = getattr(store, "display_names", {})
    found = names.get(user_id) or names.get(str(user_id))
    return str(found or "User")


def _current_version(store: Any, tool: dict[str, object]) -> dict[str, object] | None:
    for row in store.tool_versions.values():
        if row.get("tool_id") == tool.get("id"):
            return cast("dict[str, object]", row)
    return None


def _version_for(store: Any, qualified: str) -> dict[str, object] | None:
    for row in store.tool_versions.values():
        if row.get("qualified_name") == qualified:
            return cast("dict[str, object]", row)
    return None
