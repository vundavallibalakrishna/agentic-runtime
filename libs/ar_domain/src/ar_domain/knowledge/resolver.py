"""Resolve ``knowledge_collection`` references on an agent definition."""

from ar_domain.references import ReferenceIssue, ResolveContext, register_resolver


def _known(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    if key in ctx.knowledge_collections:
        return []
    return [
        ReferenceIssue(
            loc,
            f"unknown knowledge collection {key}",
            "unknown_reference",
            warning=ctx.treat_unknown_as_warning,
        )
    ]


register_resolver("knowledge_collection", _known)
