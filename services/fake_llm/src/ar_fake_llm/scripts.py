"""Script matching for fake-llm. Spec: docs/08-quality/testing-strategy.md §4."""

import re
from typing import Literal

import orjson
from pydantic import BaseModel, ConfigDict, Field


class ScriptMatch(BaseModel):
    """How a script selects a request. The first matching script wins."""

    model_config = ConfigDict(extra="forbid")

    contains: str | None = None
    regex: str | None = None
    system_contains: str | None = None
    last_tool_result: dict[str, str] | None = None


class ToolCallSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class ScriptError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: int = 500


class ScriptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    tool_calls: list[ToolCallSpec] | None = None
    error: ScriptError | None = None
    delay_ms: int = 0
    tokens_per_chunk: int = 8


class Script(BaseModel):
    model_config = ConfigDict(extra="forbid")

    match: ScriptMatch
    respond: ScriptResponse


class ChatTurn(BaseModel):
    """The parts of a chat request a script can see."""

    model_config = ConfigDict(extra="forbid")

    last_user: str
    system: str
    last_tool_name: str | None
    last_tool_result: str | None


def matches(script: Script, turn: ChatTurn) -> bool:
    """Return whether ``script`` applies to this turn."""
    rule = script.match
    user_ok = (rule.contains is None or rule.contains in turn.last_user) and (
        rule.regex is None or re.search(rule.regex, turn.last_user) is not None
    )
    system_ok = rule.system_contains is None or rule.system_contains in turn.system
    if not user_ok or not system_ok:
        return False
    if rule.last_tool_result is None:
        return True
    tool = rule.last_tool_result.get("tool")
    contains = rule.last_tool_result.get("contains")
    name_ok = turn.last_tool_name is not None and (tool is None or tool == turn.last_tool_name)
    body_ok = contains is None or contains in (turn.last_tool_result or "")
    return name_ok and body_ok


def render_text(template: str, turn: ChatTurn) -> str:
    """Substitute ``{{last_user}}`` and ``{{last_tool_result}}``."""
    return template.replace("{{last_user}}", turn.last_user).replace(
        "{{last_tool_result}}", turn.last_tool_result or ""
    )


def default_response(turn: ChatTurn) -> ScriptResponse:
    """Echo, or honour a ``/tool <name> <json>`` command."""
    command = _tool_command(turn.last_user)
    if command is not None:
        name, arguments = command
        return ScriptResponse(tool_calls=[ToolCallSpec(name=name, arguments=arguments)])
    return ScriptResponse(text=f"fake: {turn.last_user}")


def _tool_command(text: str) -> tuple[str, dict[str, object]] | None:
    if not text.startswith("/tool "):
        return None
    rest = text.removeprefix("/tool ").strip()
    name, _, raw = rest.partition(" ")
    if not name:
        return None
    arguments: dict[str, object] = {}
    if raw:
        parsed = orjson.loads(raw)
        if isinstance(parsed, dict):
            arguments = parsed
    return name, arguments


def select(scripts: list[Script], turn: ChatTurn) -> ScriptResponse:
    """Return the first matching script, or the default echo."""
    for script in scripts:
        if matches(script, turn):
            respond = script.respond
            if respond.text is not None:
                return respond.model_copy(update={"text": render_text(respond.text, turn)})
            return respond
    return default_response(turn)


def token_count(text: str) -> int:
    """Whitespace-split count times 1.3, rounded. Spec: testing-strategy §4."""
    parts = text.split()
    return round(len(parts) * 1.3)


Role = Literal["system", "user", "assistant", "tool"]
