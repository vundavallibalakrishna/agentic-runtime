"""Re-embed a tenant's memory facts after its embedding model changes.

Facts written by an earlier model are matched by words until this runs.
Spec: docs/03-specs/11-memory.md §6.

    uv run python scripts/reembed_memory.py --tenant acme
"""

import argparse
import asyncio

from ar_domain.chat.service import ChatService
from ar_domain.db.engine import app_database_url
from ar_domain.durable.bind import bind_store
from ar_domain.durable.flush import flush_store
from ar_domain.memory.vectors import reembed


async def run(tenant_slug: str) -> int:
    """Load the tenant from the database, embed its stale facts and save them."""
    store = ChatService(fake_models_allowed=False)
    binding = await bind_store(store, app_database_url(), tenant_slug=tenant_slug)
    if binding is None:
        raise SystemExit("The database did not answer.")
    try:
        count = reembed(store, binding.tenant_id)
        await flush_store(store)
    finally:
        if store.durable_engine is not None:
            await store.durable_engine.dispose()
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-embed memory facts for one tenant")
    parser.add_argument("--tenant", required=True, help="the tenant's slug")
    args = parser.parse_args()
    count = asyncio.run(run(args.tenant))
    print(f"tenant {args.tenant}: {count} facts embedded again")


if __name__ == "__main__":
    main()
