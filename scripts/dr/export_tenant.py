"""Export one tenant's rows in foreign-key order. Spec: docs/07-ops/backup-dr.md §2.3."""

from __future__ import annotations

import sys
from typing import cast

import orjson

# Parents before children. The scratch-cluster import uses this order.
TABLES = ("tenants", "users", "audit_events", "documents", "document_chunks")


def export_tenant(dataset: dict[str, object], tenant_id: str) -> dict[str, list[dict[str, object]]]:
    """Keep rows whose tenant_id matches. Tenant rows match on id."""
    exported: dict[str, list[dict[str, object]]] = {}
    tables = dataset.get("tables")
    if not isinstance(tables, dict):
        raise TypeError("dataset has no tables")
    for name in TABLES:
        raw = tables.get(name, [])
        if not isinstance(raw, list):
            continue
        kept: list[dict[str, object]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            item = cast("dict[str, object]", row)
            key = "id" if name == "tenants" else "tenant_id"
            if str(item.get(key)) == tenant_id:
                kept.append(item)
        exported[name] = kept
    return exported


def main() -> None:
    """Read JSON on stdin and write one tenant."""
    if len(sys.argv) != 2:
        raise SystemExit("usage: export_tenant.py <tenant-id>")
    dataset = cast("dict[str, object]", orjson.loads(sys.stdin.buffer.read()))
    sys.stdout.write(orjson.dumps(export_tenant(dataset, sys.argv[1])).decode() + "\n")


if __name__ == "__main__":
    main()
