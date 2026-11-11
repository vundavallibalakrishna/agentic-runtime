"""The chat-completion body every OpenAI-compatible caller sends.

Eval, the agent loop and routed completions share this builder so a provider
that rejects an omitted ``max_tokens`` (DeepInfra asks for 40960 and returns
400) cannot be reached by a second hand-rolled client.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from ar_domain.models.options import apply_request_options

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import Any

# A bound small enough for providers that treat a missing max_tokens as the
# model's full output window. A model row or AR_LLM_MAX_TOKENS overrides it.
DEFAULT_MAX_OUTPUT_TOKENS = 1024

_SECRET = re.compile(r"(?i)(bearer\s+|api[_-]?key[\"']?\s*[:=]\s*[\"']?|sk-)[A-Za-z0-9._\-]{6,}")


def default_max_output_tokens() -> int:
    """The install default, from ``AR_LLM_MAX_TOKENS`` when that is a positive int."""
    raw = os.environ.get("AR_LLM_MAX_TOKENS", "").strip()
    if not raw:
        return DEFAULT_MAX_OUTPUT_TOKENS
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_OUTPUT_TOKENS
    return value if value > 0 else DEFAULT_MAX_OUTPUT_TOKENS


def model_output_limit(model: Any) -> int | None:
    """``max_output_tokens`` on a model row, when the row sets one."""
    if isinstance(model, dict):
        raw = model.get("max_output_tokens")
    else:
        raw = getattr(model, "max_output_tokens", None)
    if isinstance(raw, int) and not isinstance(raw, bool) and raw > 0:
        return raw
    return None


def bound_max_tokens(
    requested: object = None,
    *,
    model_limit: int | None = None,
    default: int | None = None,
) -> int:
    """A positive cap. The model limit wins when the request asks for more."""
    floor = default if isinstance(default, int) and default > 0 else default_max_output_tokens()
    chosen = requested if isinstance(requested, int) and not isinstance(requested, bool) else 0
    if chosen <= 0:
        chosen = model_limit if isinstance(model_limit, int) and model_limit > 0 else floor
    if isinstance(model_limit, int) and model_limit > 0:
        chosen = min(chosen, model_limit)
    return max(1, chosen)


def chat_completion_body(
    *,
    model: str,
    messages: Sequence[object],
    tools: Sequence[object] | None = None,
    max_tokens: object = None,
    model_limit: int | None = None,
    options: dict[str, object] | None = None,
    tool_choice: str = "auto",
) -> dict[str, object]:
    """One chat-completion body. ``max_tokens`` is always set and bounded."""
    body: dict[str, object] = {
        "model": model,
        "messages": messages,
        "max_tokens": bound_max_tokens(max_tokens, model_limit=model_limit),
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice
    apply_request_options(body, options or {})
    # A stored option must not lift the cap past the model limit.
    body["max_tokens"] = bound_max_tokens(body.get("max_tokens"), model_limit=model_limit)
    return body


def redact_provider_error(body: bytes | str) -> str:
    """A short provider error with secrets removed. Safe to store on an eval row."""
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    cleaned = _SECRET.sub(r"\1[redacted]", text)
    cleaned = " ".join(cleaned.split())
    return cleaned[:500]
