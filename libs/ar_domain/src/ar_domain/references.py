"""Resolver registry for definition references. Spec: docs/03-specs/05-agent-registry.md §4."""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ReferenceIssue:
    """One validation finding. ``warning`` does not block publish."""

    loc: tuple[str | int, ...]
    msg: str
    type: str
    warning: bool = False


@dataclass
class ResolveContext:
    """What a resolver may look at. Later milestones register richer stores."""

    tenant_id: str
    alias_names: set[str] = field(default_factory=set)
    tool_servers: set[str] = field(default_factory=set)
    sandbox_templates: set[str] = field(default_factory=set)
    knowledge_collections: set[str] = field(default_factory=set)
    treat_unknown_as_warning: bool = False


Resolver = Callable[[ResolveContext, str, tuple[str | int, ...]], list[ReferenceIssue]]

RESOLVERS: dict[str, Resolver] = {}


def register_resolver(kind: str, resolver: Resolver) -> None:
    """Modules call this when their catalogue exists."""
    RESOLVERS[kind] = resolver


def resolve_reference(
    kind: str,
    ctx: ResolveContext,
    key: str,
    loc: tuple[str | int, ...],
) -> list[ReferenceIssue]:
    """Resolve one binding. An unregistered kind is ``unknown_reference``."""
    resolver = RESOLVERS.get(kind)
    if resolver is None:
        return [
            ReferenceIssue(
                loc,
                "feature not available",
                "unknown_reference",
                warning=ctx.treat_unknown_as_warning,
            )
        ]
    return resolver(ctx, key, loc)


def _model_alias(ctx: ResolveContext, key: str, loc: tuple[str | int, ...]) -> list[ReferenceIssue]:
    if key in ctx.alias_names:
        return []
    return [ReferenceIssue(loc, f"unknown model alias {key}", "unknown_reference")]


register_resolver("model_alias", _model_alias)
