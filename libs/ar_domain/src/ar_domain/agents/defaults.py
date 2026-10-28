"""Fill definition defaults before schema validation. Spec: definition-schema §12."""

from pydantic.alias_generators import to_camel

from ar_domain.agents.logic import assistant_definition

_BUDGET: dict[str, object] = {
    "max_steps": 8,
    "max_tokens": 16000,
    "max_cost_micros": 1_000_000,
    "max_wall_clock_s": 120,
    "max_tool_calls": 8,
    "max_parallel_tool_calls": 1,
}


def _snake(key: str) -> str:
    chars: list[str] = []
    for char in key:
        if char.isupper():
            chars.append("_")
            chars.append(char.lower())
        else:
            chars.append(char)
    return "".join(chars)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {_snake(str(key)): item for key, item in value.items()}


def _has(body: dict[str, object], key: str) -> bool:
    return key in body or to_camel(key) in body


def apply_definition_defaults(raw: dict[str, object]) -> dict[str, object]:
    """Return a copy with platform defaults for omitted fields."""
    base = assistant_definition()
    incoming = {_snake(str(key)): value for key, value in raw.items()}
    incoming.pop("resolved", None)
    merged = dict(base)
    merged.update(incoming)
    model = _mapping(base.get("model"))
    model.update(_mapping(incoming.get("model")))
    if not _has(model, "alias"):
        model["alias"] = "reasoning"
    if not _has(model, "fast_alias"):
        model["fast_alias"] = "fast"
    merged["model"] = model
    budget = dict(_BUDGET)
    budget.update(_mapping(incoming.get("budget")))
    merged["budget"] = budget
    persona = _mapping(base.get("persona"))
    persona.update(_mapping(incoming.get("persona")))
    if not _has(persona, "display_name"):
        persona["display_name"] = "Assistant"
    merged["persona"] = persona
    instructions = incoming.get("instructions", base.get("instructions"))
    merged["instructions"] = (
        instructions if isinstance(instructions, str) and instructions else "Help."
    )
    return merged
