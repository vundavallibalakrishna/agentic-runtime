"""Fail when a built-in tool parameter has no description.

A model chooses and uses a tool from its schema alone (M39-T01), so every parameter
of every built-in tool carries a description, every array parameter carries an item
schema, and a closed set of values is an enum. This walks the seeded catalogue and
fails on the first gap, naming ``server.tool.parameter`` so it is fixed at the source
in ``tools/seed_tools.py``.

The connector catalogue is described in M39-T01a; until then its server is deferred,
and the deferred set is pinned here so nothing else can be added to it silently.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from ar_domain.chat.service import ChatService
from ar_domain.tools import seed_tools

if TYPE_CHECKING:
    from typing import Any

# Servers whose parameters are not yet described. Each must have a task that removes it.
DEFERRED_SERVERS = {"connectors"}  # M39-T01a


def _seed_catalogue() -> list[dict[str, Any]]:
    store = ChatService()
    seed_tools.seed(store, tenant=False)  # the built-in catalogue, no demo tenant or fixtures
    return list(store.tool_versions.values())


def _schema_gaps(prefix: str, schema: dict[str, Any]) -> list[str]:
    """Missing descriptions and item schemas under one object schema, depth first."""
    gaps: list[str] = []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return gaps
    for name, definition in properties.items():
        if not isinstance(definition, dict):
            gaps.append(f"{prefix}.{name}")
            continue
        where = f"{prefix}.{name}"
        if not str(definition.get("description") or "").strip():
            gaps.append(where)
        kind = definition.get("type")
        if kind == "array":
            items = definition.get("items")
            if not isinstance(items, dict):
                gaps.append(f"{where}[] (no item schema)")
            else:
                gaps.extend(_schema_gaps(f"{where}[]", items))
        elif kind == "object":
            gaps.extend(_schema_gaps(where, definition))
    return gaps


def main() -> None:
    tools = _seed_catalogue()
    servers = {
        str(tool.get("qualified_name") or tool.get("name")).split(".", 1)[0] for tool in tools
    }
    deferred_seen = servers & DEFERRED_SERVERS
    if deferred_seen != DEFERRED_SERVERS:
        missing = DEFERRED_SERVERS - deferred_seen
        print(
            f"deferred servers not in the catalogue: {', '.join(sorted(missing))}; "
            "update DEFERRED_SERVERS when a server is described or removed",
            file=sys.stderr,
        )
        raise SystemExit(1)

    gaps: list[str] = []
    checked = 0
    for tool in tools:
        qualified = str(tool.get("qualified_name") or tool.get("name"))
        if qualified.split(".", 1)[0] in DEFERRED_SERVERS:
            continue
        checked += 1
        schema = tool.get("input_schema")
        if isinstance(schema, dict):
            gaps.extend(_schema_gaps(qualified, schema))

    if gaps:
        print(
            f"{len(gaps)} tool parameters without a description or item schema:",
            file=sys.stderr,
        )
        for gap in sorted(gaps):
            print(f"  {gap}", file=sys.stderr)
        print(
            "\nAdd a description to each parameter in libs/ar_domain/src/ar_domain/tools/"
            "seed_tools.py (an enum for a closed set, an item schema for an array).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"{checked} built-in tools: every parameter is described")


if __name__ == "__main__":
    main()
