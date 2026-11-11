"""CSRF comparison. Spec: docs/03-specs/01-api-bff.md §4."""

import hmac
from urllib.parse import urlparse

_LOOPBACK = frozenset({"localhost", "127.0.0.1", "::1"})


def csrf_ok(header: str | None, expected: str | None) -> bool:
    """Constant-time compare of the CSRF header and the session token."""
    if not header or not expected:
        return False
    return hmac.compare_digest(header, expected)


def origin_ok(
    origin: str | None,
    public_url: str,
    *,
    allowed: list[str] | tuple[str, ...] = (),
    dev: bool = False,
) -> bool:
    """The ``Origin`` header must be the public URL or an explicitly allowed origin.

    Loopback names (localhost, 127.0.0.1, ::1) match each other only when ``dev``
    is set. Production keeps an exact host match.
    """
    if origin is None or origin == "":
        return True
    origin_host = _host(origin)
    if not origin_host:
        return False
    allowed_hosts = {_host(public_url)}
    for item in allowed:
        host = _host(item)
        if host:
            allowed_hosts.add(host)
    allowed_hosts.discard("")
    if origin_host in allowed_hosts:
        return True
    return dev and _loopback(origin_host) and any(_loopback(host) for host in allowed_hosts)


def _host(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else f"http://{text}")
    return parsed.netloc.lower()


def _loopback(host: str) -> bool:
    name = host
    if name.startswith("["):
        end = name.find("]")
        name = name[1:end] if end > 1 else name
    else:
        name = name.split(":", 1)[0]
    return name in _LOOPBACK
