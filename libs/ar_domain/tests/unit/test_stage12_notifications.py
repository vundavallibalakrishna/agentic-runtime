"""Web Push contract. A local endpoint checks the VAPID signature. Proof: contract."""

from __future__ import annotations

import base64
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import orjson
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from ar_domain.chat.service import demo_id
from ar_domain.notifications.dispatch import notify_user, subscribe
from ar_domain.notifications.web_push import authorization_header, load_private_key
from ar_domain.tools.named_secrets import write_named_secret
from ar_testing.demo import demo_store


def _pem() -> tuple[str, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return pem, key


def _b64(segment: str) -> bytes:
    pad = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _signed(authorization: str, audience: str, key: ec.EllipticCurvePrivateKey) -> bool:
    token = ""
    public = ""
    for part in authorization.removeprefix("vapid ").split(","):
        name, _, value = part.strip().partition("=")
        if name == "t":
            token = value
        if name == "k":
            public = value
    header, payload, signature = token.split(".")
    signing = f"{header}.{payload}".encode()
    raw = _b64(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    key.public_key().verify(der, signing, ec.ECDSA(hashes.SHA256()))
    body = orjson.loads(_b64(payload))
    assert body["aud"] == audience
    assert public
    assert authorization_header(key, audience + "/sub").split("k=")[1] == public
    return True


def test_vapid_push_is_signed_and_a_gone_subscription_is_pruned() -> None:
    pem, key = _pem()
    assert load_private_key(pem) is not None
    seen: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            seen.append(self.headers.get("Authorization") or "")
            status = 410 if self.path.endswith("/gone") else 201
            self.send_response(status)
            self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            del fmt, args

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        store = demo_store()
        tenant = demo_id("tenant")
        user = demo_id("admin")
        write_named_secret(store, tenant, "web_push_vapid_private", pem)
        live = f"http://127.0.0.1:{port}/sub"
        gone = f"http://127.0.0.1:{port}/gone"
        subscribe(store, tenant_id=tenant, user_id=user, endpoint=live)
        dropped = subscribe(store, tenant_id=tenant, user_id=user, endpoint=gone)
        note = notify_user(
            store, tenant_id=tenant, user_id=user, title="Done", body="The run finished."
        )
        assert note["push"]["delivered"] == 1
        assert note["push"]["pruned"] == 1
        assert note["push"]["proof"] == "contract"
        assert _signed(seen[0], f"http://127.0.0.1:{port}", key)
        assert dropped["id"] not in {row["id"] for row in store.push_subscriptions.values()}
    finally:
        server.shutdown()


def test_push_without_a_key_stays_pending() -> None:
    store = demo_store()

    def _unused(request: httpx.Request) -> httpx.Response:
        del request
        raise AssertionError("no push without a key")

    store.push_transport = httpx.MockTransport(_unused)  # type: ignore[attr-defined]
    note = notify_user(
        store,
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        title="Quiet",
        body="no key",
    )
    assert note["push"]["pending"] is True
    assert note["push"]["delivered"] == 0
