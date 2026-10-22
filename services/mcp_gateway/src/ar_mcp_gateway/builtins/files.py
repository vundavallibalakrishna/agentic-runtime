"""Forward file tools, including attach-to-sandbox."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_domain.sandboxes.runtime import run_tool
from ar_domain.tools.handlers import dispatch


def forward(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Run a files tool. Attachment copies go through the computer."""
    short = name.removeprefix("files.")
    if short == "attach_to_sandbox":
        return run_tool(store, short, arguments)
    return dispatch(store, "builtin://files", short, arguments, "")
