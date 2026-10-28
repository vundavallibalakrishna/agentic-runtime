"""Transport headers. Spec: docs/06-security/authn-authz.md §7."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HEADERS = ((b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),)


class SecurityHeadersMiddleware:
    """Add the baseline security headers to every API response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(_HEADERS)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_headers)
