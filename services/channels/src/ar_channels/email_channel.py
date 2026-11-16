"""Email acceptance and an in-process mailbox. Spec: docs/03-specs/16-channels.md §3.

GreenMail is the container named in the plan. CI uses this mailbox so the
round trip does not pull that image (OQ-42).
"""

import aioimaplib
import aiosmtplib


def auth_passes(header: str, domains: set[str]) -> bool:
    """True when SPF or DKIM passed for a verified tenant domain."""
    lowered = header.lower()
    for domain in domains:
        name = domain.lower()
        if name and name in lowered and ("spf=pass" in lowered or "dkim=pass" in lowered):
            return True
    return False


class BounceBook:
    """One polite bounce per sender per day."""

    def __init__(self) -> None:
        self.sent: set[str] = set()

    def should_bounce(self, sender: str, day: str) -> bool:
        key = f"{sender.lower()}|{day}"
        if key in self.sent:
            return False
        self.sent.add(key)
        return True


class InProcessMailbox:
    def __init__(self) -> None:
        self.inbox: list[dict[str, str]] = []
        self.sent: list[dict[str, str]] = []

    def deliver(self, message: dict[str, str]) -> None:
        self.inbox.append(message)

    def poll(self) -> list[dict[str, str]]:
        found = list(self.inbox)
        self.inbox.clear()
        return found

    def send(self, message: dict[str, str]) -> None:
        self.sent.append(message)


def client_factories() -> tuple[object, object]:
    """Constructors that dial the approved address when egress is closed."""
    from ar_common.egress_http import pinned_host  # noqa: PLC0415

    def IMAP4(*args: object, **kwargs: object) -> object:  # noqa: N802
        if args:
            pinned = pinned_host(str(args[0]))
            return aioimaplib.IMAP4(pinned, *args[1:], **kwargs)
        host = kwargs.get("host")
        if isinstance(host, str):
            kwargs["host"] = pinned_host(host)
        return aioimaplib.IMAP4(*args, **kwargs)

    def SMTP(*args: object, **kwargs: object) -> object:  # noqa: N802
        hostname = kwargs.get("hostname")
        if isinstance(hostname, str):
            kwargs["hostname"] = pinned_host(hostname)
        return aiosmtplib.SMTP(*args, **kwargs)  # type: ignore[arg-type]

    return IMAP4, SMTP


def accept_email(
    message: dict[str, str], *, domains: set[str], bounces: BounceBook, day: str
) -> dict[str, str]:
    header = message.get("authentication_results") or ""
    if auth_passes(header, domains):
        return {"action": "accept"}
    sender = message.get("from") or ""
    if bounces.should_bounce(sender, day):
        return {"action": "bounce", "to": sender, "body": "We could not verify the sender domain."}
    return {"action": "drop"}
