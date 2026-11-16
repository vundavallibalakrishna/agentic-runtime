"""Rotating the callback secret signs the next delivery."""

from __future__ import annotations

import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import orjson
from fastapi.testclient import TestClient

from ar_domain.db.context import Principal, TenantContext
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.runs.callbacks import deliver_callback
from ar_domain.runs.logic import sign_run_callback
from ar_testing.demo import demo_application
from ar_testing.demo_people import DEV_TENANT_ID, catalogue


class _Handler(BaseHTTPRequestHandler):
    seen: ClassVar[dict[str, str]] = {}

    def log_message(self, *_args: object) -> None:
        return None

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        type(self).seen = {
            "signature": self.headers.get("x-signature") or "",
            "body": body.decode(),
        }
        self.send_response(204)
        self.send_header("content-length", "0")
        self.end_headers()


def test_the_rotate_route_signs_the_next_callback() -> None:
    person = catalogue()["admin@dev.local"]
    principal = Principal(
        kind="user",
        id=str(person.user_id),
        tenant_id=DEV_TENANT_ID,
        permissions=PERMISSION_KEYS,
        auth_method="api_key",
        email="admin@dev.local",
        roles=frozenset({"tenant_admin"}),
    )
    app = demo_application()

    async def resolve(_scope: object) -> Principal:
        return principal

    app.state.resolve_principal = resolve
    app.state.context_override = TenantContext.from_principal(principal, "req-rotate")
    client = TestClient(app)
    rotated = client.post("/api/v1/tenant/run-callback-secret:rotate")
    assert rotated.status_code == 200, rotated.text
    secret = rotated.json()["secret"]
    assert secret
    actions = [row.get("action") for row in app.state.chat.audit_log]
    assert "tenant.run_callback_secret_rotated" in actions

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    item: dict[str, object] = {
        "url": f"http://127.0.0.1:{port}/hook",
        "run_id": str(uuid.uuid4()),
        "status": "completed",
        "tenant_id": DEV_TENANT_ID,
    }
    deliver_callback(app.state.chat, item)
    threads = app.state.chat.callback_threads
    threads[-1].join(timeout=5)
    httpd.shutdown()
    body = _Handler.seen["body"].encode()
    stamp = int(_Handler.seen["signature"].split(",", 1)[0].removeprefix("t="))
    assert _Handler.seen["signature"] == sign_run_callback(secret, body, stamp)
    assert orjson.loads(_Handler.seen["body"])["status"] == "completed"


def test_a_failed_write_does_not_install_the_new_secret(monkeypatch) -> None:
    from sqlalchemy.exc import IntegrityError

    person = catalogue()["admin@dev.local"]
    principal = Principal(
        kind="user",
        id=str(person.user_id),
        tenant_id=DEV_TENANT_ID,
        permissions=PERMISSION_KEYS,
        auth_method="api_key",
        email="admin@dev.local",
        roles=frozenset({"tenant_admin"}),
    )
    app = demo_application()

    async def resolve(_scope: object) -> Principal:
        return principal

    app.state.resolve_principal = resolve
    app.state.context_override = TenantContext.from_principal(principal, "req-rotate")
    app.state.chat.durable_engine = object()
    previous = "previous-secret"
    app.state.webhooks.callback_secret = previous
    app.state.chat.named_secrets = {}

    def boom(*_args: object, **_kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("ux_named_secrets_name"))

    monkeypatch.setattr("ar_domain.db.session.tenant_session", boom)
    rotated = TestClient(app).post("/api/v1/tenant/run-callback-secret:rotate")
    assert rotated.status_code == 409, rotated.text
    assert app.state.webhooks.callback_secret == previous
    assert app.state.chat.named_secrets == {}
