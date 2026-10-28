"""AI governance register. Spec: docs/03-specs/21-records-governance.md §3."""

from __future__ import annotations

import hashlib
from datetime import date
from typing import TYPE_CHECKING, Any

from pydantic import JsonValue

from ar_common.errors import ArError, ErrorCode
from ar_common.ids import new_id
from ar_common.jcs import canonical_json
from ar_common.time import utcnow
from ar_domain.records.access import audit, missing, own, public, require
from ar_domain.records.memory import bucket

if TYPE_CHECKING:
    import uuid

    from ar_domain.agents.access import Actor

_MUTABLE = frozenset({"known_limitations", "review_due_at", "data_categories"})


class GovernanceBook:
    def __init__(self, store: Any) -> None:
        self.store = store

    def publish_card(
        self, actor: Actor, agent: dict[str, object], version: dict[str, object]
    ) -> dict[str, object]:
        version_id = version.get("id")
        for row in bucket(self.store, "cards").values():
            if row.get("agent_version_id") == version_id and own(row, actor.tenant_id):
                return public(row)
        raw_definition = version.get("definition")
        definition: dict[str, object] = raw_definition if isinstance(raw_definition, dict) else {}
        raw_tools = definition.get("tools")
        tools: list[object] = raw_tools if isinstance(raw_tools, list) else []
        oversight = _oversight(tools)
        body: dict[str, object] = {
            "purpose": str(agent.get("description") or agent.get("name") or ""),
            "risk_tier": str(definition.get("risk_tier") or "standard"),
            "data_categories": [],
            "oversight_mode": oversight,
            "eval_summary": None,
            "known_limitations": "",
            "owner_user_id": str(agent.get("owner_user_id") or ""),
            "review_due_at": None,
        }
        card_hash = hashlib.sha256(canonical_json(body)).hexdigest()  # type: ignore[arg-type]
        card_id = new_id()
        row = {
            "id": card_id,
            "tenant_id": actor.tenant_id,
            "agent_id": agent.get("id"),
            "agent_version_id": version_id,
            "version": version.get("version"),
            **body,
            "owner_user_id": agent.get("owner_user_id"),
            "card_hash": card_hash,
            "published_at": utcnow(),
            "created_at": utcnow(),
        }
        bucket(self.store, "cards")[card_id] = row
        audit(
            self.store,
            actor,
            "agent_card.published",
            "agent_card",
            card_id,
            {"agent_id": str(agent.get("id")), "card_hash": card_hash},
        )
        return public(row)

    def list_cards(
        self, actor: Actor, *, agent_id: uuid.UUID | None = None
    ) -> list[dict[str, object]]:
        if not actor.has("ai_governance:read") and not actor.has("agents:edit"):
            require(actor, "ai_governance:read")
        rows = []
        for row in bucket(self.store, "cards").values():
            if not own(row, actor.tenant_id):
                continue
            if agent_id is not None and row.get("agent_id") != agent_id:
                continue
            rows.append(public(row))
        return rows

    def update_card(
        self, actor: Actor, agent_id: uuid.UUID, version: int, body: dict[str, object]
    ) -> dict[str, object]:
        require(actor, "ai_governance:manage")
        extra = set(body) - _MUTABLE
        if extra:
            raise ArError(
                ErrorCode.VALIDATION_FAILED,
                "only limitations, review date and categories can change",
            )
        row = self._card(actor, agent_id, version)
        before = {key: row.get(key) for key in _MUTABLE}
        if "known_limitations" in body:
            row["known_limitations"] = str(body["known_limitations"])
        if "data_categories" in body and isinstance(body["data_categories"], list):
            row["data_categories"] = [str(item) for item in body["data_categories"]]
        if "review_due_at" in body:
            raw = body["review_due_at"]
            row["review_due_at"] = date.fromisoformat(str(raw)) if raw else None
        signed = {
            "purpose": str(row.get("purpose") or ""),
            "risk_tier": str(row.get("risk_tier") or ""),
            "data_categories": row.get("data_categories") or [],
            "oversight_mode": str(row.get("oversight_mode") or ""),
            "eval_summary": row.get("eval_summary"),
            "known_limitations": str(row.get("known_limitations") or ""),
            "owner_user_id": str(row.get("owner_user_id") or ""),
            "review_due_at": None
            if row.get("review_due_at") is None
            else str(row.get("review_due_at")),
        }
        row["card_hash"] = hashlib.sha256(canonical_json(signed)).hexdigest()  # type: ignore[arg-type]
        audit(
            self.store,
            actor,
            "agent_card.updated",
            "agent_card",
            row["id"],
            {"diff": {"old": before, "new": {key: row.get(key) for key in _MUTABLE}}},
        )
        return public(row)

    def list_incidents(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "ai_governance:read")
        return [
            public(row)
            for row in bucket(self.store, "incidents").values()
            if own(row, actor.tenant_id)
        ]

    def create_incident(self, actor: Actor, body: dict[str, object]) -> dict[str, object]:
        require(actor, "ai_governance:manage")
        severity = str(body.get("severity") or "low")
        if severity not in {"low", "medium", "high"}:
            raise ArError(ErrorCode.VALIDATION_FAILED, "severity is invalid")
        incident_id = new_id()
        row = {
            "id": incident_id,
            "tenant_id": actor.tenant_id,
            "agent_id": body.get("agent_id"),
            "agent_version_id": body.get("agent_version_id"),
            "run_id": body.get("run_id"),
            "severity": severity,
            "summary": str(body.get("summary") or ""),
            "status": "open",
            "detected_at": utcnow(),
            "closed_at": None,
            "created_at": utcnow(),
            "updated_at": utcnow(),
        }
        bucket(self.store, "incidents")[incident_id] = row
        audit(
            self.store,
            actor,
            "ai_incident.created",
            "ai_incident",
            incident_id,
            {"severity": severity},
        )
        self.store.domain_events.append(
            {
                "topic": "ai_incident.opened",
                "payload": {"incident_id": str(incident_id), "severity": severity},
                "at": utcnow().isoformat(),
            }
        )
        return public(row)

    def update_incident(
        self, actor: Actor, incident_id: uuid.UUID, body: dict[str, object]
    ) -> dict[str, object]:
        require(actor, "ai_governance:manage")
        row = bucket(self.store, "incidents").get(incident_id)
        if not isinstance(row, dict) or not own(row, actor.tenant_id):
            missing()
        if "status" in body:
            row["status"] = str(body["status"])
            if row["status"] == "closed":
                row["closed_at"] = utcnow()
        if "summary" in body:
            row["summary"] = str(body["summary"])
        if "severity" in body:
            row["severity"] = str(body["severity"])
        row["updated_at"] = utcnow()
        audit(self.store, actor, "ai_incident.updated", "ai_incident", incident_id, {})
        return public(row)

    def oversight(self, actor: Actor) -> list[dict[str, object]]:
        require(actor, "ai_governance:read")
        return [
            public(row)
            for row in bucket(self.store, "oversight").values()
            if own(row, actor.tenant_id)
        ]

    def note_oversight(self, tenant_id: uuid.UUID, agent_id: uuid.UUID, **counts: int) -> None:
        key = (str(tenant_id), str(agent_id), utcnow().date().isoformat())
        row = bucket(self.store, "oversight").get(key)
        if not isinstance(row, dict):
            row = {
                "tenant_id": tenant_id,
                "agent_id": agent_id,
                "day": utcnow().date().isoformat(),
                "approvals_requested": 0,
                "approvals_approved": 0,
                "approvals_rejected": 0,
                "signoffs_approved": 0,
                "signoffs_rejected": 0,
                "overrides": 0,
            }
            bucket(self.store, "oversight")[key] = row
        for name, value in counts.items():
            row[name] = int(str(row.get(name) or 0)) + value

    def export(self, actor: Actor, agent_ids: list[uuid.UUID]) -> dict[str, object]:
        require(actor, "ai_governance:read")
        from ar_domain.records.binders import BinderBook  # noqa: PLC0415

        cards = [
            row.get("id")
            for row in bucket(self.store, "cards").values()
            if own(row, actor.tenant_id) and (not agent_ids or row.get("agent_id") in agent_ids)
        ]
        binder = BinderBook(self.store).create(
            actor,
            {
                "title": "AI governance export",
                "selection": {"agent_card_ids": cards},
                "require_review": False,
            },
        )
        audit(
            self.store,
            actor,
            "ai_governance.exported",
            "binder",
            binder["id"],
            {"cards": len(cards)},
        )
        return {"binder_id": binder["id"]}

    def _card(self, actor: Actor, agent_id: uuid.UUID, version: int) -> dict[str, object]:
        for row in bucket(self.store, "cards").values():
            if (
                own(row, actor.tenant_id)
                and row.get("agent_id") == agent_id
                and row.get("version") == version
            ):
                return row
        missing()
        return {}


def _oversight(tools: list[object]) -> str:
    classes = []
    for tool in tools:
        if isinstance(tool, dict):
            classes.append(str(tool.get("risk_class") or tool.get("risk") or "R0"))
        else:
            classes.append("R0")
    if any(item in {"W2", "W3"} for item in classes):
        return "approval"
    if classes and all(item in {"R0", "R1"} for item in classes):
        return "autonomous_r0"
    if not classes:
        return "autonomous_r0"
    return "human_in_loop"


def card_hash(body: dict[str, JsonValue]) -> str:
    return hashlib.sha256(canonical_json(body)).hexdigest()
