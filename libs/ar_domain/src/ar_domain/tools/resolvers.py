"""Resolve ``tool`` and ``tool_server`` references on an agent definition."""

from ar_domain.references import ReferenceIssue, ResolveContext, register_resolver


def _known(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    if key in ctx.tool_servers:
        return []
    return [
        ReferenceIssue(
            loc,
            f"unknown tool server {key}",
            "unknown_reference",
            warning=ctx.treat_unknown_as_warning,
        )
    ]


register_resolver("tool", _known)
register_resolver("tool_server", _known)
