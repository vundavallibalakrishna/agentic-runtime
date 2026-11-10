"""Verify a tenant audit chain from Postgres or from a JSON file of chain rows.

    python -m ar_domain.audit.cli --file chain.json
    python -m ar_domain.audit.cli --tenant <uuid>

The database path reads ``audit_events`` through ``audit.service`` verification.
It does not read the process-local log. Exit status is 0 when the chain holds
and 1 when a row was tampered with.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

from ar_domain.audit.read import verify_public_chain

if TYPE_CHECKING:
    from typing import Any


def main(argv: list[str] | None = None) -> int:
    """Verify the chain and print the report as JSON."""
    parser = argparse.ArgumentParser(description="Verify the hash-chained audit log.")
    parser.add_argument("--file", help="JSON list of chain rows. Omit to read Postgres.")
    parser.add_argument("--tenant", help="Tenant UUID. Required when reading Postgres.")
    parser.add_argument("--from-seq", type=int, default=None)
    parser.add_argument("--to-seq", type=int, default=None)
    args = parser.parse_args(argv)
    if args.file:
        loaded = orjson.loads(Path(args.file).read_bytes())
        rows = [row for row in loaded if isinstance(row, dict)] if isinstance(loaded, list) else []
        report = verify_public_chain(rows, from_seq=args.from_seq, to_seq=args.to_seq)
    else:
        if not args.tenant:
            parser.error("--tenant is required when --file is omitted")
        report = asyncio.run(_verify_database(args.tenant, args.from_seq, args.to_seq))
    sys.stdout.write(orjson.dumps(report).decode() + "\n")
    return 0 if report["ok"] else 1


async def _verify_database(tenant: str, from_seq: int | None, to_seq: int | None) -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine  # noqa: PLC0415

    from ar_domain.audit.read import list_chain  # noqa: PLC0415
    from ar_domain.db.context import Principal, TenantContext  # noqa: PLC0415
    from ar_domain.db.engine import app_database_url  # noqa: PLC0415
    from ar_domain.db.session import tenant_session  # noqa: PLC0415

    tenant_id = uuid.UUID(tenant)
    principal = Principal(
        kind="system",
        id="audit-verify",
        tenant_id=tenant_id,
        auth_method="system",
    )
    ctx = TenantContext.from_principal(principal, "audit-verify")
    engine = create_async_engine(app_database_url(), pool_size=1, max_overflow=0)
    try:
        async with tenant_session(ctx, engine=engine) as session:
            rows = await list_chain(session, tenant_id)
    finally:
        await engine.dispose()
    return verify_public_chain(rows, from_seq=from_seq, to_seq=to_seq)


if __name__ == "__main__":
    raise SystemExit(main())
