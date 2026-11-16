"""Send a queued run callback through the egress client.

The chat service records the callback and, on a repository-backed request,
posts it. A memory double used by unit tests keeps the queue and does not dial.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from typing import Any

from ar_common.egress_http import guard, sync_client


def deliver_callback(store: Any, item: dict[str, object]) -> None:
    """POST one queued callback. A refused host is recorded and not dialled."""
    del store
    url = str(item.get("url") or "")
    problem = guard(url)
    if problem is not None:
        item["result"] = "denied"
        item["error"] = problem
        return
    body = {
        "runId": item.get("run_id"),
        "status": item.get("status"),
    }
    try:
        with sync_client(timeout=5.0) as client:
            response = client.post(url, json=body)
        item["result"] = "sent" if response.status_code < 300 else "failed"
    except httpx.HTTPError as exc:
        item["result"] = "failed"
        item["error"] = type(exc).__name__
