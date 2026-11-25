"""Per-model request options. Spec: docs/03-specs/04-model-gateway.md §3.

A model's options are what the person who registered it wrote on it. Nothing here
knows a vendor or a model family: a new model starts with none.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def request_options_of(model: Any) -> dict[str, object]:
    """The stored options of a model row or ORM object, always a dict."""
    if isinstance(model, dict):
        raw = model.get("request_options")
    else:
        raw = getattr(model, "request_options", None)
    return copy_request_options(raw) if isinstance(raw, dict) else {}


def copy_request_options(options: dict[str, object] | None) -> dict[str, object]:
    """Copy provider parameters without renaming keys.

    ``chat_template_kwargs`` is a provider field, not a public property. CamelCase
    on the way out and snake_case on the way in would both corrupt a round trip.
    """
    if not isinstance(options, dict):
        return {}
    copied: dict[str, object] = {}
    for key, value in options.items():
        copied[str(key)] = _copy_json(value)
    return copied


def _copy_json(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _copy_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_json(item) for item in value]
    return value


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
