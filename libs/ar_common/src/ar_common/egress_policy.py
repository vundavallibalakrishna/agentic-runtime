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

# Always refused, even when the name is on an allowlist.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_SIXTO4 = ipaddress.ip_network("2002::/16")
_ALWAYS_DENY = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("192.0.0.192/32"),
    ipaddress.ip_network("100.100.100.200/32"),
    ipaddress.ip_network("168.63.129.16/32"),
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("fd00:ec2::254/128"),
)
# Private ranges an operator may name when AR_EGRESS_ALLOW_NAMED_PRIVATE is on.
_NAMED_PRIVATE = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)
_PRIVATE = (
    *_ALWAYS_DENY,
    *_NAMED_PRIVATE,
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),
)
_LOOPBACK_NAMES = frozenset({"localhost", "fake-llm"})


def closed_egress() -> bool:
    """Whether this install refuses hosts that are not on an allowlist."""
    return bool(get_settings().egress_closed)


def install_hosts() -> list[str]:
    """Hosts the install itself may reach, from ``AR_EGRESS_HOSTS``.

    They apply only while closed egress is on. In open mode they do not widen
    what a tenant may dial.
    """
    raw = get_settings().egress_hosts
    return [part.strip() for part in raw.split(",") if part.strip()]


def is_operator_private(address: str) -> bool:
    """True for an RFC1918 or unique-local address, not metadata or loopback."""
    return _named_private(address)


def named_private_allowed() -> bool:
    """Whether an exactly named host may resolve to a private address."""
    return bool(get_settings().egress_allow_named_private)


def host_of(url: str) -> str:
    """The hostname of a URL, or an empty string."""
    return urlparse(url).hostname or ""


def resolved_addresses(host: str) -> list[str] | None:
    """IP addresses for ``host``. None when the name does not resolve."""
    return _addresses(host, None, need=True)


def _part(text: str) -> int | None:
    if text.lower().startswith("0x"):
        try:
            return int(text, 16)
        except ValueError:
            return None
    if len(text) > 1 and text.startswith("0") and text.isdigit():
        try:
            return int(text, 8)
        except ValueError:
            return None
    if text.isdigit():
        return int(text, 10)
    return None


def _inet_aton(text: str) -> ipaddress.IPv4Address | None:  # noqa: PLR0911
    """inet_aton forms: ``127.1``, ``0x7f.0.0.1``, decimal and octal."""
    parts = text.split(".")
    if not 1 <= len(parts) <= 4:
        return None
    numbers: list[int] = []
    for part in parts:
        parsed = _part(part)
        if parsed is None:
            return None
        numbers.append(parsed)
    try:
        if len(numbers) == 1 and numbers[0] <= 0xFFFFFFFF:
            return ipaddress.IPv4Address(numbers[0])
        if len(numbers) == 2 and numbers[0] <= 255 and numbers[1] <= 0xFFFFFF:
            return ipaddress.IPv4Address((numbers[0] << 24) | numbers[1])
        if len(numbers) == 3 and numbers[0] <= 255 and numbers[1] <= 255 and numbers[2] <= 0xFFFF:
            return ipaddress.IPv4Address((numbers[0] << 24) | (numbers[1] << 16) | numbers[2])
        if len(numbers) == 4 and all(item <= 255 for item in numbers):
            value = (numbers[0] << 24) | (numbers[1] << 16) | (numbers[2] << 8) | numbers[3]
            return ipaddress.IPv4Address(value)
    except ValueError:
        return None
    return None


def _embedded_v4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    """The IPv4 address inside NAT64 or 6to4, when ``address`` is one of those."""
    if address in _NAT64:
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    if address in _SIXTO4:
        return ipaddress.IPv4Address((int(address) >> 80) & 0xFFFFFFFF)
    return None


