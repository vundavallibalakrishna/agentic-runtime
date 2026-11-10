"""Bounded repair retries and a structured tool-failure notice.

OQ-113: the notice is a field on the reply. The wording of the answer does not
decide whether the UI shows it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

NOTICE = "A tool call failed and was not recovered."
TERMINAL = "The retry budget was used and the step still failed."

# Words that show the answer already tells the person a tool did not do its job.
_ACKNOWLEDGES_FAILURE = (
    "fail",
    "error",
    "could not",
    "couldn't",
    "cannot",
    "can't",
    "unable",
    "was not able",
    "wasn't able",
    "not able",
    "retry",
    "try again",
    "blocked",
    "refused",
    "denied",
    "rejected",
    "prevented",
    "not permitted",
    "not allowed",
    "no access",
    "unavailable",
    "not available",
    "did not work",
    "didn't work",
    "no result",
    "nothing was returned",
)


def output_repair_limit(definition: dict[str, object] | None) -> int:
    """How many times a bad model reply may be sent back. Default keeps one retry."""
    return _limit(definition, default=1)


def tool_failure_limit(definition: dict[str, object] | None) -> int:
    """Consecutive tool failures before the run stops. Default matches the existing loop."""
    return _limit(definition, default=8)


def _limit(definition: dict[str, object] | None, *, default: int) -> int:
    if not isinstance(definition, dict):
        return default
    raw = definition.get("repair")
    if not isinstance(raw, dict):
        return default
    value = raw.get("max_attempts")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return default
    return value


def repair_prompt(kind: str, detail: str) -> str:
    """The user message that shows the model the validation error."""
    text = detail.strip() or "the previous reply was not usable"
    if kind == "schema":
        return (
            "The tool arguments did not match the schema: "
            f"{text}. Reply with a corrected tool call or a final answer."
        )
    if kind == "parse":
        return f"The previous reply was not valid JSON: {text}. Reply with only valid JSON."
    if kind == "output":
        return (
            "That was not valid JSON for the required schema: "
            f"{text}. Reply with only the JSON object."
        )
    return f"A tool call failed: {text}. Use the error and try a different call, or explain it."


def acknowledges_failure(answer: str) -> bool:
    lowered = answer.lower()
    return any(word in lowered for word in _ACKNOWLEDGES_FAILURE)


def tool_failure_notice(*, code: str = "tool_failed") -> dict[str, str]:
    """Structured marker. The UI renders this. It does not depend on the answer text."""
    message = TERMINAL if code == "repair_exhausted" else NOTICE
    return {"code": code, "message": message}


def apply_tool_failure(
    assistant: dict[str, Any], *, failed_open: bool, code: str = "tool_failed"
) -> dict[str, str] | None:
    """Attach the notice when a tool failed. Return it, or None when nothing failed."""
    if not failed_open:
        return None
    notice = tool_failure_notice(code=code)
    assistant["tool_failure"] = notice
    return notice
