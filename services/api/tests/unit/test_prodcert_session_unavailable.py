"""Production-cert defect 3: a Valkey timeout on the session read is 503, not 500.

The session store is read inside ``AuthenticateMiddleware``. An error there escapes
the app's problem-details handler, so an unhandled one reaches the ASGI server as a
bare 500. The middleware must turn the store's ``UnavailableError`` into a 503 the
caller can act on. Proof: unit.
"""

import asyncio
import types

import orjson

from ar_api.middleware.stack import AuthenticateMiddleware
from ar_common.errors import UnavailableError


def _drive(resolver) -> list[dict]:
    app_obj = types.SimpleNamespace(state=types.SimpleNamespace(resolve_principal=resolver))

    async def downstream(scope, receive, send):  # pragma: no cover - must not run
        raise AssertionError("the request reached the app despite an unavailable store")

    middleware = AuthenticateMiddleware(downstream)
    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "path": "/api/v1/agents",
        "method": "GET",
        "headers": [],
        "app": app_obj,
    }
    asyncio.run(middleware(scope, receive, send))
    return sent


def test_session_store_timeout_is_503_not_500() -> None:
    async def boom(_scope):
        raise UnavailableError("session store is unavailable")

    sent = _drive(boom)
    start = next(message for message in sent if message["type"] == "http.response.start")
    assert start["status"] == 503
    headers = {key.decode(): value.decode() for key, value in start.get("headers", [])}
    assert "application/problem+json" in headers.get("content-type", "")
    body = next(message for message in sent if message["type"] == "http.response.body")
    payload = orjson.loads(body["body"])
    assert payload["status"] == 503
    assert payload["code"] == "unavailable"
