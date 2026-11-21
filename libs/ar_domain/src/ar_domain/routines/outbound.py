"""Send a routine's result outside the product: one attempt, by email or signed webhook.

Spec: docs/03-specs/15-routines-triggers.md §4. The caller has already checked policy
and the owner's approval and masked the text. Nothing here records anything: it sends,
and says what happened in words a person can act on. No content is logged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from ar_common.egress_http import EgressDenied, current_allow, guard, sync_client
from ar_common.settings import get_settings
from ar_common.time import utcnow
from ar_domain.channels.posts import load_credentials
from ar_domain.events.sign import public_json_bytes, sign_body
from ar_domain.notifications.smtp_mail import send_smtp

if TYPE_CHECKING:
    from typing import Any

_TIMEOUT_S = 10.0
SIGNATURE_HEADER = "X-Signature"
DELIVERY_HEADER = "X-Delivery-Id"


def send(
    store: Any,
    tenant_id: object,
    target: str,
    arguments: dict[str, object],
    *,
    secret: str,
    delivery_id: str,
) -> dict[str, str]:
    """Send once. ``result`` is ``posted`` or ``failed``; a failure carries a ``reason``."""
    if target == "email":
        return _email(store, tenant_id, arguments)
    if target == "webhook":
        return _webhook(arguments, secret, delivery_id)
    return _failed(f"Nothing in this install can send to {target or 'this target'} yet.")


def _email(store: Any, tenant_id: object, arguments: dict[str, object]) -> dict[str, str]:
    to = str(arguments.get("to") or "").strip()
    if "@" not in to:
        return _failed("The delivery names no email address.")
    server = _mail_server(store, tenant_id, arguments.get("integration"))
    if server is None:
        return _failed("The email integration this delivery names was not found.")
    if not server.get("host"):
        return _failed(
            "No mail server is set. Set AR_SMTP_HOST or name an email integration on the delivery."
        )
    message = {
        **server,
        "to": to,
        "subject": str(arguments.get("subject") or ""),
        "body": str(arguments.get("text") or ""),
    }
    try:
        message_id = send_smtp(message)
    except OSError as exc:  # a refusal by the server is an OSError too
        return _failed(f"The mail server refused the message ({type(exc).__name__}).")
    return {"result": "posted", "external_message_id": message_id}


def _mail_server(store: Any, tenant_id: object, named: object) -> dict[str, object] | None:
    """The server to send through: the named email integration, or the install's own."""
    if named:
        row = _integration(store, tenant_id, str(named))
        if row is None:
            return None
        found = load_credentials(store, row)
        return {
            "host": str(found.get("smtp_host") or ""),
            "port": found.get("smtp_port") or 0,
            "from": str(found.get("address") or found.get("username") or ""),
            "username": str(found.get("username") or ""),
            "password": str(found.get("password") or ""),
            "starttls": bool(found.get("username")),
        }
    settings = get_settings()
    return {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "from": settings.smtp_from,
        "username": settings.smtp_username,
        "password": settings.smtp_password.get_secret_value(),
        "starttls": settings.smtp_starttls,
    }


def _integration(store: Any, tenant_id: object, named: str) -> dict[str, object] | None:
    rows = getattr(store, "channel_integrations", None)
    if not isinstance(rows, dict):
        return None
    for row in rows.values():
        if not isinstance(row, dict) or row.get("kind") != "email":
            continue
        if str(row.get("tenant_id")) != str(tenant_id) or row.get("status") == "disabled":
            continue
        if named in {str(row.get("id")), str(row.get("name"))}:
            return row
    return None


def _webhook(arguments: dict[str, object], secret: str, delivery_id: str) -> dict[str, str]:
    url = str(arguments.get("url") or "").strip()
    if not url:
        return _failed("The delivery names no address to call.")
    allow = current_allow()
    problem = guard(url, allow)
    if problem is not None:
        return _failed(f"The address may not be called: {problem}.")
    body = public_json_bytes(arguments.get("payload") or {})
    headers = {"Content-Type": "application/json", DELIVERY_HEADER: delivery_id}
    if secret:
        headers[SIGNATURE_HEADER] = sign_body(secret, body, int(utcnow().timestamp()))
    try:
        with sync_client(allow=allow, timeout=_TIMEOUT_S) as client:
            response = client.post(url, content=body, headers=headers)
    except (httpx.HTTPError, EgressDenied) as exc:
        return _failed(f"The address could not be reached ({type(exc).__name__}).")
    if not httpx.codes.is_success(response.status_code):
        return _failed(f"The address answered {response.status_code}.")
    return {"result": "posted", "external_message_id": delivery_id}


def _failed(reason: str) -> dict[str, str]:
    return {"result": "failed", "reason": reason}
