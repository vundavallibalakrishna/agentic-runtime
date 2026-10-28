"""Bind the product cache to Postgres and flush it after each request."""

import asyncio

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger
from ar_common.settings import EnvName

_log = get_logger(__name__)
_PROBE_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})


class DurableMiddleware:
    """One bind attempt, then a flush when the cache has a database."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        await _ensure(scope)
        chat = scope["app"].state.chat
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        flushed = False

        async def committed_send(message: Message) -> None:
            nonlocal flushed
            if message["type"] == "http.response.start":
                await flush_store(chat)
                flushed = True
            await send(message)

        await self.app(scope, receive, committed_send)
        if not flushed and getattr(chat, "durable_engine", None) is not None:
            await flush_store(chat)


async def _ensure(scope: Scope) -> None:
    if str(scope.get("path", "")) in _PROBE_PATHS:
        return
    chat = scope["app"].state.chat
    if getattr(chat, "_bind_attempted", False):
        return
    lock = getattr(chat, "_bind_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        chat._bind_lock = lock
    async with lock:
        if not getattr(chat, "_bind_attempted", False):
            finished = await _bind_once(scope)
            if finished:
                chat._bind_attempted = True


async def _bind_once(scope: Scope) -> bool:
    """Return True when this attempt is final. A missing schema retries later."""
    chat = scope["app"].state.chat
    settings = scope["app"].state.settings
    chat.model_gateway_url = str(getattr(settings, "model_gateway_url", "") or "")
    from ar_domain.durable.bind import SchemaNotReadyError, bind_store, should_bind  # noqa: PLC0415

    if not should_bind():
        return True
    try:
        binding = await bind_store(chat, settings.database_url)
    except SchemaNotReadyError:
        # Compose starts the API before `migrate`. Health stays up; the next
        # request tries again once `tenants` exists.
        _log.info("durable_schema_not_ready")
        return False
    if binding is None:
        # Postgres is optional for unit tests, Playwright and a laptop without Docker.
        # The memory cache stays (OQ-31). A live database still binds above.
        _log.info("durable_memory", reason="database_unavailable")
        if getattr(settings, "env", None) in {EnvName.DEV, EnvName.CI} and hasattr(
            chat, "seed_showcase"
        ):
            chat.seed_showcase()
        return True
    scope["app"].state.demo_tenant_id = binding.tenant_id
    admin = binding.users.get("admin@dev.local")
    if admin is not None:
        scope["app"].state.demo_user_id = admin
        if hasattr(chat, "eval_suites"):
            from ar_domain.agents.access import Actor  # noqa: PLC0415
            from ar_domain.evals.book import EvalBook  # noqa: PLC0415
            from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

            EvalBook(chat).ensure_platform(
                Actor(tenant_id=binding.tenant_id, user_id=admin, permissions=PERMISSION_KEYS)
            )
    await _attach_temporal(chat, settings)
    from ar_api.plugins import attach_packs  # noqa: PLC0415

    attach_packs(scope["app"])
    return True


async def _attach_temporal(chat: object, settings: object) -> None:
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    address = configured or local_endpoint(
        "AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT"
    )
    try:
        from temporalio.client import Client  # noqa: PLC0415

        client = await asyncio.wait_for(
            Client.connect(
                address, namespace=str(getattr(settings, "temporal_namespace", "") or "default")
            ),
            timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 - turns stay in process when Temporal is down
        _log.info("temporal_unavailable", error=type(exc).__name__)
        return
    chat.temporal_client = client  # type: ignore[attr-defined]
    chat.temporal_up = True  # type: ignore[attr-defined]
