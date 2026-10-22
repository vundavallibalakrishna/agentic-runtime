"""Resolve ``sandbox_template`` references on an agent definition."""

from ar_domain.references import ReferenceIssue, ResolveContext, register_resolver


def _known(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    if key in ctx.sandbox_templates:
        return []
    return [
        ReferenceIssue(
            loc,
            f"unknown sandbox template {key}",
            "unknown_reference",
            warning=ctx.treat_unknown_as_warning,
        )
    ]


register_resolver("sandbox_template", _known)
