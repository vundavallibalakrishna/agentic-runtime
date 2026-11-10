"""Password reset and a notice travel through GreenMail. Proof: contract."""

from __future__ import annotations

import os
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from temporalio.worker import Worker

from ar_domain.identity.membership import password_matches
from ar_domain.identity.passwords import hash_password
from ar_domain.identity.recovery import remember_person
from ar_domain.notifications.dispatch import notify_user
from ar_system.workflows.notification_mail import NotificationEmailWorkflow, send_smtp_notification
from ar_testing.demo import demo_application, demo_store

pytestmark = pytest.mark.integration

_IMAGE = "greenmail/standalone:2.1.3"


def _endpoint() -> tuple[str, int, str]:
    """Return host, smtp port and the GreenMail API base URL."""
    configured = os.environ.get("AR_GREENMAIL_SMTP", "").strip()
    api = os.environ.get("AR_GREENMAIL_API", "").strip()
    if configured and api:
        host, _, port = configured.partition(":")
        return host or "127.0.0.1", int(port or "3025"), api.rstrip("/")
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
    api_port = container.get_exposed_port(8080)
    return host, smtp, f"http://{host}:{api_port}"


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


async def test_password_reset_and_notification_email(temporal_env: object) -> None:
    host, port, api = _endpoint()
    store = demo_store()
    from ar_common.ids import new_id

    tenant = new_id()
    user = new_id()
    remember_person(
        store,
        email="ada@example.com",
        tenant_id=tenant,
        user_id=user,
        password_hash=hash_password("old-password"),
    )
    app = demo_application()
    app.state.chat = store
    client = TestClient(app)
    accepted = client.post("/api/v1/auth/password-reset", json={"email": "ada@example.com"})
    assert accepted.status_code == 200
    assert store.outbox
    queued = dict(store.outbox[-1])
    queued.update({"host": host, "port": port, "from": "noreply@dev.local"})
    workflow = temporal_env.client  # type: ignore[attr-defined]
    async with Worker(
        workflow,
        task_queue="ar-system-mail",
        workflows=[NotificationEmailWorkflow],
        activities=[send_smtp_notification],
    ):
        sent = await workflow.execute_workflow(
            NotificationEmailWorkflow.run,
            queued,
            id="stage12-reset-mail",
            task_queue="ar-system-mail",
        )
        assert sent["sent"] is True
        notice = notify_user(
            store,
            tenant_id=tenant,
            user_id=user,
            title="Run finished",
            body="The run finished.",
            email="ada@example.com",
        )
        assert notice["email"] is True
        mailed = dict(store.outbox[-1])
        mailed.update({"host": host, "port": port, "from": "noreply@dev.local"})
        await workflow.execute_workflow(
            NotificationEmailWorkflow.run,
            mailed,
            id="stage12-notice-mail",
            task_queue="ar-system-mail",
        )
    rows = _messages(api, "ada@example.com")
    blob = "\n".join(_text(row) for row in rows)
    assert "Run finished" in blob
    token = str(queued["body"])
    assert token in blob
    reset = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "password": "new-password-1"},
    )
    assert reset.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "ada@example.com",
            "password": "new-password-1",
            "tenantId": str(tenant),
        },
    )
    assert login.status_code == 200
    assert password_matches(store, "ada@example.com", "new-password-1")
