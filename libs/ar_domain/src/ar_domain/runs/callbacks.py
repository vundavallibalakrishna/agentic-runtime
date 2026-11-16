"""Send a queued run callback through the egress client.

Delivery is scheduled off the request task. The body is signed with the
tenant run-callback secret when one is present. A memory double used by unit
tests keeps the queue and does not dial unless ``send_callbacks`` is set.
"""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import httpx
import orjson

from ar_common.egress_http import EgressDenied, current_allow, guard, sync_client
from ar_common.time import utcnow
from ar_domain.runs.logic import sign_run_callback

if TYPE_CHECKING:
    from typing import Any

_SECRET_NAME = "__run_callback_secret__"  # noqa: S105


def deliver_callback(store: Any, item: dict[str, object]) -> None:
    """Schedule one signed POST. The caller does not wait for the response."""
    allow = current_allow()
    secret = _secret(store)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(
            target=_send, args=(item, allow, secret), name="run-callback", daemon=True
        ).start()
        return
    task = loop.create_task(asyncio.to_thread(_send, item, allow, secret))
    tasks = getattr(store, "callback_tasks", None)
    if isinstance(tasks, list):
        tasks.append(task)


def _send(item: dict[str, object], allow: list[str], secret: str) -> None:
    url = str(item.get("url") or "")
    problem = guard(url, allow)
    if problem is not None:
        item["result"] = "denied"
        item["error"] = problem
        return
    body = orjson.dumps(
        {"runId": str(item.get("run_id") or ""), "status": str(item.get("status") or "")}
    )
    headers: dict[str, str] = {}
    if secret:
        headers["X-Signature"] = sign_run_callback(secret, body, int(utcnow().timestamp()))
    try:
        with sync_client(allow=allow, timeout=5.0) as client:
            response = client.post(url, content=body, headers=headers)
        item["result"] = "sent" if response.status_code < 300 else "failed"
    except (httpx.HTTPError, EgressDenied) as exc:
        item["result"] = "failed"
        item["error"] = type(exc).__name__


def _secret(store: Any) -> str:
    direct = getattr(store, "run_callback_secret", None)
    if isinstance(direct, str) and direct:
        return direct
    secrets = getattr(store, "secrets", None)
    if isinstance(secrets, dict):
        found = secrets.get(_SECRET_NAME)
        if isinstance(found, str):
            return found
        if isinstance(found, dict) and isinstance(found.get("value"), str):
            return str(found["value"])
    return ""
