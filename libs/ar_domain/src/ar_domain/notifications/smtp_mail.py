"""The one place the product sends mail from: one SMTP attempt, and the install's server.

Invitations, password resets, notices and a routine's email delivery all send through
``send_smtp``. ``install_server`` is the mail server the install is set to use
(``AR_SMTP_*``). The body is never logged.
"""

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


def install_server() -> dict[str, object]:
    """The install's own mail server, as ``send_smtp`` takes it. An empty host means none."""
    from ar_common.settings import get_settings  # noqa: PLC0415

    settings = get_settings()
    return {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "from": settings.smtp_from,
        "username": settings.smtp_username,
        "password": settings.smtp_password.get_secret_value(),
        "starttls": settings.smtp_starttls,
    }


def mail_is_set_up() -> bool:
    """Whether this install has a mail server to send through."""
    return bool(install_server()["host"])


def send_install_mail(to: str, subject: str, body: str) -> dict[str, str]:
    """Send one message through the install's server, and say what happened.

    ``result`` is ``sent`` or ``failed``; a failure carries a ``reason`` a person can act
    on. Nothing is raised: a caller that must not reveal whether an address exists decides
    what to say.
    """
    server = install_server()
    if not server["host"]:
        return {
            "result": "failed",
            "reason": "No mail server is set. An administrator sets AR_SMTP_HOST.",
        }
    try:
        message_id = send_smtp({**server, "to": to, "subject": subject, "body": body})
    except OSError as exc:  # a refusal by the server is an OSError too
        return {
            "result": "failed",
            "reason": f"The mail server refused the message ({type(exc).__name__}).",
        }
    return {"result": "sent", "message_id": message_id}
