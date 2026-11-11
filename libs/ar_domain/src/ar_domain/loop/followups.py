"""After-answer follow-up prompts. The prompt text is a shipped file, not a constant."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import orjson

from ar_domain.prompts.budget import read_prompt
from ar_domain.runs.request import asked

if TYPE_CHECKING:
    from typing import Any

_DEFAULT_COUNT = 3
_MAX_COUNT = 6


def wants_followups(definition: dict[str, object] | None, run: dict[str, object]) -> bool:
    """True when this turn should ask for follow-up prompts."""
    if asked(run, "suggest_followups") is True:
        return True
    output = definition.get("output") if isinstance(definition, dict) else None
    if not isinstance(output, dict):
        return False
    return output.get("followups") is True


def followup_count(definition: dict[str, object] | None) -> int:
    output = definition.get("output") if isinstance(definition, dict) else None
    raw = output.get("followup_count") if isinstance(output, dict) else None
    if raw is None and isinstance(output, dict):
        raw = output.get("followupCount")
    if isinstance(raw, bool) or not isinstance(raw, int):
        return _DEFAULT_COUNT
    return min(_MAX_COUNT, max(1, raw))


def parse_followups(text: str, *, limit: int) -> list[str]:
    """A JSON array of short prompts, or nothing when the model did not answer that way."""
    raw = text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        parsed = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return []
    if isinstance(parsed, dict):
        parsed = parsed.get("prompts") or parsed.get("followups")
    if not isinstance(parsed, list):
        return []
    prompts: list[str] = []
    for item in parsed:
        if not isinstance(item, str):
            continue
        prompt = " ".join(item.split())
        if prompt and prompt not in prompts:
            prompts.append(prompt[:240])
        if len(prompts) >= limit:
            break
    return prompts


async def suggest_followups(
    store: Any,
    run: dict[str, object],
    definition: dict[str, object] | None,
    user_text: str,
    answer: str,
) -> list[str]:
    """One extra model call. A failure leaves the answer unchanged and returns no prompts."""
    if not wants_followups(definition, run) or not answer.strip():
        return []
    limit = followup_count(definition)
    instruction = read_prompt("followups.md").replace("{limit}", str(limit))
    from ar_domain.tools.agent_loop import model_alias_for  # noqa: PLC0415

    tenant = run.get("tenant_id")
    if not isinstance(tenant, uuid.UUID):
        try:
            tenant = uuid.UUID(str(tenant))
        except ValueError:
            return []
    try:
        turn = await store.complete_turn(
            [
                {"role": "system", "content": instruction},
                {
                    "role": "user",
                    "content": f"Request:\n{user_text[:2000]}\n\nAnswer:\n{answer[:4000]}",
                },
            ],
            [],
            tenant_id=tenant,
            model_alias=model_alias_for(store, run),
        )
    except Exception:  # noqa: BLE001 - a follow-up miss never fails the turn
        return []
    if not isinstance(turn, dict):
        return []
    return parse_followups(str(turn.get("text") or ""), limit=limit)
