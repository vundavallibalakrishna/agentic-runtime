"""Limits and tool descriptions for calling another agent."""

from __future__ import annotations

import uuid
from typing import Any, TypedDict

from ar_domain.runs.request import asked
from ar_domain.skills.logic import platform_max_depth

_TIMEOUT_DEFAULT = 45
_FANOUT_CAP = 8
_CALLS_DEFAULT = 16


def whole(value: object, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


class SubagentLimits(TypedDict):
    allowed: list[str]
    allow_self_clone: bool
    max_depth: int
    max_parallel: int
    max_calls: int
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
    width = min(max(parallel, 1), _FANOUT_CAP)
    return {
        "allowed": allowed,
        "allow_self_clone": spec.get("allow_self_clone") is True,
        "max_depth": min(max(depth, 1), platform_max_depth()),
        "max_parallel": width,
        # One call may always name as many agents as may run at once.
        "max_calls": max(width, min(max(whole(spec.get("max_calls"), _CALLS_DEFAULT), 1), 64)),
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


def contract_of(store: Any, tenant: object, slug: str) -> dict[str, object]:
    """What the agent's published version says a caller gives it and gets back."""
    agent = agent_by_slug(store, tenant, slug)
    version_id = agent.get("published_version_id") if agent is not None else None
    version = store.versions.get(version_id) if isinstance(version_id, uuid.UUID) else None
    definition = version.get("definition") if isinstance(version, dict) else None
    contract = definition.get("contract") if isinstance(definition, dict) else None
    return contract if isinstance(contract, dict) else {}


def contract_line(store: Any, tenant: object, slug: str) -> str:
    """Name, description and schemas the parent model is allowed to see."""
    agent = agent_by_slug(store, tenant, slug)
    if agent is None:
        return slug
    spec = contract_of(store, tenant, slug)
    description = str(spec.get("description") or agent.get("description") or slug)
    line = (
        f"{slug}: {description}. "
        f"Input schema: {spec.get('input_schema') or {'task': 'string'}}. "
        f"Output schema: {spec.get('output_schema') or {'answer': 'string'}}."
    )
    if enforced(spec.get("input_schema")) is not None:
        line += " Pass an `input` object that matches its input schema."
    return line


def enforced(schema: object) -> dict[str, object] | None:
    """The schema, when it is a JSON Schema for an object. Otherwise None.

    A contract may describe its shapes loosely, as in ``{"answer": "string"}``. That is
    shown to the caller and nothing is checked against it. A schema that says it is an
    object, or lists properties, is a promise: what is passed in and what comes back are
    checked against it.
    """
    if not isinstance(schema, dict):
        return None
    if schema.get("type") == "object" or isinstance(schema.get("properties"), dict):
        return schema
    return None


def input_problem(store: Any, tenant: object, slug: str, given: object) -> str | None:
    """Why what the caller passed does not fit the called agent's input schema, if so."""
    schema = enforced(contract_of(store, tenant, slug).get("input_schema"))
    if schema is None:
        return None
    if not isinstance(given, dict):
        return f"{slug} needs an `input` object that matches its input schema: {schema}."
    from ar_domain.tools.logic import schema_errors  # noqa: PLC0415

    problem = schema_errors(schema, given)
    return None if problem is None else f"`input` does not match {slug}'s input schema ({problem})."


def brief(task: str, given: object) -> str:
    """The called agent's message: the task, and the input the caller passed with it."""
    if not isinstance(given, dict) or not given:
        return task
    import orjson  # noqa: PLC0415

    body = orjson.dumps(given, option=orjson.OPT_INDENT_2).decode()
    return f"{task}\n\nInput:\n{body}".strip()


def chain(run: dict[str, object]) -> list[str]:
    raw = run.get("agent_chain")
    if not isinstance(raw, list):
        # The copy on the request is what another process reads back from the database.
        raw = asked(run, "agent_chain")
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
