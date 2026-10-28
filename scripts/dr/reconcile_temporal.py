"""Terminate Temporal runs whose rows were not restored. Spec: docs/07-ops/backup-dr.md §2.1."""

from __future__ import annotations

import sys
from typing import cast

import orjson


def runs_to_terminate(restored_ids: set[str], temporal_ids: set[str]) -> list[str]:
    """Runs that exist in Temporal but not in the restored database."""
    return sorted(temporal_ids - restored_ids)


def main() -> None:
    """Read {restored, temporal} id lists from stdin."""
    payload = cast("dict[str, object]", orjson.loads(sys.stdin.buffer.read()))
    restored = {str(item) for item in cast("list[object]", payload.get("restored") or [])}
    temporal = {str(item) for item in cast("list[object]", payload.get("temporal") or [])}
    sys.stdout.write(
        orjson.dumps({"terminate": runs_to_terminate(restored, temporal)}).decode() + "\n"
    )


if __name__ == "__main__":
    main()
