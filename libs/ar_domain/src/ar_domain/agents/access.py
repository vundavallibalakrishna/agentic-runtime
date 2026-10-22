"""Who may see and change an agent. Spec: docs/03-specs/05-agent-registry.md §2."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ar_domain.agents.logic import AgentView, can_see_agent

if TYPE_CHECKING:
    import uuid


@dataclass(frozen=True, slots=True)
class Actor:
    """Caller fields the registry needs. Permissions are the effective set."""

    tenant_id: uuid.UUID
    user_id: uuid.UUID
    permissions: frozenset[str]
    team_ids: frozenset[str] = frozenset()
    display_name: str = "User"

    def has(self, permission: str) -> bool:
        return permission in self.permissions


def _view(agent: dict[str, object]) -> AgentView:
    owner = agent.get("owner_user_id")
    team = agent.get("owner_team_id")
    return AgentView(
        tenant_id=str(agent["tenant_id"]),
        owner_user_id=None if owner is None else str(owner),
        owner_team_id=None if team is None else str(team),
        visibility=str(agent["visibility"]),
        status=str(agent["status"]),
        disabled=bool(agent.get("disabled")),
    )


def can_edit(agent: dict[str, object], actor: Actor) -> bool:
    """Owner, team editors, or someone who manages every agent."""
    if str(agent["tenant_id"]) != str(actor.tenant_id):
        return False
    if actor.has("agents:manage_all"):
        return True
    if agent.get("owner_user_id") is not None and str(agent["owner_user_id"]) == str(actor.user_id):
        return True
    team = agent.get("owner_team_id")
    return team is not None and str(team) in actor.team_ids and actor.has("agents:edit")


def can_publish(agent: dict[str, object], actor: Actor) -> bool:
    """Editors who may publish. High-risk agents need a second person."""
    if actor.has("agents:manage_all"):
        return True
    if not can_edit(agent, actor) or not actor.has("agents:publish"):
        return False
    return str(agent.get("risk_tier")) != "high"


def can_archive(agent: dict[str, object], actor: Actor) -> bool:
    """Owner or a tenant-wide manager."""
    if actor.has("agents:manage_all"):
        return True
    return agent.get("owner_user_id") is not None and str(agent["owner_user_id"]) == str(
        actor.user_id
    )


def can_see(agent: dict[str, object], actor: Actor) -> bool:
    """Visibility plus drafts, which only editors can see."""
    visible = can_see_agent(
        _view(agent),
        tenant_id=str(actor.tenant_id),
        user_id=str(actor.user_id),
        team_ids=set(actor.team_ids),
        manage_all=actor.has("agents:manage_all"),
    )
    if not visible:
        return False
    return bool(str(agent.get("status")) == "published" or can_edit(agent, actor))
