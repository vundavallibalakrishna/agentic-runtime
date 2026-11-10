"""Readiness checks for the API process.

``/healthz`` stays a liveness probe and does not connect. ``/readyz`` checks
Postgres, Valkey when sessions and the limiter are shared, and Temporal when
``AR_TEMPORAL_REQUIRED`` is set. A check is cached for ten seconds.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING

from ar_common.settings import BaseServiceSettings, uses_shared_process_state

if TYPE_CHECKING:
    from ar_common.web.health import ReadinessCheck

_TTL_S = 10.0
Ping = Callable[[], Awaitable[None]]


def readiness_names(*, shared: bool, temporal_required: bool) -> list[str]:
    """Check names ``/readyz`` reports, in a stable order."""
    names = ["postgres"]
    if shared:
        names.append("valkey")
    if temporal_required:
        names.append("temporal")
    return names


def api_readiness(settings: BaseServiceSettings) -> dict[str, ReadinessCheck]:
    """The checks this process installs."""
    shared = uses_shared_process_state(settings.env)
    checks: dict[str, ReadinessCheck] = {
        "postgres": _cached(lambda: ping_postgres(settings.database_url)),
    }
    if shared:
        checks["valkey"] = _cached(lambda: ping_valkey(settings.valkey_url))
    if settings.temporal_required:
        checks["temporal"] = _cached(
            lambda: ping_temporal(settings.temporal_address, settings.temporal_namespace)
        )
    return checks


def _cached(ping: Ping) -> ReadinessCheck:
    checked_at = 0.0
    failed: BaseException | None = None
    ok = False

    async def run() -> None:
        nonlocal checked_at, failed, ok
        now = time.monotonic()
        if now - checked_at < _TTL_S and (ok or failed is not None):
            if failed is not None:
                raise failed
            return
        try:
            await ping()
        except Exception as exc:
            failed = exc
            ok = False
            checked_at = now
            raise
        failed = None
        ok = True
        checked_at = now

    return run


async def ping_postgres(url: str) -> None:
    """``SELECT 1`` on the application database."""
    from sqlalchemy import text  # noqa: PLC0415

    from ar_domain.db.engine import get_engine  # noqa: PLC0415

    engine = get_engine(url)
    async with asyncio.timeout(2):
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))


async def ping_valkey(url: str) -> None:
    """``PING`` the shared Valkey."""
    from redis.asyncio import Redis  # noqa: PLC0415

    client = Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
    try:
        if await client.ping() is not True:
            raise RuntimeError("valkey did not answer")
    finally:
        await client.aclose()


async def ping_temporal(address: str, namespace: str) -> None:
    """Temporal health. An empty address is not ready."""
    from temporalio.client import Client  # noqa: PLC0415

    target = address.strip()
    if not target:
        raise RuntimeError("temporal address is empty")
    client = await asyncio.wait_for(
        Client.connect(target, namespace=namespace.strip() or "default"),
        timeout=2,
    )
    serving = await client.service_client.check_health(
        timeout=timedelta(seconds=2),
        retry=False,
    )
    if not serving:
        raise RuntimeError("temporal is not serving")
