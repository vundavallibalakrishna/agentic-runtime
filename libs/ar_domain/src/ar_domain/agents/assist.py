"""Draft an agent definition from a sentence. Spec: docs/03-specs/05-agent-registry.md §3."""

import re
from typing import TYPE_CHECKING, Any

import orjson
from pydantic import ValidationError

from ar_common.errors import ArError, ErrorCode
from ar_contracts.definitions import AgentDefinition
from ar_domain.agents.defaults import apply_definition_defaults
from ar_domain.agents.service import AgentLifecycle
from ar_domain.agents.validation import reference_issues, schema_errors, split_issues

if TYPE_CHECKING:
    from ar_domain.agents.access import Actor

_SLUG = re.compile(r"[^a-z0-9]+")


def slug_from(text: str) -> str:
    """A stable slug derived from the instruction."""
    lowered = _SLUG.sub("-", text.lower()).strip("-")
    lowered = re.sub(r"-{2,}", "-", lowered)
    if len(lowered) < 2:
        return "draft-agent"
    return lowered[:63]


def title_from(text: str) -> str:
    words = [word for word in re.split(r"\s+", text.strip()) if word][:8]
    title = " ".join(words).strip(" .")
    return (title[:80] or "New agent").capitalize() if title else "New agent"


def scripted_definition(description: str) -> dict[str, object]:
    """Deterministic proposal used when the model does not return JSON."""
    raw = apply_definition_defaults(
        {
            "persona": {
                "display_name": title_from(description)[:80],
                "greeting": "Tell me which report or gap you want reviewed.",
            },
            "instructions": description.strip()[:32_000] or "Help the user.",
            "starter_prompts": [
                "Review the latest report and list the gaps",
                "What evidence is still missing?",
            ],
            "model": {"alias": "reasoning", "fast_alias": "fast"},
            "tools": [{"server": "files", "version": "*", "include": ["*"]}],
        }
    )
    model = AgentDefinition.model_validate(raw)
    return model.model_dump(by_alias=True, mode="json")


def proposal_bundle(description: str, definition: dict[str, object]) -> dict[str, object]:
    """CamelCase bundle fragment. It is not published."""
    slug = slug_from(description)
    return {
        "apiVersion": "agentic-runtime.dev/v1",
        "kind": "Bundle",
        "metadata": {"name": slug},
        "resources": [
            {
                "kind": "Agent",
                "metadata": {"slug": slug, "name": title_from(description)},
                "spec": definition,
            }
        ],
    }


def _loads(text: str) -> dict[str, object] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        parsed = orjson.loads(text[start : end + 1])
    except orjson.JSONDecodeError:
        return None
    if isinstance(parsed, dict) and isinstance(parsed.get("resources"), list):
        resources = parsed["resources"]
        first = resources[0] if resources else None
        spec = first.get("spec") if isinstance(first, dict) else None
        if isinstance(spec, dict):
            return {str(key): value for key, value in spec.items()}
    return parsed if isinstance(parsed, dict) else None


def _validate(
    actor: Actor, store: Any, raw: dict[str, object]
) -> tuple[dict[str, object] | None, list[dict[str, object]], list[dict[str, object]]]:
    normalised, schema = schema_errors(raw)
    if normalised is None:
        return (
            None,
            [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in schema],
            [],
        )
    issues, _resolved = reference_issues(
        normalised, AgentLifecycle(store).context(actor, warnings=True)
    )
    errors, warnings = split_issues(issues)
    dumped = AgentDefinition.model_validate(normalised).model_dump(by_alias=True, mode="json")
    return (
        dumped,
        [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in errors],
        [{"loc": list(item.loc), "msg": item.msg, "type": item.type} for item in warnings],
    )


async def draft_from_description(store: Any, actor: Actor, description: str) -> dict[str, object]:
    """Return a definition that validates, or 502 after one repair attempt."""
    if len(description) > 4000:
        raise ArError(ErrorCode.VALIDATION_FAILED, "description is too long")
    texts = list(store.builder_scripts)
    store.builder_scripts.clear()
    if not texts:
        texts.append(await _complete(store, description))
    last_errors: list[dict[str, object]] = []
    for attempt, text in enumerate(texts[:2]):
        parsed = _loads(text)
        if parsed is None and not store.builder_strict and attempt == len(texts[:2]) - 1:
            parsed = scripted_definition(description)
        if parsed is None:
            last_errors = [{"msg": "model output was not JSON", "type": "validation_failed"}]
            if len(texts) == 1 and not store.builder_strict:
                texts.append(orjson.dumps(scripted_definition(description)).decode())
            continue
        try:
            definition, errors, warnings = _validate(actor, store, parsed)
        except ValidationError:
            definition, errors, warnings = None, [{"msg": "definition is invalid"}], []
        if definition is not None and not errors:
            return {
                "definition": definition,
                "rationale": (
                    "Drafted a persona, instructions and a tool slot from your description."
                ),
                "warnings": warnings,
            }
        last_errors = errors or last_errors
    raise ArError(ErrorCode.UPSTREAM_ERROR, "the model did not return a valid agent", errors=[])


async def _complete(store: Any, description: str) -> str:
    responder = getattr(store, "builder_responder", None)
    if responder is not None:
        return str(responder(description))
    if store.builder_strict:
        return ""
    return orjson.dumps(scripted_definition(description)).decode()
