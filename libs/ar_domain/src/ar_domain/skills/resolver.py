"""Resolve ``skill`` and ``subagent`` references. Spec: docs/03-specs/14-skills.md §2."""

from ar_domain.references import ReferenceIssue, ResolveContext, register_resolver
from ar_domain.skills.logic import (
    chain_too_deep,
    constraint_matches,
    highest_match,
    platform_max_depth,
    reaches,
    split_skill_ref,
)


def _skill(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    slug, constraint = split_skill_ref(key)
    versions = ctx.skill_versions.get(slug, ())
    if slug not in ctx.published_skills and not versions:
        return [
            ReferenceIssue(
                loc,
                f"unknown skill {slug}",
                "unknown_reference",
                warning=ctx.treat_unknown_as_warning,
            )
        ]
    if constraint and highest_match(versions, constraint) is None:
        return [
            ReferenceIssue(
                loc,
                f"skill {slug} has no version matching {constraint}",
                "unknown_reference",
                warning=ctx.treat_unknown_as_warning,
            )
        ]
    if constraint and not any(constraint_matches(version, constraint) for version in versions):
        return [
            ReferenceIssue(
                loc,
                f"skill {slug} has no version matching {constraint}",
                "unknown_reference",
                warning=ctx.treat_unknown_as_warning,
            )
        ]
    return []


def _subagent(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    if key not in ctx.published_agents:
        return [
            ReferenceIssue(
                loc,
                f"unknown subagent {key}",
                "unknown_reference",
                warning=ctx.treat_unknown_as_warning,
            )
        ]
    if ctx.publishing_slug and key == ctx.publishing_slug:
        return [
            ReferenceIssue(
                loc,
                "an agent cannot list itself as a subagent",
                "validation_failed",
            )
        ]
    if ctx.publishing_slug and reaches(key, ctx.publishing_slug, ctx.subagent_edges):
        return [
            ReferenceIssue(
                loc,
                f"subagent cycle through {key}",
                "validation_failed",
            )
        ]
    return []


def depth_issue(
    ctx: ResolveContext, allowed: list[str], loc: tuple[str | int, ...]
) -> list[ReferenceIssue]:
    """Reject a chain that is deeper than the definition or the platform cap."""
    if not ctx.publishing_slug or not allowed:
        return []
    limit = min(ctx.subagent_max_depth, platform_max_depth())
    if chain_too_deep(ctx.publishing_slug, allowed, ctx.subagent_edges, limit):
        return [
            ReferenceIssue(
                loc,
                f"subagent chain is deeper than {limit}",
                "validation_failed",
            )
        ]
    return []


register_resolver("skill", _skill)
register_resolver("subagent", _subagent)
