"""Limits and tool descriptions for calling another agent."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from ar_domain.skills.logic import platform_max_depth

_TIMEOUT_DEFAULT = 45
_FANOUT_CAP = 8


def whole(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


class SubagentLimits(TypedDict):
    allowed: list[str]
    allow_self_clone: bool
    max_depth: int
    max_parallel: int
    child_timeout_s: int


def subagent_spec(definition: dict[str, object]) -> SubagentLimits:
    """Normalise the subagent block. Missing numbers use the platform defaults."""
    raw = definition.get("subagents")
    spec = raw if isinstance(raw, dict) else {}
    raw_allowed = spec.get("allowed")
    allowed = (
        [str(item) for item in raw_allowed if str(item).strip()]
        if isinstance(raw_allowed, list)
        else []
    )
    depth = whole(spec.get("max_depth"), 1)
    parallel = whole(spec.get("max_parallel"), 3)
    timeout = whole(spec.get("child_timeout_s"), _TIMEOUT_DEFAULT)
    return {
        "allowed": allowed,
        "allow_self_clone": spec.get("allow_self_clone") is True,
        "max_depth": min(max(depth, 1), platform_max_depth()),
        "max_parallel": min(max(parallel, 1), _FANOUT_CAP),
        "child_timeout_s": min(max(timeout, 1), 600),
    }


def human_enabled(definition: dict[str, object]) -> bool:
    raw = definition.get("human")
    return isinstance(raw, dict) and raw.get("enabled") is True


def agent_slug(store: Any, run: dict[str, object]) -> str:
    agent = store.agents.get(run.get("agent_id"))
    slug = agent.get("slug") if isinstance(agent, dict) else None
    if isinstance(slug, str):
        return slug
    return ""


def agent_by_slug(store: Any, tenant: object, slug: str) -> dict[str, object] | None:
    for row in store.agents.values():
        if not isinstance(row, dict) or row.get("slug") != slug:
            continue
        if tenant is not None and row.get("tenant_id") != tenant:
            continue
        return row
    return None


def contract_line(store: Any, tenant: object, slug: str) -> str:
    """Name, description and schemas the parent model is allowed to see."""
    agent = agent_by_slug(store, tenant, slug)
    if agent is None:
        return slug
    version_id = agent.get("published_version_id")
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    body = definition if isinstance(definition, dict) else {}
    contract = body.get("contract")
    spec = contract if isinstance(contract, dict) else {}
    description = str(spec.get("description") or agent.get("description") or slug)
    return (
        f"{slug}: {description}. "
        f"Input schema: {spec.get('input_schema') or {'task': 'string'}}. "
        f"Output schema: {spec.get('output_schema') or {'answer': 'string'}}."
    )


def chain(run: dict[str, object]) -> list[str]:
    raw = run.get("agent_chain")
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item)]


def is_cycle(run: dict[str, object], slug: str, *, allow_self: bool) -> bool:
    """A slug already in the chain is a cycle. A self-clone of the current agent is not."""
    seen = chain(run)
    if slug not in seen:
        return False
    current = seen[-1] if seen else ""
    return not (allow_self and slug == current)


def depth_blocked(run: dict[str, object], max_depth: int) -> bool:
    return whole(run.get("depth"), 0) + 1 > max_depth
