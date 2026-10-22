"""Forward memory tools through the policy pipeline."""

from typing import TYPE_CHECKING

from ar_domain.tools.handlers import dispatch

if TYPE_CHECKING:
    from typing import Any


def forward(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Run a memory tool. Policy has already decided."""
    return dispatch(store, "builtin://memory", name.removeprefix("memory."), arguments, "")
