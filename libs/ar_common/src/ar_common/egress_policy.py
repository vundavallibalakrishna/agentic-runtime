"""One decision for an outbound host.

Closed mode (``AR_EGRESS_CLOSED``) refuses any host that is not on the list it is
given, plus the install list ``AR_EGRESS_HOSTS``. An empty list then means no
outbound. With closed mode off, a public host is still allowed, which is how an
existing tenant keeps a cloud model.

A host named exactly on the list may resolve to a private address. A metadata
address is refused even when it is named. A star, a CIDR wider than one host,
and a wildcard of a single label are not matches.
"""

from __future__ import annotations

import ipaddress
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Callable

from ar_common.settings import get_settings, loopback_allowed

_METADATA = (
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)
_PRIVATE = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def closed_egress() -> bool:
    """Whether this install refuses hosts that are not on an allowlist."""
    return bool(get_settings().egress_closed)


def install_hosts() -> list[str]:
    """Hosts the install itself may reach, from ``AR_EGRESS_HOSTS``."""
    raw = get_settings().egress_hosts
    return [part.strip() for part in raw.split(",") if part.strip()]


def host_of(url: str) -> str:
    """The hostname of a URL, or an empty string."""
    return urlparse(url).hostname or ""


def resolved_addresses(host: str) -> list[str] | None:
    """IP addresses for ``host``. None when the name does not resolve."""
    return _addresses(host, None, need=True)


def metadata_address(address: str) -> bool:
    """True for a link-local or cloud metadata address."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in _METADATA)


def private_address(address: str) -> bool:
    """True for a non-public address, including loopback and metadata."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if metadata_address(address):
        return True
    return any(ip in network for network in _PRIVATE) or ip.is_private or ip.is_loopback


def explicit_host(host: str, allow: list[str]) -> bool:
    """True when the list names this host itself, not a wildcard or a star."""
    lowered = host.lower().rstrip(".")
    for item in allow:
        rule = item.strip().lower().rstrip(".")
        if not rule or rule == "*" or rule.startswith("*.") or "/" in rule:
            continue
        if rule == lowered:
            return True
    return False


def listed_host(host: str, allow: list[str]) -> bool:
    """True when the list names this host or a wildcard of at least two labels."""
    if explicit_host(host, allow):
        return True
    lowered = host.lower().rstrip(".")
    labels = lowered.split(".")
    for item in allow:
        rule = item.strip().lower().rstrip(".")
        if not rule.startswith("*."):
            continue
        suffix = rule[2:]
        if suffix.count(".") < 1:
            continue
        if (lowered == suffix or lowered.endswith("." + suffix)) and len(labels) >= 2:
            return True
    return False


def decide(  # noqa: PLR0911, PLR0912
    host: str,
    allow: list[str],
    *,
    resolve: Callable[[str], list[str]] | None = None,
    closed: bool | None = None,
    loopback: bool | None = None,
    check_private: bool = True,
) -> str | None:
    """Why ``host`` may not be dialled, or None when it may.

    ``check_private`` resolves names and refuses a private address that was not
    named exactly. Model calls leave it off unless closed mode or cluster
    residency is on, so a hostname such as an in-cluster service keeps working.
    """
    name = host.strip().lower().rstrip(".")
    if not name:
        return "url must name a host"
    if name in {"169.254.169.254", "metadata.google.internal"}:
        return f"{name} is a metadata address and is denied"
    combined = [*allow, *install_hosts()]
    is_closed = closed_egress() if closed is None else closed
    loop = loopback_allowed() if loopback is None else loopback
    if is_closed and not listed_host(name, [item for item in combined if item.strip() != "*"]):
        return (
            f"{name} is not on the egress allow list. "
            "Add it to the organisation allowlist or to AR_EGRESS_HOSTS."
        )
    addresses = _addresses(
        name, resolve, need=check_private or is_closed or explicit_host(name, combined)
    )
    if addresses is None:
        if check_private or is_closed:
            return f"{name} could not be resolved"
        return None
    if any(metadata_address(item) for item in addresses):
        return f"{name} is a metadata address and is denied"
    if explicit_host(name, combined):
        # Loopback stays an install setting. Any other private address that was
        # named exactly is the on-prem path.
        if any(_loopback(item) for item in addresses) and not loop:
            return f"{name} is blocked by the egress deny list"
        return None
    if not check_private and not is_closed:
        literals = [item for item in addresses if _literal(name)]
        if any(private_address(item) for item in literals):
            if loop and all(_loopback(item) for item in literals):
                return None
            return f"{name} is blocked by the egress deny list"
        return None
    if any(private_address(item) for item in addresses):
        if loop and all(_loopback(item) for item in addresses):
            return None
        return f"{name} is blocked by the egress deny list"
    return None


def decide_url(
    url: str,
    allow: list[str],
    *,
    resolve: Callable[[str], list[str]] | None = None,
    closed: bool | None = None,
    loopback: bool | None = None,
    check_private: bool = True,
) -> str | None:
    """``decide`` for a URL. A non-http scheme is refused."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return "url must be an http or https URL"
    return decide(
        parsed.hostname or "",
        allow,
        resolve=resolve,
        closed=closed,
        loopback=loopback,
        check_private=check_private,
    )


def _literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _loopback(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def _addresses(
    host: str,
    resolve: Callable[[str], list[str]] | None,
    *,
    need: bool,
) -> list[str] | None:
    if _literal(host):
        return [host]
    if not need:
        return []
    lookup = resolve or _resolve
    try:
        found = lookup(host)
    except OSError:
        return None
    return found or None


def _resolve(host: str) -> list[str]:
    import socket  # noqa: PLC0415

    infos = socket.getaddrinfo(host, None)
    return [str(item[4][0]) for item in infos]
