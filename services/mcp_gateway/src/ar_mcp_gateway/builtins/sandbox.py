"""Forward sandbox tools through the shared computer. Spec: docs/03-specs/12-sandbox-manager.md."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from ar_domain.sandboxes.runtime import run_tool


def forward(store: Any, name: str, arguments: dict[str, object]) -> dict[str, object]:
    """Run one ``sandbox.*`` tool. Policy has already decided."""
    return run_tool(store, name.removeprefix("sandbox."), arguments)
