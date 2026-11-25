"""Deliver one webhook. Signing is ``sign_body``. Backoff is the shared schedule.

A Temporal workflow on the system worker calls :func:`attempt`. A process with
no Temporal client calls it directly, so a delivery is not stuck waiting for a
worker that is not running.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import httpx

from ar_common.egress_http import EgressDenied, current_allow, guard, sync_client
from ar_common.time import utcnow
from ar_domain.durable.after import run_off_request
from ar_domain.events.sign import next_backoff_s, public_json_bytes, sign_body
from ar_domain.webhooks.book import WebhookBook, event_body

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
    topic, payload = event_body(store, row)
    body = public_json_bytes(
        {
            "id": str(row.get("outbox_event_id") or ""),
            "topic": topic,
            "tenant_id": str(tenant_id),
            "occurred_at": utcnow().isoformat(),
            "payload": payload,
        }
    )
    problem = guard(url, current_allow())
    if problem is not None:
        return _fail(row, problem, dead=True)
    stamp = int(utcnow().timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": _AGENT,
        _EVENT: str(row.get("outbox_event_id") or ""),
        _TOPIC: topic,
    }
    if secret:
        headers[_HEADER] = sign_body(secret, body, stamp)
    try:
        with sync_client(allow=current_allow(), timeout=_TIMEOUT_S) as client:
            response = client.post(url, content=body, headers=headers)
    except EgressDenied as exc:
        return _fail(row, exc.reason or type(exc).__name__, dead=True)
    except httpx.HTTPError as exc:
        return _schedule(row, None, type(exc).__name__)
    code = int(response.status_code)
    if 200 <= code < 300:
        row["status"] = "succeeded"
        row["last_status_code"] = code
        row["last_error"] = None
        row["attempts"] = _count(row.get("attempts")) + 1
        row["updated_at"] = utcnow()
        return {"status": "succeeded", "status_code": code}
    if code == 410:
        hook["status"] = "disabled"
        return _fail(row, "the receiver asked to stop", dead=True, code=code)
    return _schedule(row, code, f"the receiver answered {code}")


def _schedule(row: dict[str, object], code: int | None, error: str) -> dict[str, object]:
    attempts = _count(row.get("attempts")) + 1
    row["attempts"] = attempts
    row["last_status_code"] = code
    row["last_error"] = error[:500]
    row["updated_at"] = utcnow()
    wait = next_backoff_s(attempts - 1)
    if wait is None:
        row["status"] = "dead"
        return {"status": "dead", "error": error}
    row["status"] = "failed"
    row["next_attempt_at"] = utcnow() + timedelta(seconds=wait)
    return {"status": "failed", "retry_in_s": wait, "error": error}


def _count(value: object) -> int:
    return value if isinstance(value, int) else 0


def _fail(
    row: dict[str, object], error: str, *, dead: bool, code: int | None = None
) -> dict[str, object]:
    row["status"] = "dead" if dead else "failed"
    row["last_error"] = error
    row["last_status_code"] = code
    row["attempts"] = _count(row.get("attempts")) + 1
    row["updated_at"] = utcnow()
    return {"status": row["status"], "error": error}


def sweep_due(store: Any) -> int:
    """Retry deliveries that are due. A connected Temporal client owns the retries."""
    if getattr(store, "temporal_client", None) is not None:
        return 0
    now = utcnow()
    bucket = getattr(store, "webhook_deliveries", {})
    if not isinstance(bucket, dict):
        return 0
    count = 0
    for row in list(bucket.values()):
        if not isinstance(row, dict) or row.get("status") not in {"pending", "failed"}:
            continue
        due = row.get("next_attempt_at")
        if isinstance(due, datetime) and due > now:
            continue
        delivery_id = row.get("id")
        if isinstance(delivery_id, uuid.UUID):
            attempt(store, delivery_id)
            count += 1
    return count


async def sweep_due_deliveries(store: Any) -> int:
    """The system worker's sweep. Postgres is read when this process has no rows of its own."""
    if getattr(store, "temporal_client", None) is not None:
        return 0
    from ar_domain.readmodel.model import RepositoryReadModel  # noqa: PLC0415

    if isinstance(store, RepositoryReadModel):
        return await _sweep_postgres(store)
    return sweep_due(store)


async def _sweep_postgres(store: Any) -> int:
    from sqlalchemy import text  # noqa: PLC0415

    from ar_domain.db.session import platform_session  # noqa: PLC0415

    try:
        async with platform_session("webhook delivery sweep") as session:
            found = (
                await session.execute(
                    text(
                        "SELECT id, tenant_id FROM webhook_deliveries "
                        "WHERE status IN ('pending', 'failed') "
                        "AND (next_attempt_at IS NULL OR next_attempt_at <= now()) "
                        "LIMIT 50"
                    )
                )
            ).all()
    except Exception:  # noqa: BLE001 — no platform database means there is nothing to sweep
        return 0
    count = 0
    for delivery_id, tenant_id in found:
        if not isinstance(delivery_id, uuid.UUID) or not isinstance(tenant_id, uuid.UUID):
            continue
        async with store.open(tenant_id) as unit:
            attempt(unit, delivery_id)
            count += 1
    return count


def _start_or_attempt(store: Any, delivery_id: uuid.UUID) -> None:
    client = getattr(store, "temporal_client", None)
    start = getattr(client, "start_workflow", None)
    if not callable(start):
        run_off_request(store, lambda: attempt(store, delivery_id))
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # A test or a script has no request loop. Deliver here so the result is visible.
        attempt(store, delivery_id)
        return
    tenant_id = _tenant_of(store, delivery_id)

    def _go() -> None:
        _spawn(store, start, delivery_id, tenant_id)

    if getattr(store, "durable_engine", None) is not None:
        waiting = getattr(store, "after_commit", None)
        if not isinstance(waiting, list):
            waiting = []
            store.after_commit = waiting
        waiting.append(_go)
        return
    _go()


def _tenant_of(store: Any, delivery_id: uuid.UUID) -> str:
    row = WebhookBook(store).get_delivery(delivery_id)
    tenant_id = row.get("tenant_id") if isinstance(row, dict) else None
    return str(tenant_id or "")


def _spawn(store: Any, start: Any, delivery_id: uuid.UUID, tenant_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_start(start, delivery_id, tenant_id))
        return
    tasks = getattr(store, "webhook_tasks", None)
    if not isinstance(tasks, list):
        tasks = []
        store.webhook_tasks = tasks
    tasks.append(loop.create_task(_start(start, delivery_id, tenant_id)))


async def _start(start: Any, delivery_id: uuid.UUID, tenant_id: str) -> None:
    try:
        await start(
            "WebhookDeliveryWorkflow",
            {"delivery_id": str(delivery_id), "tenant_id": tenant_id},
            id=f"whd-{delivery_id}",
            task_queue="ar-system",
        )
    except Exception:  # noqa: BLE001 — the row stays pending for a later sweep
        return
