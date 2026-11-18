"""Transport headers. Spec: docs/06-security/authn-authz.md §7."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_HEADERS = ((b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),)
# An event stream is read as it is written. ``no-transform`` stops a proxy from compressing
# it, which holds every event back until the stream ends; ``x-accel-buffering`` says the
# same to nginx.
_STREAM_HEADERS = (
    (b"cache-control", b"no-cache, no-transform"),
    (b"x-accel-buffering", b"no"),
)


def _is_event_stream(headers: list[tuple[bytes, bytes]]) -> bool:
    return any(
        name.lower() == b"content-type" and value.lower().startswith(b"text/event-stream")
        for name, value in headers
    )


class SecurityHeadersMiddleware:
    """Add the baseline headers to every API response, and the stream ones to a stream."""

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
                path = str(scope.get("path") or "")
                if path == "/v1" or path.startswith("/v1/"):
                    headers.append((b"api-version", b"1"))
                if _is_event_stream(headers):
                    replaced = {name for name, _ in _STREAM_HEADERS}
                    headers = [pair for pair in headers if pair[0].lower() not in replaced]
                    headers.extend(_STREAM_HEADERS)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_headers)
