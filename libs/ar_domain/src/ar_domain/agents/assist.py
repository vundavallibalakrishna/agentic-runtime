"""Draft an agent definition from a sentence. Spec: docs/03-specs/05-agent-registry.md §3."""

import re
from dataclasses import dataclass
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
    lowered = description.lower()
    if "skill" in lowered or "brand guideline" in lowered:
        raw["skills"] = ["brand-guidelines"]
    if "subagent" in lowered or "delegate" in lowered:
        raw["subagents"] = {
            "allowed": ["researcher"],
            "allow_self_clone": False,
            "max_depth": 2,
            "max_parallel": 2,
        }
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


@dataclass(frozen=True, slots=True)
class Draft:
    """One proposal text and whether a real model produced it."""

    text: str
    real: bool


_BUILDER_SYSTEM = (
    "You turn a plain-language request into an agent definition for Agentic Runtime.\n"
    "Return one JSON object and nothing else, with these keys:\n"
    '- "persona": {"display_name": string of at most 80 characters, "greeting": one sentence}\n'
    '- "instructions": what the agent does, how it answers, and what it must not do\n'
    '- "starter_prompts": two to four short strings a person could click\n'
    '- "model": {"alias": "reasoning"}\n'
    '- "tools": a list of {"server": name, "version": "*", "include": ["*"]} using only the '
    "servers the task needs\n"
    "Available tool servers: {servers}.\n"
    "No markdown fences and no commentary."
)


async def draft_from_description(store: Any, actor: Actor, description: str) -> dict[str, object]:
    """Return a definition that validates.

    The reasoning model drafts first and repairs once from the validation errors.
    The deterministic proposal is the last resort, and the only path when no real
    model is connected. Raises 502 when nothing validates.
    """
    if len(description) > 4000:
        raise ArError(ErrorCode.VALIDATION_FAILED, "description is too long")
    texts = list(store.builder_scripts)
    store.builder_scripts.clear()
    from_model = False
    if not texts:
        drafted = await _complete(store, actor, description)
        from_model = drafted.real
        texts.append(drafted.text)
    scripted = orjson.dumps(scripted_definition(description)).decode()
    last_errors: list[dict[str, object]] = []
    attempt = 0
    while texts and attempt < 3:
        text = texts.pop(0)
        attempt += 1
        parsed = _loads(text)
        if parsed is None:
            last_errors = [{"msg": "model output was not JSON", "type": "validation_failed"}]
        else:
            try:
                definition, errors, warnings = _validate(actor, store, parsed)
            except ValidationError:
                definition, errors, warnings = None, [{"msg": "definition is invalid"}], []
            if definition is not None and not errors:
                return {
                    "definition": definition,
                    "rationale": (
                        "Drafted a persona, instructions and a tool slot from your description."
                        if text == scripted
                        else "Drafted with the reasoning model from your description."
                    ),
                    "warnings": warnings,
                }
            last_errors = errors or last_errors
        if texts or store.builder_strict:
            continue
        if from_model and attempt == 1:
            repaired = await _complete(store, actor, description, errors=last_errors, previous=text)
            texts.append(repaired.text)
        elif text != scripted:
            texts.append(scripted)
    raise ArError(ErrorCode.UPSTREAM_ERROR, "the model did not return a valid agent", errors=[])


async def _complete(
    store: Any,
    actor: Actor,
    description: str,
    *,
    errors: list[dict[str, object]] | None = None,
    previous: str = "",
) -> Draft:
    responder = getattr(store, "builder_responder", None)
    if responder is not None:
        return Draft(str(responder(description)), real=False)
    if store.builder_strict:
        return Draft("", real=False)
    completion = getattr(store, "_completion_call", None)
    if completion is None:
        return Draft(orjson.dumps(scripted_definition(description)).decode(), real=False)
    ensure_key = getattr(store, "_ensure_provider_key", None)
    if ensure_key is not None:
        await ensure_key(actor.tenant_id, "reasoning")
    model, headers, timeout_s, real = completion(actor.tenant_id, "reasoning")
    if not real:
        return Draft(orjson.dumps(scripted_definition(description)).decode(), real=False)
    return Draft(
        await _ask_model(
            store,
            actor,
            description,
            model=model,
            headers=headers,
            timeout_s=timeout_s,
            errors=errors,
            previous=previous,
        ),
        real=True,
    )


def _server_names(store: Any, actor: Actor) -> list[str]:
    rows = getattr(store, "tool_servers", {})
    names: list[str] = []
    if isinstance(rows, dict):
        for row in rows.values():
            if not isinstance(row, dict):
                continue
            owner = row.get("tenant_id")
            if owner not in (None, actor.tenant_id):
                continue
            name = str(row.get("slug") or row.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names or ["files"]


async def _ask_model(
    store: Any,
    actor: Actor,
    description: str,
    *,
    model: str,
    headers: dict[str, str],
    timeout_s: float,
    errors: list[dict[str, object]] | None,
    previous: str,
) -> str:
    """One chat completion against the tenant's reasoning model. Errors become text."""
    import httpx  # noqa: PLC0415

    system = _BUILDER_SYSTEM.replace("{servers}", ", ".join(_server_names(store, actor)))
    user = f"Create an agent that does this:\n{description.strip()}"
    if errors:
        user = (
            f"{user}\n\nYour previous answer failed validation:\n"
            f"{orjson.dumps(errors).decode()}\n\nPrevious answer:\n{previous[:4000]}\n\n"
            "Return the corrected JSON object only."
        )
    body: dict[str, object] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": 1200,
    }
    from ar_domain.models.options import apply_request_options  # noqa: PLC0415

    options_for = getattr(store, "request_options", None)
    options = options_for(actor.tenant_id, "reasoning") if callable(options_for) else {}
    apply_request_options(body, options)
    url = store._completion_url_for(actor.tenant_id, "reasoning", headers)
    try:
        async with httpx.AsyncClient(timeout=max(timeout_s, 30.0)) as client:
            response = await client.post(url, json=body, headers=headers)
    except httpx.HTTPError:
        return "The model provider did not answer."
    if response.status_code >= 300:
        return "The model provider returned an error."
    from ar_domain.models.logic import completion_text  # noqa: PLC0415

    return completion_text(response.json()) or ""
