"""Check a restored dataset. Spec: docs/07-ops/backup-dr.md."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import cast

import orjson

from ar_domain.audit.exports import verify_chain

RPO_LIMIT_S = 15 * 60
RTO_LIMIT_S = 4 * 60 * 60


def check_dataset(dataset: dict[str, object], *, elapsed_s: float = 0) -> dict[str, object]:
    """Return a report or raise ValueError when the restore is not acceptable."""
    rows = dataset.get("rows")
    if not isinstance(rows, dict) or not rows:
        raise ValueError("restored dataset has no row counts")
    audit = dataset.get("audit")
    if not isinstance(audit, list) or not verify_chain(
        [cast("dict[str, object]", row) for row in audit]
    ):
        raise ValueError("audit chain does not verify")
    rpo = int(cast("int", dataset.get("wal_archive_timeout_s") or 0))
    if rpo <= 0 or rpo > RPO_LIMIT_S:
        raise ValueError("WAL archive interval exceeds the 15 minute RPO")
    if elapsed_s > RTO_LIMIT_S:
        raise ValueError("restore exceeded the 4 hour RTO")
    return {
        "ok": True,
        "tables": len(rows),
        "rpoSeconds": rpo,
        "elapsedSeconds": elapsed_s,
        "vectors": "pgvector rows are inside the Postgres backup",
    }


def main(argv: list[str] | None = None) -> None:
    """Validate a dataset file and print the report."""
    args = argv if argv is not None else sys.argv[1:]
    path = Path(args[0] if args else "scripts/dr/fixtures/dataset.json")
    elapsed = float(args[1]) if len(args) > 1 else 0
    dataset = cast("dict[str, object]", orjson.loads(path.read_bytes()))
    report = check_dataset(dataset, elapsed_s=elapsed)
    sys.stdout.write(orjson.dumps(report).decode() + "\n")


if __name__ == "__main__":
    main()
