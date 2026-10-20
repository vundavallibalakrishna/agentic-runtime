"""Outbound HTTP. Spec: docs/08-quality/coding-standards-python.md §7."""

import ipaddress
import socket
from collections.abc import Callable, Sequence
from typing import Any  # noqa: TC003 - kwargs are passed through to httpx
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ar_common.errors import ForbiddenError

_CONNECT_TIMEOUT_S = 5.0
_READ_TIMEOUT_S = 30.0
_IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
_BLOCKED = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

Resolver = Callable[[str], list[str]]


def is_public_ip(value: str) -> bool:
    """Return whether an IP address is a globally routable unicast address."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    if not address.is_global:
        return False
    return not any(address in network for network in _BLOCKED)


def _default_resolver(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    addresses: list[str] = []
    for info in infos:
        sockaddr = info[4]
        if isinstance(sockaddr, tuple):
            addresses.append(str(sockaddr[0]))
    return addresses


def assert_public_url(
    url: str,
    *,
    resolver: Resolver = _default_resolver,
    allow_hosts: Sequence[str] = (),
) -> None:
    """Reject URLs that resolve to private, link-local, or metadata addresses.

    Raises:
        ForbiddenError: the host is not public and is not in ``allow_hosts``.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if host is None or parsed.scheme not in {"http", "https"}:
        raise ForbiddenError("URL is not an absolute http(s) URL")
    if host in allow_hosts:
        return
    literal = host
    try:
        addresses = [literal] if ipaddress.ip_address(literal) else resolver(host)
    except ValueError:
        addresses = resolver(host)
    except socket.gaierror as exc:
        raise ForbiddenError("Host did not resolve") from exc
    if not addresses or any(not is_public_ip(item) for item in addresses):
        raise ForbiddenError("URL resolves to a blocked address")


class HttpClient:
    """httpx client with timeouts, SSRF checks and retries for idempotent methods."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        resolver: Resolver = _default_resolver,
        allow_hosts: Sequence[str] = (),
    ) -> None:
        self._client = client
        self._resolver = resolver
        self._allow_hosts = allow_hosts

    @property
    def raw(self) -> httpx.AsyncClient:
        return self._client

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request after the SSRF check."""
        assert_public_url(url, resolver=self._resolver, allow_hosts=self._allow_hosts)
        if method.upper() in _IDEMPOTENT:
            return await self._idempotent(method, url, **kwargs)
        return await self._client.request(method, url, **kwargs)

    async def _idempotent(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        @retry(
            retry=retry_if_exception_type(httpx.TransportError),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.05, max=1),
            reraise=True,
        )
        async def send() -> httpx.Response:
            return await self._client.request(method, url, **kwargs)

        return await send()


def http_client(
    *,
    resolver: Resolver = _default_resolver,
    allow_hosts: Sequence[str] = (),
) -> HttpClient:
    """Build the process HTTP client. OpenTelemetry instruments the inner httpx client."""
    timeout = httpx.Timeout(_READ_TIMEOUT_S, connect=_CONNECT_TIMEOUT_S)
    client = httpx.AsyncClient(timeout=timeout, follow_redirects=False)
    return HttpClient(client, resolver=resolver, allow_hosts=allow_hosts)
