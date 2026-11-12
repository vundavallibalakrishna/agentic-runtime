"""Tools that work only once the tenant has set something up.

A model describes what it can do from the tools it is offered. A tool that would only
answer "not configured" is not offered, so the model does not promise it. A person who
calls the tool directly, from the tool console, still gets the refusal that says what to
set.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.tools.searching import search_configured

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

# Qualified tool name to the check that says the tenant has made it usable.
_NEEDS: dict[str, Callable[[Any, object], bool]] = {
    "general.search": search_configured,
}


def ready_for(store: Any, tenant_id: object, qualified_name: str) -> bool:
    """Whether the tool can do its work for this tenant as it is set up now."""
    check = _NEEDS.get(qualified_name)
    return True if check is None else check(store, tenant_id)
