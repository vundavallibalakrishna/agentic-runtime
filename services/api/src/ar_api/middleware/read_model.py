"""Open one Postgres unit per authenticated request and commit it with the response."""

from starlette.types import ASGIApp, Receive, Scope, Send

from ar_domain.readmodel.model import RepositoryReadModel

_PROBE_PATHS = frozenset({"/healthz", "/readyz", "/metrics"})


class ReadModelMiddleware:
    """Repositories per request. A process-local double is left untouched."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or str(scope.get("path", "")) in _PROBE_PATHS:
            await self.app(scope, receive, send)
            return
        chat = scope["app"].state.chat
        if not isinstance(chat, RepositoryReadModel):
            await self.app(scope, receive, send)
            return
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        tenant_id = getattr(principal, "tenant_id", None)
        if tenant_id is None:
            await self.app(scope, receive, send)
            return
        user_id = str(getattr(principal, "id", "") or "")
        request_id = ""
        if isinstance(state, dict):
            raw = state.get("request_id")
            request_id = "" if raw is None else str(raw)
        async with chat.open(tenant_id, user_id=user_id, request_id=request_id) as unit:
            if isinstance(state, dict):
                state["read_unit"] = unit
            try:
                await self.app(scope, receive, send)
            finally:
                if isinstance(state, dict):
                    state["read_unit"] = None
