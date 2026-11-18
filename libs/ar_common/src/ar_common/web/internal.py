"""Reject internal routes that do not carry the install HMAC."""

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from ar_common.errors import ArError, UnauthenticatedError
from ar_common.internal_auth import secret_value, verify_request
from ar_common.web.problems import problem_response

_OPEN = frozenset({"/healthz", "/readyz"})


def _request_id(scope: Scope) -> str:
    state = scope.get("state", {})
    if isinstance(state, dict):
        found = state.get("request_id")
        if isinstance(found, str):
            return found
    return ""


class InternalAuthMiddleware:
    """``/internal`` and ``/metrics`` require ``X-AR-Internal``. Health stays open."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        if path in _OPEN or not (path.startswith("/internal/") or path == "/metrics"):
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        secret = secret_value(getattr(request.app.state, "settings", None))
        try:
            verify_request(secret, request.method, path, request.headers.get("x-ar-internal"))
        except ArError as exc:
            response = problem_response(exc, instance=path, request_id=_request_id(scope))
            await response(scope, receive, send)
            return
        except Exception:  # noqa: BLE001 - a bad token is a refusal, not a 500
            response = problem_response(
                UnauthenticatedError(), instance=path, request_id=_request_id(scope)
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
