"""Tools that work only once the tenant has set something up.

A model describes what it can do from the tools it is offered. A tool that would only
answer "not configured" is not offered, so the model does not promise it. A person who
calls the tool directly, from the tool console, still gets the refusal that says what to
set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.documents.vision import vision_ready
from ar_domain.tools.searching import search_configured

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


def _search(store: Any, tenant_id: object, definition: dict[str, object]) -> bool:
    del definition
    return search_configured(store, tenant_id)


def _vision(store: Any, tenant_id: object, definition: dict[str, object]) -> bool:
    """The agent's own vision alias when it names one, otherwise the tenant's ``vision``."""
    model = definition.get("model")
    named = model.get("vision_alias") or model.get("visionAlias") if isinstance(model, dict) else ""
    return vision_ready(store, tenant_id, str(named or "vision"))


# Qualified tool name to the check that says the tenant has made it usable.
_NEEDS: dict[str, Callable[[Any, object, dict[str, object]], bool]] = {
    "general.search": _search,
    "image.ask": _vision,
}


def ready_for(
    store: Any,
    tenant_id: object,
    qualified_name: str,
    definition: dict[str, object] | None = None,
) -> bool:
    """Whether the tool can do its work for this tenant, and this agent, as set up now."""
    check = _NEEDS.get(qualified_name)
    return True if check is None else check(store, tenant_id, definition or {})
