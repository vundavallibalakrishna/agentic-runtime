"""Natural-language builder sessions. Spec: docs/03-specs/05-agent-registry.md §11."""

import uuid
from typing import TYPE_CHECKING, Any, cast

from ar_common.errors import ArError, ErrorCode, NotFoundError, ValidationFailedError
from ar_common.ids import new_id
from ar_common.time import utcnow
from ar_domain.agents.assist import draft_from_description, proposal_bundle, slug_from
from ar_domain.agents.service import AgentLifecycle
from ar_domain.agents.validation import reference_issues, schema_errors, split_issues

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor


class BuilderService:
    """Sessions that propose a definition and apply it as a draft."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def _session(self, actor: Actor, session_id: uuid.UUID) -> dict[str, object]:
        row = self.store.builder_sessions.get(session_id)
        if not isinstance(row, dict) or row.get("tenant_id") != actor.tenant_id:
            raise NotFoundError()
        if row.get("user_id") != actor.user_id and not actor.has("agents:manage_all"):
            raise NotFoundError()
        return row

    def _builder_agent(self, actor: Actor) -> dict[str, object]:
        AgentLifecycle(self.store).ensure_builtins(actor.tenant_id, actor.user_id)
        for agent in self.store.agents.values():
            if agent.get("tenant_id") == actor.tenant_id and agent.get("slug") == "builder":
                return cast("dict[str, object]", agent)
        raise NotFoundError()

    async def start(self, actor: Actor, instruction: str) -> dict[str, object]:
        drafted = await draft_from_description(self.store, actor, instruction)
        definition = cast("dict[str, object]", drafted["definition"])
        proposal = proposal_bundle(instruction, definition)
        agent = self._builder_agent(actor)
        now = utcnow()
        conversation_id = new_id()
        run_id = new_id()
        self.store.conversations[conversation_id] = {
            "id": conversation_id,
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "agent_version_id": agent.get("published_version_id"),
            "title": instruction[:80],
            "status": "active",
            "pinned": False,
            "is_preview": True,
            "active_run_id": None,
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        self.store.runs[run_id] = {
            "id": run_id,
            "tenant_id": actor.tenant_id,
            "conversation_id": conversation_id,
            "agent_id": agent["id"],
            "user_id": actor.user_id,
            "status": "completed",
            "trigger": "chat",
            "label": "preview",
            "created_at": now,
            "ended_at": now,
        }
        session_id = new_id()
        self.store.builder_sessions[session_id] = {
            "id": session_id,
            "tenant_id": actor.tenant_id,
            "user_id": actor.user_id,
            "conversation_id": conversation_id,
            "run_id": run_id,
            "instruction": instruction,
            "messages": [
                {"role": "user", "text": instruction},
                {"role": "assistant", "text": drafted["rationale"]},
            ],
            "proposal": proposal,
            "warnings": drafted.get("warnings") or [],
            "created_at": now,
        }
        return {
            "session_id": str(session_id),
            "conversation_id": str(conversation_id),
            "run_id": str(run_id),
        }

    def read(self, actor: Actor, session_id: uuid.UUID) -> dict[str, object]:
        row = self._session(actor, session_id)
        proposal = row.get("proposal")
        errors, warnings = self._panel(actor, proposal)
        return {
            "session_id": str(row["id"]),
            "messages": row.get("messages"),
            "proposal": proposal,
            "validation": {"errors": errors, "warnings": warnings or row.get("warnings") or []},
        }

    async def message(self, actor: Actor, session_id: uuid.UUID, text: str) -> dict[str, object]:
        row = self._session(actor, session_id)
        combined = f"{row.get('instruction', '')}\n\n{text}".strip()
        drafted = await draft_from_description(self.store, actor, combined)
        definition = cast("dict[str, object]", drafted["definition"])
        proposal = proposal_bundle(combined, definition)
        raw_messages = row.get("messages")
        messages = list(raw_messages) if isinstance(raw_messages, list) else []
        messages.append({"role": "user", "text": text})
        messages.append({"role": "assistant", "text": drafted["rationale"]})
        row["messages"] = messages
        row["proposal"] = proposal
        row["warnings"] = drafted.get("warnings") or []
        row["instruction"] = combined
        run_id = new_id()
        return {"run_id": str(run_id)}

    def apply(
        self, actor: Actor, session_id: uuid.UUID, *, mode: str, agent_id: uuid.UUID | None
    ) -> dict[str, object]:
        row = self._session(actor, session_id)
        proposal = row.get("proposal")
        errors, _warnings = self._panel(actor, proposal)
        if errors:
            raise ValidationFailedError("the proposal still has errors")
        spec = _spec(proposal)
        life = AgentLifecycle(self.store)
        if mode == "update":
            if agent_id is None:
                raise ArError(ErrorCode.VALIDATION_FAILED, "agentId is required to update")
            saved = life.save_draft(actor, agent_id, spec)
            return {"agent_id": str(agent_id), "version_id": saved.get("id")}
        metadata = _metadata(proposal)
        slug = str(metadata.get("slug") or slug_from(str(row.get("instruction") or "agent")))
        name = str(metadata.get("name") or slug)
        base = slug
        suffix = 2
        while any(
            agent.get("tenant_id") == actor.tenant_id and agent.get("slug") == slug
            for agent in self.store.agents.values()
        ):
            slug = f"{base[:58]}-{suffix}"
            suffix += 1
        created = life.create(actor, slug=slug, name=name, definition=spec, template="blank")
        created_id = uuid.UUID(str(created["id"]))
        agent = self.store.agents[created_id]
        version_id = agent.get("draft_version_id")
        if agent.get("status") == "published":
            raise ArError(ErrorCode.INVALID_STATE, "apply must not publish")
        return {
            "agent_id": str(created_id),
            "version_id": None if version_id is None else str(version_id),
        }

    def _panel(
        self, actor: Actor, proposal: object
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        spec = _spec(proposal)
        normalised, schema = schema_errors(spec)
        if normalised is None:
            return (
                [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in schema],
                [],
            )
        issues, _resolved = reference_issues(
            normalised, AgentLifecycle(self.store).context(actor, warnings=True)
        )
        errors, warnings = split_issues(issues)
        return (
            [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in errors],
            [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in warnings],
        )


def _resources(proposal: object) -> dict[str, object]:
    if not isinstance(proposal, dict):
        return {}
    resources = proposal.get("resources")
    if isinstance(resources, list) and resources and isinstance(resources[0], dict):
        return cast("dict[str, object]", resources[0])
    return {}


def _spec(proposal: object) -> dict[str, object]:
    resource = _resources(proposal)
    spec = resource.get("spec")
    if isinstance(spec, dict):
        return cast("dict[str, object]", spec)
    return {}


def _metadata(proposal: object) -> dict[str, object]:
    resource = _resources(proposal)
    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        return cast("dict[str, object]", metadata)
    return {}
