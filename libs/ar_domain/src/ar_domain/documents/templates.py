"""Named reading tasks from agent config or a pack file.

A template is a prompt, an optional checklist, an optional output schema and
an optional preferred strategy. Core does not ship one. A missing id is an
error; a file that is not the schema is ignored.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orjson
from jsonschema import Draft202012Validator

from ar_common.errors import ArError, ErrorCode
from ar_common.settings import get_settings

TEMPLATE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["id", "prompt"],
    "properties": {
        "id": {"type": "string", "minLength": 1},
        "prompt": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "outputSchema": {"type": "object"},
        "strategy": {"type": "string"},
    },
}


@dataclass(frozen=True, slots=True)
class TaskTemplate:
    """One reusable task. ``strategy`` is empty when the template does not prefer one."""

    id: str
    prompt: str
    items: tuple[str, ...]
    output_schema: dict[str, object] | None
    strategy: str


def resolve_template(
    definition: dict[str, object] | None,
    template_id: str,
    *,
    packs_dir: str | None = None,
) -> TaskTemplate:
    """The template from the agent, otherwise from a pack file. Unknown is an error."""
    wanted = template_id.strip()
    if not wanted:
        raise ArError(ErrorCode.VALIDATION_FAILED, "taskTemplate is empty")
    found = _from_definition(definition).get(wanted) or _from_packs(wanted, packs_dir)
    if found is None:
        raise ArError(ErrorCode.VALIDATION_FAILED, "taskTemplate was not found")
    return found


def apply_template(
    template: TaskTemplate | None,
    *,
    instruction: str,
    items: list[object],
    response_format: dict[str, object] | None,
    strategy: str,
) -> tuple[str, list[object], dict[str, object] | None, str]:
    """Fill only the fields the request left empty. The instruction is still the request."""
    if template is None:
        return instruction, items, response_format, strategy
    text = instruction
    if template.prompt.strip():
        text = f"{template.prompt.strip()}\n\n{instruction}".strip()
    chosen_items = items or [{"id": "", "text": item} for item in template.items]
    schema = response_format if response_format else template.output_schema
    chosen_strategy = strategy or template.strategy
    return text, chosen_items, schema, chosen_strategy


def _from_definition(definition: dict[str, object] | None) -> dict[str, TaskTemplate]:
    if not isinstance(definition, dict):
        return {}
    raw = definition.get("task_templates", definition.get("taskTemplates"))
    found: dict[str, TaskTemplate] = {}
    if not isinstance(raw, list):
        return found
    for item in raw:
        parsed = _parse(item)
        if parsed is not None:
            found[parsed.id] = parsed
    return found


def _from_packs(template_id: str, packs_dir: str | None) -> TaskTemplate | None:
    root = Path(packs_dir if packs_dir is not None else get_settings().packs_dir)
    if not root.is_dir():
        return None
    paths = list(root.glob("task-templates/*.json")) + list(root.glob("*/task-templates/*.json"))
    for path in sorted(paths):
        parsed = _read(path)
        if parsed is not None and parsed.id == template_id:
            return parsed
    return None


def _read(path: Path) -> TaskTemplate | None:
    try:
        raw = orjson.loads(path.read_bytes())
    except orjson.JSONDecodeError:
        return None
    return _parse(raw)


def _parse(raw: object) -> TaskTemplate | None:
    wired = _wire(raw)
    if wired is None or list(Draft202012Validator(TEMPLATE_SCHEMA).iter_errors(wired)):
        return None
    raw = wired
    items = raw.get("items")
    schema = raw.get("outputSchema")
    strategy = str(raw.get("strategy") or "").strip()
    return TaskTemplate(
        id=str(raw.get("id") or "").strip(),
        prompt=str(raw.get("prompt") or ""),
        items=tuple(str(item) for item in items) if isinstance(items, list) else (),
        output_schema=schema if isinstance(schema, dict) and schema else None,
        strategy=strategy,
    )


def _wire(raw: object) -> dict[str, object] | None:
    """CamelCase keys the schema expects. A stored agent definition uses snake_case."""
    if not isinstance(raw, dict):
        return None
    names = {
        "id": "id",
        "prompt": "prompt",
        "items": "items",
        "output_schema": "outputSchema",
        "outputSchema": "outputSchema",
        "strategy": "strategy",
    }
    wired: dict[str, object] = {}
    for key, value in raw.items():
        name = names.get(str(key))
        if name is None or value is None:
            continue
        wired[name] = value
    return wired
