"""Segregation of duties. Spec: docs/03-specs/09-policy-approvals.md §12."""

import uuid
from typing import TYPE_CHECKING

from ar_common.errors import NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.audit.memory import remember

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


class SodBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def assert_approval(self, actor: Actor, approval: dict[str, object], *, decision: str) -> None:
        if decision != "approve":
            self._roles(actor, approval.get("requested_for_user_id"), "approval")
            return
        violations = self.approval_violations(actor, approval)
        if violations:
            remember(
                self.store,
                tenant_id=actor.tenant_id,
                actor_id=actor.user_id,
                action="sod.violation_blocked",
                target_type="approval",
                target_id=approval.get("id"),
                detail={"violations": violations},
                outcome="failure",
            )
            raise ValidationFailedError("sod_violation")

    def approval_violations(
        self, actor: Actor, approval: Mapping[str, object]
    ) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        agent = self.store.agents.get(approval.get("agent_id"))
        if isinstance(agent, dict) and str(agent.get("owner_user_id")) == str(actor.user_id):
            found.append({"invariant": "agent_owner", "principal_id": str(actor.user_id)})
        if approval.get("four_eyes") and str(approval.get("requested_for_user_id")) == str(
            actor.user_id
        ):
            found.append({"invariant": "four_eyes", "principal_id": str(actor.user_id)})
        found.extend(self._role_hits(actor, approval.get("requested_for_user_id"), "approval"))
        return found

    def assert_signoff(self, actor: Actor, item: dict[str, object], *, decision: str) -> None:
        if decision == "reject":
            return
        violations = self.signoff_violations(actor, item)
        if violations:
            remember(
                self.store,
                tenant_id=actor.tenant_id,
                actor_id=actor.user_id,
                action="sod.violation_blocked",
                target_type="review_item",
                target_id=item.get("id"),
                detail={"violations": violations},
                outcome="failure",
            )
            raise ValidationFailedError("sod_violation")

    def signoff_violations(self, actor: Actor, item: Mapping[str, object]) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        if str(item.get("preparer_principal_id")) == str(actor.user_id):
            found.append({"invariant": "preparer", "principal_id": str(actor.user_id)})
        signed = {
            str(row.get("signer_principal_id"))
            for row in self.store.signoffs.values()
            if row.get("review_item_id") == item.get("id") and row.get("decision") == "approve"
        }
        if str(actor.user_id) in signed:
            found.append({"invariant": "distinct_levels", "principal_id": str(actor.user_id)})
        if self._owner_blocked(actor, item):
            found.append({"invariant": "agent_owner", "principal_id": str(actor.user_id)})
        found.extend(self._role_hits(actor, item.get("preparer_principal_id"), "signoff"))
        return found

    def assert_standing(self, actor: Actor, routine_id: uuid.UUID | None) -> None:
        if routine_id is None:
            return
        routines = getattr(self.store, "routines", {})
        routine = routines.get(routine_id)
        owner = routine.get("owner_user_id") if isinstance(routine, dict) else None
        if owner is not None and str(owner) == str(actor.user_id):
            raise ValidationFailedError("sod_self_approval")

    def simulate(
        self, actor: Actor, body: dict[str, object], decision: dict[str, object]
    ) -> dict[str, object]:
        del decision
        approval = {
            "agent_id": _uuid(body.get("agent_id")),
            "requested_for_user_id": _uuid(body.get("user_id")) or actor.user_id,
            "four_eyes": False,
            "id": None,
        }
        violations = self.approval_violations(actor, approval) if body.get("agent_id") else []
        return {"allowed": not violations, "violations": violations}

    def list_constraints(self, actor: Actor) -> list[dict[str, object]]:
        return [
            _view(row)
            for row in self.store.sod_constraints.values()
            if row.get("tenant_id") == actor.tenant_id
        ]

    def create_constraint(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        role_a = str(body.get("role_a") or "")
        role_b = str(body.get("role_b") or "")
        applies = str(body.get("applies_to") or "")
        if not role_a or not role_b or role_a == role_b:
            raise ValidationFailedError("role_a and role_b must differ")
        if applies not in {"approval", "signoff", "both"}:
            raise ValidationFailedError("applies_to is invalid")
        row = {
            "id": new_id(),
            "tenant_id": actor.tenant_id,
            "kind": "conflicting_roles",
            "role_a": role_a,
            "role_b": role_b,
            "applies_to": applies,
            "enabled": True,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        self.store.sod_constraints[row["id"]] = row
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="sod_constraint.created",
            target_type="sod_constraint",
            target_id=row["id"],
            detail={"role_a": role_a, "role_b": role_b},
        )
        return _view(row)

    def get_constraint(self, actor: Actor, constraint_id: uuid.UUID) -> dict[str, object]:
        return _view(self._require(actor, constraint_id))

    def patch_constraint(
        self, actor: Actor, constraint_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        row = self._require(actor, constraint_id)
        if "enabled" in body:
            row["enabled"] = bool(body["enabled"])
        if body.get("applies_to") in {"approval", "signoff", "both"}:
            row["applies_to"] = body["applies_to"]
        row["updated_at"] = utcnow()
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="sod_constraint.updated",
            target_type="sod_constraint",
            target_id=constraint_id,
            detail={},
        )
        return _view(row)

    def delete_constraint(self, actor: Actor, constraint_id: uuid.UUID) -> None:
        row = self._require(actor, constraint_id)
        del self.store.sod_constraints[constraint_id]
        remember(
            self.store,
            tenant_id=actor.tenant_id,
            actor_id=actor.user_id,
            action="sod_constraint.deleted",
            target_type="sod_constraint",
            target_id=row["id"],
            detail={},
        )

    def check(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        signer = Actor(
            actor.tenant_id,
            _uuid(body.get("signer_principal_id")) or actor.user_id,
            actor.permissions,
            roles=frozenset(
                self.store.user_roles.get(_uuid(body.get("signer_principal_id")), set())
            ),
        )
        action = str(body.get("action") or "approval")
        if action == "signoff":
            item = {
                "id": None,
                "preparer_principal_id": _uuid(body.get("preparer_principal_id")),
                "subject_type": "message",
                "agent_id": _uuid(body.get("agent_id")),
            }
            violations = self.signoff_violations(signer, item)
        else:
            approval = {
                "agent_id": _uuid(body.get("agent_id")),
                "requested_for_user_id": _uuid(body.get("preparer_principal_id")),
                "four_eyes": False,
            }
            violations = self.approval_violations(signer, approval)
        return {"allowed": not violations, "violations": violations}

    def _roles(self, actor: Actor, other: object, applies: str) -> None:
        if self._role_hits(actor, other, applies):
            raise ValidationFailedError("sod_violation")

    def _role_hits(self, actor: Actor, other_id: object, applies: str) -> list[dict[str, str]]:
        other_roles = set(self.store.user_roles.get(other_id, set()))
        mine = set(actor.roles)
        found: list[dict[str, str]] = []
        for row in self.store.sod_constraints.values():
            if row.get("tenant_id") != actor.tenant_id or row.get("enabled") is not True:
                continue
            scope = str(row.get("applies_to"))
            if scope not in {applies, "both"}:
                continue
            left, right = str(row.get("role_a")), str(row.get("role_b"))
            if (left in mine and right in other_roles) or (right in mine and left in other_roles):
                found.append({"invariant": "conflicting_roles", "principal_id": str(actor.user_id)})
        return found

    def _owner_blocked(self, actor: Actor, item: Mapping[str, object]) -> bool:
        if item.get("subject_type") not in {"message", "artifact", "run_record", "binder"}:
            return False
        agent_id = item.get("agent_id") or _subject_agent(self.store, item)
        agent = self.store.agents.get(agent_id)
        return isinstance(agent, dict) and str(agent.get("owner_user_id")) == str(actor.user_id)

    def _require(self, actor: Actor, constraint_id: uuid.UUID) -> dict[str, object]:
        row = self.store.sod_constraints.get(constraint_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError("constraint not found")
        return row


def _view(row: dict[str, object]) -> dict[str, object]:
    return {
        "id": row.get("id"),
        "kind": row.get("kind"),
        "role_a": row.get("role_a"),
        "role_b": row.get("role_b"),
        "applies_to": row.get("applies_to"),
        "enabled": row.get("enabled"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _uuid(value: object) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _subject_agent(store: Any, item: Mapping[str, object]) -> uuid.UUID | None:
    subject_id = item.get("subject_id")
    if item.get("subject_type") == "message":
        message = store.messages.get(subject_id)
        if isinstance(message, dict):
            run = store.runs.get(message.get("run_id"))
            if isinstance(run, dict):
                agent_id = run.get("agent_id")
                return agent_id if isinstance(agent_id, uuid.UUID) else None
    return None
