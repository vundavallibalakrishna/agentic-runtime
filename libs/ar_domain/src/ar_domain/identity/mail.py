"""SMTP delivery for invitations and notifications."""

import smtplib
from email.message import EmailMessage


def send_email(
    *,
    host: str,
    port: int,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    username: str = "",
    password: str = "",
    starttls: bool = False,
) -> None:
    """Send one plain-text message. Callers run this in a worker thread."""
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=10) as client:
        if starttls:
            client.starttls()
        if username:
            client.login(username, password)
        client.send_message(message)
