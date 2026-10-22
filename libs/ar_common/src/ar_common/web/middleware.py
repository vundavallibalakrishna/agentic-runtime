"""Request-id, body-size and access-log middleware."""

import time
from typing import TYPE_CHECKING
from uuid import UUID

import orjson
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ar_common.errors import PayloadTooLargeError
from ar_common.ids import new_id
from ar_common.json_api import camelize
from ar_common.logging import get_logger
from ar_common.metrics import REQUESTS
from ar_common.web.problems import problem_response

if TYPE_CHECKING:
    from ar_common.settings import BaseServiceSettings

_log = get_logger(__name__)


class RequestIdMiddleware:
    """Echo ``X-Request-Id`` or generate one, and write an access log line."""

    def __init__(self, app: ASGIApp, service_name: str) -> None:
        self.app = app
        self.service_name = service_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = _header(scope, b"x-request-id") or f"req_{new_id()}"
        scope.setdefault("state", {})
        scope["state"]["request_id"] = request_id
        status = 500
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            REQUESTS.labels(service=self.service_name, status=str(status)).inc()
            _log.info(
                "http_access",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                request_id=request_id,
            )


class BodyLimitMiddleware:
    """Reject JSON bodies larger than ``AR_MAX_JSON_BODY_BYTES``."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        content_length = _header(scope, b"content-length")
        if content_length is not None and int(content_length) > self.max_bytes:
            response = problem_response(
                PayloadTooLargeError(),
                instance=str(scope.get("path", "")),
                request_id=_state_request_id(scope),
            )
            await response(scope, receive, send)
            return
        received = 0

        async def limited(message: Message) -> Message:
            nonlocal received
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise PayloadTooLargeError
            return message

        async def receive_limited() -> Message:
            return await limited(await receive())

        await self.app(scope, receive_limited, send)


class SecurityHeadersMiddleware:
    """API response headers from spec 01 §4. Applied to every service."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    (
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"strict-origin-when-cross-origin"),
                        (b"cross-origin-resource-policy", b"same-origin"),
                        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'"),
                        (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),
                    )
                )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_headers)


class CamelJsonMiddleware:
    """Rewrite JSON object keys to camelCase before the body reaches the client.

    Runs outside the service stack so problem documents, pagination envelopes
    and hand-built dict responses share one wire format. A second pass is safe.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        if path.startswith("/api/v1/openai/"):
            await self.app(scope, receive, send)
            return
        start: Message | None = None
        chunks: list[bytes] = []

        async def send_camel(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                if _json_content(message):
                    start = message
                    return
                await send(message)
                return
            if message["type"] == "http.response.body" and start is not None:
                chunks.append(bytes(message.get("body", b"")))
                if message.get("more_body"):
                    return
                rewritten = _camel_body(b"".join(chunks))
                headers = [
                    (key, value)
                    for key, value in list(start.get("headers", []))
                    if key.lower() != b"content-length"
                ]
                headers.append((b"content-length", str(len(rewritten)).encode()))
                start["headers"] = headers
                await send(start)
                await send({"type": "http.response.body", "body": rewritten})
                return
            await send(message)

        await self.app(scope, receive, send_camel)


def _json_content(message: Message) -> bool:
    for key, value in message.get("headers", []):
        if key.lower() == b"content-type" and b"json" in value.lower():
            return True
    return False


def _camel_body(body: bytes) -> bytes:
    if not body:
        return body
    try:
        parsed = orjson.loads(body)
    except orjson.JSONDecodeError:
        return body
    public = camelize(parsed)
    if isinstance(public, dict) and isinstance(public.get("data"), list) and "items" not in public:
        public["items"] = public.pop("data")
        if "nextCursor" not in public:
            public["nextCursor"] = None
        if "hasMore" not in public:
            public["hasMore"] = public.get("nextCursor") is not None
    return orjson.dumps(public)


def install_middleware(
    app: ASGIApp,
    settings: BaseServiceSettings,
    inner: list[tuple[type, dict[str, object]]] | None = None,
    *,
    camel_json: bool = False,
) -> None:
    """Attach middleware. Later additions run further out.

    ``inner`` is ordered outer-to-inner and is installed inside the body limit,
    which matches spec 01 §4 for the API pipeline. ``camel_json`` rewrites public
    JSON bodies for the product API. OpenAI-compatible services leave it off.
    """
    stack = app
    for middleware, kwargs in reversed(inner or []):
        stack.add_middleware(middleware, **kwargs)  # type: ignore[attr-defined]
    stack.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_json_body_bytes)  # type: ignore[attr-defined]
    stack.add_middleware(SecurityHeadersMiddleware)  # type: ignore[attr-defined]
    stack.add_middleware(RequestIdMiddleware, service_name=settings.service_name)  # type: ignore[attr-defined]
    if camel_json:
        stack.add_middleware(CamelJsonMiddleware)  # type: ignore[attr-defined]


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            decoded = value.decode()
            return decoded if isinstance(decoded, str) else str(decoded)
    return None


def _state_request_id(scope: Scope) -> str:
    state = scope.get("state", {})
    request_id = state.get("request_id") if isinstance(state, dict) else None
    if isinstance(request_id, str):
        return request_id
    if isinstance(request_id, UUID):
        return str(request_id)
    return ""
