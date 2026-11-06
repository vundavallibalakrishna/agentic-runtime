"""SMTP send and IMAP read. The platform does not provide a mail server."""

from __future__ import annotations

import imaplib
import smtplib
from email.message import EmailMessage
from typing import TYPE_CHECKING

from ar_common.sandboxkit import DEFAULT_DENY_CIDRS, host_denied
from ar_common.settings import loopback_allowed
from ar_domain.tools.general import _resolve

if TYPE_CHECKING:
    from typing import Any


def host_blocked(host: str) -> str | None:
    if host_denied(host, DEFAULT_DENY_CIDRS, _resolve, allow_loopback=loopback_allowed()):
        return f"{host} is blocked by the egress deny list"
    return None


def send_message(
    store: Any,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    use_tls: bool,
) -> dict[str, object]:
    problem = host_blocked(host)
    if problem:
        return _fail(problem)
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    factory = getattr(store, "connector_smtp", None)
    try:
        if factory is not None:
            with factory() as client:
                _login_and_send(client, username, password, sender, recipient, message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as client:
                client.ehlo()
                if use_tls:
                    client.starttls()
                    client.ehlo()
                _login_and_send(client, username, password, sender, recipient, message)
    except (OSError, smtplib.SMTPException) as exc:
        return _fail(f"SMTP refused the message. {exc.__class__.__name__}.")
    return {
        "text": f"Sent to {recipient}.",
        "structured": {"to": recipient, "subject": subject},
        "is_error": False,
    }


def list_messages(
    store: Any,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    limit: int,
    use_ssl: bool,
) -> dict[str, object]:
    problem = host_blocked(host)
    if problem:
        return _fail(problem)
    try:
        client = _imap(store, host, port, use_ssl=use_ssl)
        try:
            client.login(username, password)
            client.select("INBOX")
            _status, data = client.search(None, "ALL")
            raw = data[0] if data else b""
            ids = raw.split()[-limit:] if isinstance(raw, bytes) else []
            rows = [_header(client, item) for item in ids]
        finally:
            client.logout()
    except (OSError, imaplib.IMAP4.error) as exc:
        return _fail(f"IMAP refused the login or the mailbox. {exc.__class__.__name__}.")
    return {
        "text": f"{len(rows)} messages.",
        "structured": {"messages": rows},
        "is_error": False,
    }


def read_message(
    store: Any,
    *,
    host: str,
    port: int,
    username: str,
    password: str,
    message_id: str,
    use_ssl: bool,
) -> dict[str, object]:
    listed = list_messages(
        store,
        host=host,
        port=port,
        username=username,
        password=password,
        limit=50,
        use_ssl=use_ssl,
    )
    if listed.get("is_error"):
        return listed
    structured = listed.get("structured")
    rows = structured.get("messages") if isinstance(structured, dict) else []
    if not isinstance(rows, list):
        return _fail("The mailbox did not return messages.")
    for row in rows:
        if isinstance(row, dict) and str(row.get("id")) == message_id:
            return {"text": str(row.get("subject") or ""), "structured": row, "is_error": False}
    return _fail("The provider could not find that item (404).")


def _login_and_send(  # noqa: PLR0917
    client: Any, username: str, password: str, sender: str, recipient: str, message: EmailMessage
) -> None:
    has_auth = getattr(client, "has_extn", None)
    if username and (not callable(has_auth) or has_auth("auth")):
        client.login(username, password)
    client.send_message(message, from_addr=sender, to_addrs=[recipient])


def _imap(store: Any, host: str, port: int, *, use_ssl: bool) -> Any:
    factory = getattr(store, "connector_imap", None)
    if factory is not None:
        return factory()
    if use_ssl:
        return imaplib.IMAP4_SSL(host, port)
    return imaplib.IMAP4(host, port)


def _header(client: Any, item: bytes) -> dict[str, str]:
    _status, fetched = client.fetch(item, "(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE)])")
    text = ""
    if fetched and isinstance(fetched[0], tuple):
        text = fetched[0][1].decode("utf-8", errors="replace")
    subject = _field(text, "Subject")
    sender = _field(text, "From")
    sent = _field(text, "Date")
    return {"id": item.decode(), "subject": subject, "from": sender, "date": sent}


def _field(text: str, name: str) -> str:
    prefix = name.lower() + ":"
    for line in text.splitlines():
        if line.lower().startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _fail(text: str) -> dict[str, object]:
    return {"text": text, "structured": {}, "is_error": True, "code": "upstream_error"}
