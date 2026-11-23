"""Password reset and a notice travel through a real mail server (GreenMail)."""

from __future__ import annotations

import os
import re
from email import message_from_string
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from fastapi.testclient import TestClient

from ar_common.settings import get_settings, set_settings
from ar_domain.demo_ids import demo_id
from ar_domain.notifications.dispatch import notify_user
from ar_testing.demo import demo_application

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

_IMAGE = "greenmail/standalone:2.1.3"


@pytest.fixture
def mailbox() -> Iterator[str]:
    """A mail server the install is pointed at. Yields the address of its reading API.

    The container this starts is stopped afterwards; an earlier version left one behind
    on every run.
    """
    configured = os.environ.get("AR_GREENMAIL_SMTP", "").strip()
    api = os.environ.get("AR_GREENMAIL_API", "").strip()
    container = None
    if configured and api:
        host, _, port = configured.partition(":")
        host, smtp, api = host or "127.0.0.1", int(port or "3025"), api.rstrip("/")
    else:
        from testcontainers.core.container import DockerContainer
        from testcontainers.core.waiting_utils import wait_for_logs

        container = (
            DockerContainer(_IMAGE)
            .with_env(
                "GREENMAIL_OPTS",
                "-Dgreenmail.setup.test.all -Dgreenmail.hostname=0.0.0.0 -Dgreenmail.auth.disabled",
            )
            .with_exposed_ports(3025, 8080)
        )
        container.start()
        wait_for_logs(container, "Starting GreenMail", timeout=90)
        host = container.get_container_host_ip()
        smtp = int(container.get_exposed_port(3025))
        api = f"http://{host}:{container.get_exposed_port(8080)}"
    before = get_settings()
    set_settings(
        before.model_copy(
            update={
                "smtp_host": host,
                "smtp_port": smtp,
                "smtp_from": "noreply@dev.local",
                "egress_allow_loopback": True,
            }
        )
    )
    try:
        yield api
    finally:
        set_settings(before)
        if container is not None:
            container.stop()


def _messages(api: str, address: str) -> list[dict[str, Any]]:
    response = httpx.get(f"{api}/api/user/{address}/messages", timeout=10)
    response.raise_for_status()
    body = response.json()
    if isinstance(body, list):
        return [row for row in body if isinstance(row, dict)]
    if isinstance(body, dict) and isinstance(body.get("messages"), list):
        return [row for row in body["messages"] if isinstance(row, dict)]
    return []


def _text(message: dict[str, Any]) -> str:
    for key in ("mimeMessage", "body", "text", "content"):
        value = message.get(key)
        if isinstance(value, str) and value:
            return value
    return str(message)


def _read(message: dict[str, Any]) -> str:
    """The text of a stored mail as its reader sees it, whatever encoding it travelled in."""
    parsed = message_from_string(_text(message))
    payload = parsed.get_payload(decode=True)
    return payload.decode() if isinstance(payload, bytes) else _text(message)


def test_password_reset_and_notification_email(mailbox: str) -> None:
    address = "admin@dev.local"
    app = demo_application()
    client = TestClient(app)
    accepted = client.post("/api/v1/auth/password-reset", json={"email": address})
    assert accepted.status_code == 200
    inbox = _messages(mailbox, address)
    assert inbox, "the reset mail reached the mail server"
    found = re.search(r"/reset-password\?token=(\S+)", _read(inbox[-1]))
    assert found, "the mail carries a link"
    done = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": found.group(1), "password": "a-new-password"},
    )
    assert done.status_code == 200
    signed_in = TestClient(app).post(
        "/api/v1/auth/login", json={"email": address, "password": "a-new-password"}
    )
    assert signed_in.status_code == 200

    notice = notify_user(
        app.state.chat,
        tenant_id=demo_id("tenant"),
        user_id=demo_id("admin"),
        title="Run finished",
        body="The run finished.",
        email=address,
    )
    assert notice["email"] is True
    assert any("Run finished" in _text(row) for row in _messages(mailbox, address))
