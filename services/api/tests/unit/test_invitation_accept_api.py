"""An invitation through the API: the mail has a link, and the link makes an account."""

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

NEW = "new.person@example.test"


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
    parsed = message_from_string(raw)
    payload = parsed.get_payload(decode=True)
    return payload.decode() if isinstance(payload, bytes) else str(parsed.get_payload())


def _admin(app: Any) -> TestClient:
    client = TestClient(app)
    signed = client.post(
        "/api/v1/auth/login", json={"email": "admin@dev.local", "password": "dev-password"}
    )
    assert signed.status_code == 200
    # What the page sends with a change: the token from its cookie, and where it is from.
    client.headers.update(
        {
            "x-csrf-token": str(client.cookies.get("ar_csrf") or ""),
            "origin": str(app.state.settings.public_url),
        }
    )
    return client


def test_an_invited_person_makes_their_account_from_the_mailed_link(mail: Any) -> None:
    app = demo_application()
    admin = _admin(app)
    invited = admin.post("/api/v1/invitations", json={"emails": [NEW], "roleKeys": ["member"]})
    assert invited.status_code == 200, invited.text
    assert invited.json()[0]["mail"]["result"] == "sent"
    [message] = mail.messages
    assert f"To: {NEW}" in message
    assert "Subject: You are invited to join" in message
    public = str(app.state.settings.public_url).rstrip("/")
    found = re.search(r"(https?://\S+/invite\?token=(\S+))", _body(message))
    assert found, "the mail carries a link with the site's address"
    assert found.group(1).startswith(f"{public}/invite?token=")
    token = found.group(2)

    visitor = TestClient(app)  # nobody is signed in
    shown = visitor.post("/api/v1/auth/invitation", json={"token": token})
    assert shown.status_code == 200
    assert shown.json()["email"] == NEW
    assert shown.json()["tenantName"]
    short = visitor.post(
        "/api/v1/auth/invitation/accept",
        json={"token": token, "displayName": "New Person", "password": "short"},
    )
    assert short.status_code == 422
    done = visitor.post(
        "/api/v1/auth/invitation/accept",
        json={"token": token, "displayName": "New Person", "password": "a-good-password"},
    )
    assert done.status_code == 200
    assert done.json() == {"accepted": True, "email": NEW}

    signed = visitor.post("/api/v1/auth/login", json={"email": NEW, "password": "a-good-password"})
    assert signed.status_code == 200
    session = visitor.get("/api/v1/auth/session")
    assert session.status_code == 200
    assert "chat:use" in session.json()["permissions"]
    assert "users:manage" not in session.json()["permissions"]

    again = TestClient(app).post(
        "/api/v1/auth/invitation/accept",
        json={"token": token, "displayName": "Other", "password": "another-password"},
    )
    assert again.status_code == 422
    assert "already been used" in again.json()["detail"]


def test_with_no_mail_server_the_invitation_is_made_and_says_its_mail_did_not_go() -> None:
    before = get_settings()
    set_settings(before.model_copy(update={"smtp_host": ""}))
    try:
        admin = _admin(demo_application())
        invited = admin.post("/api/v1/invitations", json={"emails": [NEW]})
    finally:
        set_settings(before)
    assert invited.status_code == 200
    mailed = invited.json()[0]["mail"]
    assert mailed["result"] == "failed"
    assert "AR_SMTP_HOST" in mailed["reason"]
    # The person who invited has the token, so they can pass the link on themselves.
    assert invited.json()[0]["token"]


def test_the_list_says_where_each_invitation_stands(mail: Any) -> None:
    app = demo_application()
    admin = _admin(app)
    made = admin.post(
        "/api/v1/invitations", json={"emails": ["one@example.test", "two@example.test"]}
    ).json()
    assert {row["status"] for row in made} == {"pending"}
    assert admin.delete(f"/api/v1/invitations/{made[0]['id']}").status_code == 200
    token = made[1]["token"]
    TestClient(app).post(
        "/api/v1/auth/invitation/accept",
        json={"token": token, "displayName": "Two", "password": "a-good-password"},
    )
    listed = {
        row["email"]: row["status"] for row in admin.get("/api/v1/invitations").json()["items"]
    }
    assert listed == {"one@example.test": "revoked", "two@example.test": "accepted"}
    assert len(mail.messages) == 2


def test_a_token_that_is_not_an_invitation_is_refused() -> None:
    visitor = TestClient(demo_application())
    shown = visitor.post("/api/v1/auth/invitation", json={"token": "not-a-token"})
    assert shown.status_code == 422
    assert "not valid" in shown.json()["detail"]
    blank = visitor.post("/api/v1/auth/invitation/accept", json={})
    assert blank.status_code == 422
