"""Operator check for a Temporal schedule fire.

The automated proof is the time-skipping test
``test_schedule_fires_from_the_temporal_clock``. This script does not create a
schedule and does not call ``:tick``. When ``AR_TEMPORAL_ADDRESS`` is unset it
prints the checklist and exits 0. A private cluster fire is not claimed here.
"""

from __future__ import annotations

import asyncio
import os
import sys

from temporalio.client import Client


def main() -> int:
    address = os.environ.get("AR_TEMPORAL_ADDRESS", "").strip()
    print("M35 Temporal schedule checklist")
    print("1. Start Postgres, the API, the system worker and the runtime worker.")
    print("2. Point AR_TEMPORAL_ADDRESS at a Temporal frontend you control.")
    print("   The compose default host port is 7233 (AR_TEMPORAL_HOST_PORT).")
    print("3. Create a schedule with cron `*/1 * * * *` and leave it active.")
    print("4. Do not call POST /api/v1/routines/{id}:tick.")
    print("5. After the next minute, the routine has an event whose source is schedule.")
    print("6. If Temporal is down, :tick remains the in-process fallback.")
    if not address:
        print("AR_TEMPORAL_ADDRESS is unset. A private cluster fire was not observed.")
        return 0
    print(f"AR_TEMPORAL_ADDRESS is set ({_host(address)}). Listing schedules only.")
    namespace = os.environ.get("AR_TEMPORAL_NAMESPACE", "default")

    async def _list() -> int:
        client = await Client.connect(address, namespace=namespace)
        count = 0
        async for schedule in await client.list_schedules():
            if str(schedule.id).startswith("routine-"):
                count += 1
                print(f"schedule {schedule.id}")
        print(f"{count} routine schedules listed. This does not prove a fire.")
        return 0

    try:
        return asyncio.run(_list())
    except Exception as exc:  # noqa: BLE001 — the checklist must stay usable offline
        print(f"Temporal did not answer ({type(exc).__name__}). A fire was not observed.")
        return 0


def _host(address: str) -> str:
    return address.rsplit("@", maxsplit=1)[-1]


if __name__ == "__main__":
    sys.exit(main())
