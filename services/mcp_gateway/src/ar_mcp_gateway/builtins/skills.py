"""Forward skill tools through the policy pipeline."""

from typing import TYPE_CHECKING

from ar_domain.tools.handlers import dispatch

if TYPE_CHECKING:
    from typing import Any


def forward(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Run a skills tool. Policy has already decided."""
    return dispatch(store, "builtin://skills", name.removeprefix("skills."), arguments, "")
