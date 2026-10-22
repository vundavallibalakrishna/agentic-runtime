"""Bind the product cache to Postgres and flush it after each request."""

from starlette.types import ASGIApp, Receive, Scope, Send

from ar_common.host_ports import local_endpoint
from ar_common.logging import get_logger

_log = get_logger(__name__)


class DurableMiddleware:
    """One bind attempt, then a flush when the cache has a database."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            await _ensure(scope)
        await self.app(scope, receive, send)
        if scope["type"] != "http":
            return
        chat = scope["app"].state.chat
        if getattr(chat, "durable_engine", None) is None:
            return
        from ar_domain.durable.flush import flush_store  # noqa: PLC0415

        await flush_store(chat)


async def _ensure(scope: Scope) -> None:
    chat = scope["app"].state.chat
    if getattr(chat, "_bind_attempted", False):
        return
    chat._bind_attempted = True
    settings = scope["app"].state.settings
    chat.model_gateway_url = str(getattr(settings, "model_gateway_url", "") or "")
    from ar_domain.durable.bind import bind_store, should_bind  # noqa: PLC0415

    if not should_bind():
        return
    binding = await bind_store(chat, settings.database_url)
    if binding is None:
        return
    scope["app"].state.demo_tenant_id = binding.tenant_id
    admin = binding.users.get("admin@dev.local")
    if admin is not None:
        scope["app"].state.demo_user_id = admin
    await _attach_temporal(chat, settings)


async def _attach_temporal(chat: object, settings: object) -> None:
    configured = str(getattr(settings, "temporal_address", "") or "").strip()
    address = configured or local_endpoint(
        "AR_TEMPORAL_ADDRESS", "localhost:{port}", "AR_TEMPORAL_HOST_PORT"
    )
    try:
        import asyncio  # noqa: PLC0415

        from temporalio.client import Client  # noqa: PLC0415

        client = await asyncio.wait_for(Client.connect(address), timeout=0.5)
    except Exception as exc:  # noqa: BLE001 - turns stay in process when Temporal is down
        _log.info("temporal_unavailable", error=type(exc).__name__)
        return
    chat.temporal_client = client  # type: ignore[attr-defined]
    chat.temporal_up = True  # type: ignore[attr-defined]
