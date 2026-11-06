"""Assemble the ordered prompt. Spec: docs/03-specs/07-agent-runtime.md §4."""

from dataclasses import dataclass

import orjson

from ar_common.wrapping import wrap_documents, wrap_untrusted
from ar_domain.prompts.budget import estimate_tokens, prompt_hash, read_prompt, truncate_history
from ar_domain.tools.structured import output_schema


@dataclass(frozen=True, slots=True)
class PromptBundle:
    """Messages sent to the model, plus the hash stored on the step."""

    messages: tuple[dict[str, str], ...]
    tools: tuple[dict[str, str], ...]
    estimated_tokens: int
    prompt_hash: str


def build_prompt(run: dict[str, object]) -> PromptBundle:
    """Fixed block order. Blocks 1-5 are never dropped to make room for history."""
    raw_definition = run.get("definition")
    definition = raw_definition if isinstance(raw_definition, dict) else {}
    raw_persona = definition.get("persona")
    persona = raw_persona if isinstance(raw_persona, dict) else {}
    display = str(persona.get("display_name") or persona.get("displayName") or "Assistant")
    instructions = str(definition.get("instructions") or "")
    raw_session = run.get("session")
    session = raw_session if isinstance(raw_session, dict) else {}
    blocks = [
        read_prompt("platform.md"),
        read_prompt("tool_use.md") if uses_tools(definition) else "",
        f"You are {display}.\n\n{instructions}".strip(),
        output_block(definition),
        str(run.get("capabilities") or ""),
        str(run.get("skills") or ""),
        _session(session),
        str(run.get("memory") or ""),
        str(run.get("plan") or ""),
        str(run.get("summary") or ""),
        _knowledge(run.get("documents")),
    ]
    system = "\n\n".join(block for block in blocks if block)
    history = _history(run.get("history"))
    current = str(run.get("user_text") or "")
    files = run.get("files")
    if isinstance(files, str) and files:
        current = with_attachments(current, files)
    reserved = estimate_tokens(system) + estimate_tokens(current)
    budget_value = run.get("token_budget")
    budget = budget_value if isinstance(budget_value, int) else 8000
    kept = truncate_history(history, budget=budget, reserved=reserved)
    messages = [{"role": "system", "content": system}, *kept]
    if current:
        messages.append({"role": "user", "content": current})
    digest = prompt_hash(messages)
    return PromptBundle(
        messages=tuple(messages),
        tools=(),
        estimated_tokens=sum(estimate_tokens(item["content"]) for item in messages),
        prompt_hash=digest,
    )


def uses_tools(definition: dict[str, object]) -> bool:
    """True when the agent can call something: a bound tool or another agent."""
    if definition.get("tools"):
        return True
    subagents = definition.get("subagents")
    if not isinstance(subagents, dict):
        return False
    return bool(subagents.get("allowed")) or subagents.get("allow_self_clone") is True


def output_block(definition: dict[str, object]) -> str:
    """The instruction to answer in the agent's output schema. Empty when it has none."""
    schema = output_schema(definition)
    if not schema:
        return ""
    return f"Return only JSON matching this schema:\n{orjson.dumps(schema).decode()}"


def with_attachments(text: str, lines: str) -> str:
    """A message followed by the files attached to it.

    The person's own words stay as they wrote them. The file lines carry names the
    person did not type into the chat, so they are wrapped as data. ``lines`` comes from
    ``ar_domain.files.attachments.attachment_lines``.
    """
    if not lines:
        return text
    note = (
        "Files attached to this message. Each is in the working folder at its path. "
        "Give a tool the id or the path."
    )
    block = f"{note}\n{wrap_untrusted(source='file:attached', content=lines)}"
    return f"{text}\n\n{block}" if text else block


def _session(session: dict[str, object]) -> str:
    if not session:
        return ""
    return (
        f"Today is {session.get('date', '')} ({session.get('timezone', 'UTC')}). "
        f"User: {session.get('user_name', '')}. Locale: {session.get('locale', 'en')}. "
        f"Channel: {session.get('channel', 'web')}. Tenant: {session.get('tenant_name', '')}."
    )


def _knowledge(documents: object) -> str:
    if not isinstance(documents, list) or not documents:
        return ""
    rows = [item for item in documents if isinstance(item, dict)]
    if not rows:
        return ""
    return wrap_documents(rows)


def _history(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    return [
        {"role": item["role"], "content": item["content"]}
        for item in value
        if isinstance(item, dict)
        and isinstance(item.get("role"), str)
        and isinstance(item.get("content"), str)
    ]
