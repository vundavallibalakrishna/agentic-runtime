"""One SMTP attempt. The worker activity retries with backoff. The body is not logged."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from typing import Any  # noqa: TC003 - the message dict is read at runtime


def send_smtp(message: dict[str, Any]) -> str:
    """Send one message and return its Message-ID. Raises when the server refuses it."""
    host = str(message.get("host") or "")
    port = int(message.get("port") or 0)
    if not host or port <= 0:
        raise smtplib.SMTPException("smtp host is not configured")
    from ar_common.egress_policy import closed_egress, decide  # noqa: PLC0415

    if closed_egress():
        from ar_common.egress_http import EgressDenied, pinned_host  # noqa: PLC0415

        problem = decide(host, [], closed=True, check_private=True)
        if problem is not None:
            raise smtplib.SMTPException(problem)
        try:
            host = pinned_host(host)
        except EgressDenied as exc:
            raise smtplib.SMTPException(exc.reason) from exc
    mail = EmailMessage()
    sender = str(message.get("from") or "noreply@dev.local")
    mail["From"] = sender
    mail["To"] = str(message.get("to") or "")
    mail["Subject"] = str(message.get("subject") or "")
    domain = parseaddr(sender)[1].rpartition("@")[2]
    mail["Date"] = formatdate()
    mail["Message-ID"] = make_msgid(domain=domain or None)
    mail.set_content(str(message.get("body") or ""))
    with smtplib.SMTP(host, port, timeout=10) as client:
        if message.get("starttls"):
            client.starttls()
        username = str(message.get("username") or "")
        if username:
            client.login(username, str(message.get("password") or ""))
        client.send_message(mail)
    return str(mail["Message-ID"])
