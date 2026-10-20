"""Idempotency-Key middleware. Spec: docs/03-specs/20-notifications-events.md §4."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ar_common.errors import ArError, ConflictError, ErrorCode
from ar_common.web.problems import problem_response
from ar_domain.events.idempotency import StoredResponse, decide
from ar_domain.events.sign import request_fingerprint

_UNSAFE = frozenset({"POST", "PATCH", "DELETE"})


class MemoryIdempotencyStore:
    """Process-local idempotency table."""

    def __init__(self) -> None:
        self.rows: dict[tuple[str, str, str], StoredResponse] = {}

    async def get(self, key: tuple[str, str, str]) -> StoredResponse | None:
        return self.rows.get(key)

    async def put(self, key: tuple[str, str, str], value: StoredResponse) -> None:
        self.rows[key] = value


class IdempotencyMiddleware:
    """Replay stored responses and reject reused keys."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") not in _UNSAFE:
            await self.app(scope, receive, send)
            return
        header = _header(scope, b"idempotency-key")
        if not header:
            await self.app(scope, receive, send)
            return
        if len(header) > 255:
            response = problem_response(
                ArError(ErrorCode.BAD_REQUEST, "Idempotency-Key is too long"),
                instance=str(scope.get("path", "")),
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        body = await _read_body(receive)
        fingerprint = request_fingerprint(str(scope.get("method")), str(scope.get("path")), body)
        state = scope.get("state", {})
        principal = state.get("principal") if isinstance(state, dict) else None
        tenant = getattr(principal, "tenant_id", None)
        principal_id = getattr(principal, "id", "")
        store = scope["app"].state.idempotency
        slot = (str(tenant), str(principal_id), header)
        decision = decide(await store.get(slot), fingerprint)
        if decision.kind == "reused":
            response = problem_response(
                ArError(
                    ErrorCode.IDEMPOTENCY_KEY_REUSED,
                    "Idempotency-Key was reused with a different body",
                ),
                instance=str(scope.get("path", "")),
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        if decision.kind == "in_flight":
            response = problem_response(
                ConflictError("a request with this Idempotency-Key is in flight"),
                instance=str(scope.get("path", "")),
                request_id=_request_id(scope),
            )
            await response(scope, receive, send)
            return
        if decision.kind == "replay" and decision.status_code is not None:
            payload = decision.body or b""
            await _send_bytes(send, decision.status_code, payload, replay=True)
            return
        await store.put(slot, StoredResponse(request_hash=fingerprint, status_code=None, body=None))
        status = 500
        chunks: list[bytes] = []

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
                headers = list(message.get("headers", []))
                message["headers"] = headers
            elif message["type"] == "http.response.body":
                chunks.append(bytes(message.get("body", b"")))
            await send(message)

        await self.app(scope, _replay(body), capture)
        await store.put(
            slot,
            StoredResponse(request_hash=fingerprint, status_code=status, body=b"".join(chunks)),
        )


def _replay(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive


async def _read_body(receive: Receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        chunks.append(bytes(message.get("body", b"")))
        if not message.get("more_body", False):
            return b"".join(chunks)


async def _send_bytes(send: Send, status: int, body: bytes, *, replay: bool) -> None:
    headers = [(b"content-type", b"application/json")]
    if replay:
        headers.append((b"idempotent-replayed", b"true"))
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return str(value.decode())
    return None


def _request_id(scope: Scope) -> str:
    state = scope.get("state", {})
    if isinstance(state, dict) and isinstance(state.get("request_id"), str):
        return str(state["request_id"])
    return ""
