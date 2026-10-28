"""Agent visibility and definition hashing. Spec: docs/03-specs/05-agent-registry.md."""

from dataclasses import dataclass
from typing import cast

from pydantic import JsonValue

from ar_common.jcs import args_hash


@dataclass(frozen=True, slots=True)
class AgentView:
    """The fields visibility checks need."""

    tenant_id: str
    owner_user_id: str | None
    owner_team_id: str | None
    visibility: str
    status: str
    disabled: bool


def definition_hash(definition: dict[str, object]) -> str:
    """SHA-256 hex of the JCS encoding of a definition."""
    return args_hash(cast("JsonValue", definition))


def can_see_agent(
    agent: AgentView,
    *,
    tenant_id: str,
    user_id: str,
    team_ids: set[str],
    manage_all: bool,
) -> bool:
    """Return whether the caller may see this agent."""
    if agent.tenant_id != tenant_id:
        return False
    if manage_all:
        return True
    if agent.visibility == "tenant":
        return True
    if agent.visibility == "team" and agent.owner_team_id in team_ids:
        return True
    return agent.visibility == "private" and agent.owner_user_id == user_id


def can_start_run(agent: AgentView, *, can_see: bool) -> bool:
    """Published, visible, enabled agents can start runs."""
    return can_see and agent.status == "published" and not agent.disabled


def assistant_definition() -> dict[str, object]:
    """Schema default. No tools, so the v1 Temporal loop stays on model steps."""
    return {
        "persona": {
            "display_name": "Assistant",
            "greeting": "Hello. I can help with writing, summaries and questions.",
        },
        "instructions": (
            "You are a helpful corporate assistant. Answer clearly and briefly. "
            "When the user attaches a file, mention its name in the answer."
        ),
        "starter_prompts": [
            "Summarise the attached document",
            "Draft a short status update",
            "Explain this in simpler terms",
        ],
        "model": {"alias": "reasoning", "fast_alias": "fast", "vision_alias": "vision"},
        "tools": [],
        "budget": {
            "max_steps": 8,
            "max_tokens": 16000,
            "max_cost_micros": 1_000_000,
            "max_wall_clock_s": 120,
            "max_tool_calls": 0,
            "max_parallel_tool_calls": 1,
        },
    }


def published_assistant_definition() -> dict[str, object]:
    """The seeded assistant can file a ticket and create a pet. The v1 loop does not."""
    definition = assistant_definition()
    definition["tools"] = [
        {"server": "tickets", "version": "*", "include": ["*"]},
        {"server": "petstore", "version": "*", "include": ["create_pet"]},
    ]
    budget = definition.get("budget")
    if isinstance(budget, dict):
        budget["max_tool_calls"] = 8
    definition["instructions"] = (
        str(definition.get("instructions") or "")
        + " When the person asks you to file a ticket or create a pet, call the tool."
        + " Do not say the action is done unless the tool ran."
    )
    return definition


def enable_assistant_tools(store: object) -> None:
    """Give an already published assistant the tool budget. Other agents stay unchanged."""
    agents = getattr(store, "agents", {})
    versions = getattr(store, "versions", {})
    if not isinstance(agents, dict) or not isinstance(versions, dict):
        return
    wanted = published_assistant_definition()
    for agent in agents.values():
        if not isinstance(agent, dict) or agent.get("slug") != "assistant":
            continue
        version = versions.get(agent.get("published_version_id"))
        if not isinstance(version, dict):
            continue
        current = version.get("definition")
        tools = current.get("tools") if isinstance(current, dict) else None
        budget = current.get("budget") if isinstance(current, dict) else None
        bound = isinstance(tools, list) and any(
            isinstance(item, dict) and item.get("server") == "tickets" for item in tools
        )
        calls = int(budget.get("max_tool_calls") or 0) if isinstance(budget, dict) else 0
        if bound and calls > 0:
            continue
        version["definition"] = wanted
