"""One SMTP attempt. The worker activity retries with backoff. The body is not logged."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Any  # noqa: TC003 - the message dict is read at runtime


def send_smtp(message: dict[str, Any]) -> None:
    """Send one message. Raises when the server refuses it so the activity can retry."""
    host = str(message.get("host") or "")
    port = int(message.get("port") or 0)
    if not host or port <= 0:
        raise smtplib.SMTPException("smtp host is not configured")
    mail = EmailMessage()
    sender = str(message.get("from") or "noreply@dev.local")
    mail["From"] = sender
    mail["To"] = str(message.get("to") or "")
    mail["Subject"] = str(message.get("subject") or "")
    mail.set_content(str(message.get("body") or ""))
    with smtplib.SMTP(host, port, timeout=10) as client:
        if message.get("starttls"):
            client.starttls()
        username = str(message.get("username") or "")
        if username:
            client.login(username, str(message.get("password") or ""))
        client.send_message(mail)
