"""Run triggers shared by the model, the migration and the writers.

Adding a value here is not enough for a database that already migrated: ship a
new revision that replaces ``ck_runs_trigger``. A fresh database applies the
current list from that revision, so the model and the schema cannot drift.
"""

from __future__ import annotations

RUN_TRIGGERS: tuple[str, ...] = (
    "chat",
    "api",
    "channel",
    "routine",
    "subagent",
    "eval",
    "research",
)

_PREVIOUS_TRIGGERS: tuple[str, ...] = (
    "chat",
    "api",
    "channel",
    "routine",
    "subagent",
    "eval",
)


def trigger_check_sql(triggers: tuple[str, ...] = RUN_TRIGGERS) -> str:
    """The ``runs.trigger`` check expression."""
    quoted = ", ".join(f"'{item}'" for item in triggers)
    return f"trigger IN ({quoted})"


def previous_trigger_check_sql() -> str:
    """The check that revision 0009 installed, used by the downgrade."""
    return trigger_check_sql(_PREVIOUS_TRIGGERS)
