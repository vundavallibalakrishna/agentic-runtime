"""Deliver one webhook. Signing is ``sign_body``. Backoff is the shared schedule.

A Temporal workflow on the system worker calls :func:`attempt`. A process with
no Temporal client calls it directly, so a delivery is not stuck waiting for a
worker that is not running.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import httpx

from ar_common.egress_http import EgressDenied, current_allow, guard, sync_client
from ar_common.time import utcnow
from ar_domain.events.sign import next_backoff_s, public_json_bytes, sign_body
from ar_domain.webhooks.book import WebhookBook

if TYPE_CHECKING:
    from typing import Any

_TIMEOUT_S = 10.0
_HEADER = "X-AR-Signature"
_EVENT = "X-AR-Event-Id"
_TOPIC = "X-AR-Topic"
_AGENT = "agentic-runtime-webhooks/1"


def dispatch_public_event(
    store: Any, tenant_id: object, topic: str, payload: dict[str, object]
) -> int:
    """Enqueue and attempt delivery for one public event. Returns how many were queued."""
    if not isinstance(tenant_id, uuid.UUID):
        try:
            tenant_id = uuid.UUID(str(tenant_id))
        except ValueError:
            return 0
    book = WebhookBook(store)
    made = book.enqueue(tenant_id, topic, payload)
    for row in made:
        delivery_id = row.get("id")
        if isinstance(delivery_id, uuid.UUID):
            _start_or_attempt(store, delivery_id)
    return len(made)


def attempt(store: Any, delivery_id: uuid.UUID) -> dict[str, object]:  # noqa: PLR0911
    """One POST. A 2xx succeeds. Anything else waits out the backoff, then dies."""
    book = WebhookBook(store)
    row = book.get_delivery(delivery_id)
    if row is None:
        return {"status": "missing"}
    if row.get("status") in {"succeeded", "dead"}:
        return {"status": str(row.get("status"))}
    webhook_id = row.get("webhook_id")
    tenant_id = row.get("tenant_id")
    hooks = getattr(store, "outbound_webhooks", {})
    hook = hooks.get(webhook_id) if isinstance(hooks, dict) else None
    if not isinstance(hook, dict) or not isinstance(tenant_id, uuid.UUID):
        return _fail(row, "the subscription is gone", dead=True)
    url = str(hook.get("url") or "")
    secret = book.secret(tenant_id, webhook_id) if isinstance(webhook_id, uuid.UUID) else ""
    body = public_json_bytes(
        {
            "id": str(row.get("outbox_event_id") or ""),
            "topic": str(row.get("topic") or ""),
            "tenant_id": str(tenant_id),
            "occurred_at": utcnow().isoformat(),
            "payload": row.get("payload") if isinstance(row.get("payload"), dict) else {},
        }
    )
    problem = guard(url, current_allow())
    if problem is not None:
        return _schedule(row, None, problem)
    stamp = int(utcnow().timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _AGENT,
        _EVENT: str(row.get("outbox_event_id") or ""),
        _TOPIC: str(row.get("topic") or ""),
    }
    if secret:
        headers[_HEADER] = sign_body(secret, body, stamp)
    try:
        with sync_client(allow=current_allow(), timeout=_TIMEOUT_S) as client:
            response = client.post(url, content=body, headers=headers)
    except (httpx.HTTPError, EgressDenied) as exc:
        return _schedule(row, None, type(exc).__name__)
    code = int(response.status_code)
    if 200 <= code < 300:
        row["status"] = "succeeded"
        row["last_status_code"] = code
        row["last_error"] = None
        row["attempts"] = int(row.get("attempts") or 0) + 1
        row["updated_at"] = utcnow()
        return {"status": "succeeded", "status_code": code}
    if code == 410:
        hook["status"] = "disabled"
        return _fail(row, "the receiver asked to stop", dead=True, code=code)
    return _schedule(row, code, f"the receiver answered {code}")


def _schedule(row: dict[str, object], code: int | None, error: str) -> dict[str, object]:
    attempts = int(row.get("attempts") or 0) + 1
    row["attempts"] = attempts
    row["last_status_code"] = code
    row["last_error"] = error[:500]
    row["updated_at"] = utcnow()
    wait = next_backoff_s(attempts - 1)
    if wait is None:
        row["status"] = "dead"
        return {"status": "dead", "error": error}
    row["status"] = "failed"
    row["next_attempt_at"] = utcnow()
    return {"status": "failed", "retry_in_s": wait, "error": error}


def _fail(
    row: dict[str, object], error: str, *, dead: bool, code: int | None = None
) -> dict[str, object]:
    row["status"] = "dead" if dead else "failed"
    row["last_error"] = error
    row["last_status_code"] = code
    row["attempts"] = int(row.get("attempts") or 0) + 1
    row["updated_at"] = utcnow()
    return {"status": row["status"], "error": error}


def _start_or_attempt(store: Any, delivery_id: uuid.UUID) -> None:
    client = getattr(store, "temporal_client", None)
    start = getattr(client, "start_workflow", None)
    if not callable(start):
        attempt(store, delivery_id)
        return
    try:
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_running_loop()
    except RuntimeError:
        attempt(store, delivery_id)
        return
    tasks = getattr(store, "webhook_tasks", None)
    if not isinstance(tasks, list):
        tasks = []
        store.webhook_tasks = tasks
    tasks.append(loop.create_task(_start(start, delivery_id)))


async def _start(start: Any, delivery_id: uuid.UUID) -> None:
    try:
        await start(
            "WebhookDeliveryWorkflow",
            {"delivery_id": str(delivery_id)},
            id=f"whd-{delivery_id}",
            task_queue="ar-system",
        )
    except Exception:  # noqa: BLE001 — the row stays pending for a later sweep
        return
