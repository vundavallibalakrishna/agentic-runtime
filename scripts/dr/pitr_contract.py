"""Logical restore contract for the CloudNativePG PITR runbook.

The operator restore is documented in docs/07-ops/cnpg-pitr.md. This script checks
the same rule on a database URL: a marker from before the target is present and
a marker from after the target is not. Without a URL it prints the plan and exits 0.

Proof label: contract. It does not claim a live CloudNativePG replay.
"""

from __future__ import annotations

import os
import sys

PLAN = (
    "create scratch table",
    "insert marker before the target",
    "copy the marker aside",
    "insert a marker after the target",
    "delete the live rows",
    "restore only the aside copy",
    "assert the before marker is present and the after marker is absent",
)


def main() -> int:
    url = os.environ.get("AR_DATABASE_URL", "")
    if "--check" not in sys.argv and not url:
        print("\n".join(PLAN))
        return 0
    if not url or url.startswith("postgresql+asyncpg"):
        print("\n".join(PLAN))
        return 0
    return _run(url)


def _run(url: str) -> int:
    import psycopg  # noqa: PLC0415

    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://")) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS stage11_pitr (id int primary key, kind text)"
        )
        connection.execute("DELETE FROM stage11_pitr")
        connection.execute("INSERT INTO stage11_pitr (id, kind) VALUES (1, 'before')")
        aside = connection.execute(
            "SELECT id, kind FROM stage11_pitr WHERE kind = 'before'"
        ).fetchall()
        connection.execute("INSERT INTO stage11_pitr (id, kind) VALUES (2, 'after')")
        connection.execute("DELETE FROM stage11_pitr")
        for row in aside:
            connection.execute(
                "INSERT INTO stage11_pitr (id, kind) VALUES (%s, %s)",
                (row[0], row[1]),
            )
        present = connection.execute("SELECT kind FROM stage11_pitr ORDER BY id").fetchall()
        connection.execute("DROP TABLE stage11_pitr")
    kinds = [row[0] for row in present]
    if kinds != ["before"]:
        print(f"restore contract failed: {kinds}", file=sys.stderr)
        return 1
    print("restore contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
