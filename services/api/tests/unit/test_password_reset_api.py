"""Password reset through the API: a real mail arrives with a link, and the link works."""

from __future__ import annotations

import re
import threading
from email import message_from_string
from socketserver import StreamRequestHandler, ThreadingTCPServer
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from ar_common.settings import get_settings, set_settings
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    from collections.abc import Iterator

ADA = "admin@dev.local"


class _Mail(StreamRequestHandler):
    def handle(self) -> None:
        self.wfile.write(b"220 ready\r\n")
        lines: list[str] | None = None
        while True:
            raw = self.rfile.readline()
            if not raw:
                return
            line = raw.decode(errors="replace").rstrip("\r\n")
            if lines is not None:
                if line == ".":
                    self.server.messages.append("\n".join(lines))  # type: ignore[attr-defined]
                    lines = None
                    self.wfile.write(b"250 ok\r\n")
                else:
                    lines.append(line)
            elif line.upper().startswith("DATA"):
                lines = []
                self.wfile.write(b"354 go\r\n")
            elif line.upper().startswith("QUIT"):
                self.wfile.write(b"221 bye\r\n")
                return
            else:
                self.wfile.write(b"250 ok\r\n")


@pytest.fixture
def mail() -> Iterator[Any]:
    server: Any = ThreadingTCPServer(("127.0.0.1", 0), _Mail)
    server.messages = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    before = get_settings()
    set_settings(
        before.model_copy(
            update={
                "smtp_host": "127.0.0.1",
                "smtp_port": server.server_address[1],
                "smtp_from": "accounts@install.test",
                "egress_allow_loopback": True,
            }
        )
    )
    yield server
    set_settings(before)
    server.shutdown()
    server.server_close()


def _body(raw: str) -> str:
    """The text of a mail as its reader sees it, whatever encoding it travelled in."""
    parsed = message_from_string(raw)
    payload = parsed.get_payload(decode=True)
    return payload.decode() if isinstance(payload, bytes) else str(parsed.get_payload())


def _client() -> TestClient:
    return TestClient(demo_application())


def _sign_in(client: TestClient, password: str) -> int:
    return client.post("/api/v1/auth/login", json={"email": ADA, "password": password}).status_code


def test_with_no_mail_server_the_reply_says_so_for_any_address() -> None:
    before = get_settings()
    set_settings(before.model_copy(update={"smtp_host": ""}))
    try:
        client = _client()
        known = client.post("/api/v1/auth/password-reset", json={"email": ADA})
        unknown = client.post("/api/v1/auth/password-reset", json={"email": "nobody@dev.local"})
    finally:
        set_settings(before)
    assert (known.status_code, unknown.status_code) == (503, 503)
    assert "cannot send mail" in known.json()["detail"]
    # The same words for an address that exists and one that does not.
    assert known.json()["detail"] == unknown.json()["detail"]


def test_the_mailed_link_sets_a_new_password_once(mail: Any) -> None:
    client = _client()
    assert _sign_in(client, "dev-password") == 200
    asked = client.post("/api/v1/auth/password-reset", json={"email": ADA})
    assert asked.status_code == 200
    assert asked.json() == {"accepted": True}
    [message] = mail.messages
    assert f"To: {ADA}" in message
    assert "From: accounts@install.test" in message
    assert "Subject: Reset your password" in message
    found = re.search(r"(https?://\S+/reset-password\?token=(\S+))", _body(message))
    assert found, "the mail carries a link, not a bare token"
    public = str(client.app.state.settings.public_url).rstrip("/")  # type: ignore[attr-defined]
    assert found.group(1).startswith(f"{public}/reset-password?token=")
    token = found.group(2)

    short = client.post(
        "/api/v1/auth/password-reset/confirm", json={"token": token, "password": "short"}
    )
    assert short.status_code == 422
    done = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "password": "a-new-password"},
    )
    assert done.status_code == 200
    fresh = _client_like(client)
    assert _sign_in(fresh, "dev-password") != 200
    assert _sign_in(fresh, "a-new-password") == 200
    again = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "password": "yet-another-one"},
    )
    assert again.status_code == 422
    assert "not valid" in again.json()["detail"]


def test_an_unknown_address_gets_the_same_reply_and_no_mail(mail: Any) -> None:
    client = _client()
    asked = client.post("/api/v1/auth/password-reset", json={"email": "nobody@dev.local"})
    assert asked.status_code == 200
    assert asked.json() == {"accepted": True}
    assert mail.messages == []
    blank = client.post("/api/v1/auth/password-reset", json={})
    assert blank.json() == {"accepted": True}


def _client_like(client: TestClient) -> TestClient:
    """A second browser on the same application: no cookies of the first."""
    return TestClient(client.app)