def canonical_ip(
    host: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """The address ``host`` names, unwrapping mapped, decimal and octal forms.

    ``2130706433`` and ``0177.0.0.1`` are ``127.0.0.1``. ``::ffff:169.254.169.254``
    is ``169.254.169.254``. A hostname returns None.
    """
    text = host.strip().strip("[]")
    if not text:
        return None
    dotted = _inet_aton(text)
    if dotted is not None:
        return dotted
    try:
        parsed_ip = ipaddress.ip_address(text)
    except ValueError:
        return None
    mapped = getattr(parsed_ip, "ipv4_mapped", None)
    if isinstance(mapped, ipaddress.IPv4Address):
        return mapped
    if isinstance(parsed_ip, ipaddress.IPv6Address):
        embedded = _embedded_v4(parsed_ip)
        if embedded is not None:
            return embedded
    return parsed_ip


def metadata_address(address: str) -> bool:
    """True for a link-local, unspecified, or cloud metadata address."""
    ip = canonical_ip(address)
    if ip is None:
        return address.strip().lower().rstrip(".") == "metadata.google.internal"
    if any(ip in network for network in _ALWAYS_DENY):
        return True
    return bool(ip.is_link_local or ip.is_unspecified)


def private_address(address: str) -> bool:
    """True for a non-public address, including loopback and metadata."""
    ip = canonical_ip(address)
    if ip is None:
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


def decide(  # noqa: PLR0911
    host: str,
    allow: list[str],
    *,
    resolve: Callable[[str], list[str]] | None = None,
    closed: bool | None = None,
    loopback: bool | None = None,
    check_private: bool = True,
    named_private: bool | None = None,
) -> str | None:
    """Why ``host`` may not be dialled, or None when it may.

    ``check_private`` resolves names and refuses a private address that was not
    named exactly. Model calls leave it off unless closed mode or cluster
    residency is on, so a hostname such as an in-cluster service keeps working.
    """
    name = host.strip().lower().rstrip(".")
    if not name:
        return "url must name a host"
    if name == "metadata.google.internal" or metadata_address(name):
        return f"{name} is a metadata address and is denied"
    is_closed = closed_egress() if closed is None else closed
    loop = loopback_allowed() if loopback is None else loopback
    private_ok = named_private_allowed() if named_private is None else named_private
    combined = list(allow)
    if is_closed:
        combined = [*combined, *install_hosts()]
    listed = [item for item in combined if item.strip() != "*"]
    if is_closed and not listed_host(name, listed):
        return (
            f"{name} is not on the egress allow list. "
            "Add it to the organisation allowlist or to AR_EGRESS_HOSTS."
        )
    if name in _LOOPBACK_NAMES:
        if not loop:
            return f"{name} is not allowed"
        return None
    literal = canonical_ip(name)
    if literal is not None:
        return _ip_decision(name, [str(literal)], listed, loop=loop, private_ok=private_ok)
    addresses = _addresses(name, resolve, need=check_private or is_closed)
    if addresses is None:
        if check_private or is_closed:
            return f"{name} could not be resolved"
        return None
    if not addresses and not check_private and not is_closed:
        return None
    canonical = [str(canonical_ip(item) or item) for item in addresses]
    return _ip_decision(
        name, canonical, listed, loop=loop, private_ok=private_ok, named=explicit_host(name, listed)
    )


def decide_url(
    url: str,
    allow: list[str],
    *,
    resolve: Callable[[str], list[str]] | None = None,
    closed: bool | None = None,
    loopback: bool | None = None,
    check_private: bool = True,
    named_private: bool | None = None,
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
        named_private=named_private,
    )


def dial_addresses(
    host: str,
    allow: list[str],
    *,
    resolve: Callable[[str], list[str]] | None = None,
    closed: bool | None = None,
    loopback: bool | None = None,
    named_private: bool | None = None,
) -> tuple[str | None, list[str]]:
    """The addresses a real connection may use, after ``decide``.

    The caller connects to these addresses and not to a second DNS answer.
    """
    problem = decide(
        host,
        allow,
        resolve=resolve,
        closed=closed,
        loopback=loopback,
        check_private=True,
        named_private=named_private,
    )
    if problem is not None:
        return problem, []
    literal = canonical_ip(host)
    if literal is not None:
        return None, [str(literal)]
    found = _addresses(host, resolve, need=True)
    if not found:
        return f"{host} could not be resolved", []
    pinned = [str(canonical_ip(item) or item) for item in found]
    return None, pinned


def _ip_decision(  # noqa: PLR0911
    name: str,
    addresses: list[str],
    listed: list[str],
    *,
    loop: bool,
    private_ok: bool,
    named: bool | None = None,
) -> str | None:
    """Refuse metadata, unspecified, and private addresses the install did not allow."""
    if not addresses:
        return f"{name} could not be resolved"
    if any(metadata_address(item) for item in addresses):
        return f"{name} is a metadata address and is denied"
    is_named = explicit_host(name, listed) if named is None else named
    if any(private_address(item) for item in addresses):
        if all(_loopback(item) for item in addresses) and loop:
            return None
        if is_named and private_ok and all(_named_private(item) for item in addresses):
            return None
        if is_named and all(_named_private(item) for item in addresses):
            return (
                f"{name} is a private address. Set AR_EGRESS_ALLOW_NAMED_PRIVATE "
                "to reach a named private host."
            )
        return f"{name} is blocked by the egress deny list"
    return None


def _named_private(address: str) -> bool:
    ip = canonical_ip(address)
    if ip is None or metadata_address(address) or _loopback(address):
        return False
    return any(ip in network for network in _NAMED_PRIVATE)


def _literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def _loopback(address: str) -> bool:
    ip = canonical_ip(address)
    return bool(ip is not None and ip.is_loopback)


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
