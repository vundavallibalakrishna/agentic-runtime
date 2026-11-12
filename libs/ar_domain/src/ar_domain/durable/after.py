"""Work that must wait until the current request's changes are committed.

A request changes rows in its own unit and commits them when it ends. A step that makes
another process act on those rows, such as asking the tool gateway to run an approved
call, cannot run before that: the other process reads the database and would not see the
change. Such a step is registered here and runs right after the commit.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


def after_commit(store: Any, step: Callable[[], None]) -> None:
    """Run ``step`` once this unit's changes are committed.

    A store that is not a unit of the read model has nothing to commit and no other
    process reading behind it, so the step runs now.
    """
    waiting = getattr(store, "after_commit", None)
    if isinstance(waiting, list):
        waiting.append(step)
        return
    step()


def run_after_commit(unit: Any) -> None:
    """Run the steps a unit registered, in order. The caller commits what they change."""
    waiting = getattr(unit, "after_commit", None)
    while isinstance(waiting, list) and waiting:
        waiting.pop(0)()
