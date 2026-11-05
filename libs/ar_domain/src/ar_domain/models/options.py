"""Per-model request options. Spec: docs/03-specs/04-model-gateway.md §3."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

# Models whose chat template reasons out loud unless asked not to. The rule lives
# here once, as a registration default a tenant can see and change on the model row.
_NO_THINKING_FAMILIES = ("qwen3",)


def default_request_options(upstream_model: str) -> dict[str, object]:
    """Options a newly registered model starts with, from its upstream name."""
    lowered = upstream_model.lower()
    if any(family in lowered for family in _NO_THINKING_FAMILIES):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


def request_options_of(model: Any) -> dict[str, object]:
    """The stored options of a model row or ORM object, always a dict."""
    if isinstance(model, dict):
        raw = model.get("request_options")
    else:
        raw = getattr(model, "request_options", None)
    return {str(key): value for key, value in raw.items()} if isinstance(raw, dict) else {}


def apply_request_options(body: dict[str, object], options: dict[str, object]) -> dict[str, object]:
    """Merge options into a chat-completion body without overriding what the caller set."""
    for key, value in options.items():
        current = body.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged = dict(value)
            merged.update(current)
            body[key] = merged
        else:
            body.setdefault(key, value)
    return body
