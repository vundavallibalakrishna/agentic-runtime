"""Schema validation for an agent definition. Spec: definition-schema §2.1."""

from pydantic import ValidationError
from pydantic.alias_generators import to_camel

from ar_contracts.definitions import AgentDefinition
from ar_domain.agents.defaults import apply_definition_defaults
from ar_domain.references import ReferenceIssue, ResolveContext, resolve_reference
from ar_domain.skills.logic import highest_match, split_skill_ref
from ar_domain.skills.resolver import depth_issue


def _loc(parts: tuple[object, ...]) -> tuple[str | int, ...]:
    loc: list[str | int] = []
    for part in parts:
        if isinstance(part, int):
            loc.append(part)
        else:
            loc.append(to_camel(str(part)))
    return tuple(loc)


def schema_errors(raw: dict[str, object]) -> tuple[dict[str, object] | None, list[ReferenceIssue]]:
    """Validate structure. Returns the normalised definition, or errors."""
    try:
        model = AgentDefinition.model_validate(apply_definition_defaults(raw))
    except ValidationError as exc:
        issues = [
            ReferenceIssue(_loc(tuple(error["loc"])), str(error["msg"]), "validation_failed")
            for error in exc.errors()
        ]
        return None, issues
    dumped = model.model_dump(by_alias=False)
    prompt_issues: list[ReferenceIssue] = []
    prompts = dumped.get("starter_prompts")
    if isinstance(prompts, list):
        for index, prompt in enumerate(prompts):
            if isinstance(prompt, str) and len(prompt) > 200:
                prompt_issues.append(
                    ReferenceIssue(
                        ("starterPrompts", index),
                        "starter prompt is longer than 200 characters",
                        "validation_failed",
                    )
                )
    if prompt_issues:
        return None, prompt_issues
    return dumped, []


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def reference_issues(  # noqa: PLR0912
    definition: dict[str, object],
    ctx: ResolveContext,
) -> tuple[list[ReferenceIssue], dict[str, object]]:
    """Resolve bindings. Unknown kinds stay errors unless the context says otherwise."""
    issues: list[ReferenceIssue] = []
    model = definition.get("model")
    alias = ""
    if isinstance(model, dict) and isinstance(model.get("alias"), str):
        alias = model["alias"]
        issues.extend(resolve_reference("model_alias", ctx, alias, ("model", "alias")))
        fast = model.get("fast_alias")
        if isinstance(fast, str) and fast:
            issues.extend(resolve_reference("model_alias", ctx, fast, ("model", "fastAlias")))
        vision = model.get("vision_alias")
        if isinstance(vision, str) and vision:
            issues.extend(resolve_reference("model_alias", ctx, vision, ("model", "visionAlias")))
    tools = definition.get("tools")
    if isinstance(tools, list):
        for index, tool in enumerate(tools):
            server = tool.get("server") if isinstance(tool, dict) else None
            if isinstance(server, str):
                issues.extend(resolve_reference("tool", ctx, server, ("tools", index, "server")))
    for index, slug in enumerate(_strings(definition.get("skills"))):
        issues.extend(resolve_reference("skill", ctx, slug, ("skills", index)))
    knowledge = definition.get("knowledge")
    collections = knowledge.get("collections") if isinstance(knowledge, dict) else []
    for index, slug in enumerate(_strings(collections)):
        issues.extend(
            resolve_reference(
                "knowledge_collection", ctx, slug, ("knowledge", "collections", index)
            )
        )
    subagents = definition.get("subagents")
    allowed = subagents.get("allowed") if isinstance(subagents, dict) else []
    for index, slug in enumerate(_strings(allowed)):
        issues.extend(resolve_reference("subagent", ctx, slug, ("subagents", "allowed", index)))
    issues.extend(depth_issue(ctx, _strings(allowed), ("subagents", "maxDepth")))
    sandbox = definition.get("sandbox")
    if isinstance(sandbox, dict) and sandbox.get("enabled") is True:
        template = str(sandbox.get("template") or "default")
        issues.extend(resolve_reference("sandbox_template", ctx, template, ("sandbox", "template")))
    resolved_skills: list[dict[str, str]] = []
    for raw in _strings(definition.get("skills")):
        slug, constraint = split_skill_ref(raw)
        matched = highest_match(ctx.skill_versions.get(slug, ()), constraint or "*")
        version_id = ctx.skill_version_ids.get(slug, {}).get(matched or 0, "")
        if not version_id:
            version_id = ctx.published_skills.get(slug, "")
        if version_id:
            resolved_skills.append({"slug": slug, "skill_version_id": version_id})
    resolved: dict[str, object] = {
        "tools": [],
        "model": {"alias": alias},
        "skills": resolved_skills,
        "knowledge": [],
    }
    return issues, resolved


def split_issues(
    issues: list[ReferenceIssue],
) -> tuple[list[ReferenceIssue], list[ReferenceIssue]]:
    """Errors block publish. Warnings do not."""
    errors = [issue for issue in issues if not issue.warning]
    warnings = [issue for issue in issues if issue.warning]
    return errors, warnings
