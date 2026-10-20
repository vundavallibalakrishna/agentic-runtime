"""Request-id, body-size and access-log middleware."""

import time
from typing import TYPE_CHECKING
from uuid import UUID

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ar_common.errors import PayloadTooLargeError
from ar_common.ids import new_id
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


def install_middleware(app: ASGIApp, settings: BaseServiceSettings) -> None:
    """Attach middleware. ``app`` is a FastAPI instance."""
    stack = app
    stack.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_json_body_bytes)  # type: ignore[attr-defined]
    stack.add_middleware(RequestIdMiddleware, service_name=settings.service_name)  # type: ignore[attr-defined]


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
