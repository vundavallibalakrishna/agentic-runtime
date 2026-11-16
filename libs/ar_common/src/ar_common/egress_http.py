"""The only HTTP client the platform uses to leave the process.

The transport resolves the host once, refuses a failed lookup, and dials the
approved address from a custom network backend. The request URL is unchanged,
so the Host header and TLS SNI stay on the original name. This does not patch
``socket.getaddrinfo`` and does not depend on which event-loop DNS the process
uses.

``proxy``, ``mounts`` and environment proxies are rejected. They would skip
this transport.
"""

from __future__ import annotations

import socket
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

import httpcore
import httpx

from ar_common.egress_policy import canonical_ip, decide, host_of

if TYPE_CHECKING:
    from typing import Any

_MODES = frozenset({"external", "cluster"})
_REJECTED = frozenset({"proxy", "mounts", "trust_env"})
_allow: ContextVar[list[str] | None] = ContextVar("egress_http_allow", default=None)
_dial: ContextVar[dict[str, str] | None] = ContextVar("egress_http_dial", default=None)


class EgressDenied(httpx.TransportError):
    """The egress decision refused this URL before a socket was opened."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def bind_allow(hosts: list[str]) -> Token[list[str] | None]:
    """Remember the allowlist for clients created later in this task."""
    return _allow.set(list(hosts))


def reset_allow(token: Token[list[str] | None]) -> None:
    """Drop the allowlist bound by :func:`bind_allow`."""
    _allow.reset(token)


def current_allow() -> list[str]:
    """The allowlist bound for this task, or an empty list."""
    bound = _allow.get()
    return [] if bound is None else list(bound)


def resolve_host(host: str) -> list[str]:
    """Addresses for ``host``. A failed lookup raises :class:`EgressDenied`.

    Tests replace this function. Production uses ``socket.getaddrinfo`` once,
    in the caller, and the socket then dials the returned address.
    """
    literal = canonical_ip(host)
    if literal is not None:
        return [str(literal)]
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise EgressDenied(f"{host} could not be resolved") from exc
    found: list[str] = []
    for info in infos:
        address = info[4][0]
        parsed = canonical_ip(str(address))
        if parsed is not None and str(parsed) not in found:
            found.append(str(parsed))
    if not found:
        raise EgressDenied(f"{host} could not be resolved")
    return found


def pinned_host(host: str, allow: list[str] | None = None) -> str:
    """The address a non-HTTP client dials. Open mode keeps the name.

    Closed mode resolves once and returns the approved address, or raises.
    """
    from ar_common.egress_policy import closed_egress  # noqa: PLC0415

    if not closed_egress():
        return host
    return approved_address(host, allow)


def approved_address(
    host: str,
    allow: list[str] | None = None,
    *,
    mode: str = "external",
    loopback: bool | None = None,
) -> str:
    """Resolve ``host`` and return the address a non-HTTP client may dial."""
    addresses = resolve_host(host)
    problem = _judge(host, addresses, allow or current_allow(), mode, loopback)
    if problem is not None:
        raise EgressDenied(problem)
    return addresses[0]


def guard(
    url: str,
    allow: list[str] | None = None,
    *,
    mode: str = "external",
    loopback: bool | None = None,
) -> str | None:
    """Why ``url`` may not be called, or None when it may. No socket is opened."""
    host = host_of(url)
    if not host:
        return "url must name a host"
    try:
        addresses = resolve_host(host)
    except EgressDenied as exc:
        return exc.reason
    return _judge(host, addresses, allow or [], mode, loopback)


class _PinSync(httpcore.NetworkBackend):
    """Dial the address this task approved. Never look the name up again."""

    def __init__(self) -> None:
        self._inner = httpcore.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: object = None,
    ) -> httpcore.NetworkStream:
        return self._inner.connect_tcp(
            _target(host),
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,  # type: ignore[arg-type]
        )

    def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: object = None
    ) -> httpcore.NetworkStream:
        del path, timeout, socket_options
        raise httpcore.ConnectError("a unix socket is not an egress path")

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


class _PinAsync(httpcore.AsyncNetworkBackend):
    """Async dial of the address this task approved."""

    def __init__(self) -> None:
        self._inner = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109
        local_address: str | None = None,
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        return await self._inner.connect_tcp(
            _target(host),
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,  # type: ignore[arg-type]
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109
        socket_options: object = None,
    ) -> httpcore.AsyncNetworkStream:
        del path, timeout, socket_options
        raise httpcore.ConnectError("a unix socket is not an egress path")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class EgressTransport(httpx.BaseTransport):
    """Sync transport. One pool, one decision, one pinned dial per request."""

    def __init__(self, *, allow: list[str], mode: str, loopback: bool | None) -> None:
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._inner = httpx.HTTPTransport(trust_env=False)
        self._inner._pool._network_backend = _PinSync()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        token = _approve(request, self._allow, self._mode, self._loopback)
        try:
            return self._inner.handle_request(request)
        finally:
            _dial.reset(token)

    def close(self) -> None:
        self._inner.close()


class AsyncEgressTransport(httpx.AsyncBaseTransport):
    """Async transport. The pin is on this task, not on ``socket.getaddrinfo``."""

    def __init__(self, *, allow: list[str], mode: str, loopback: bool | None) -> None:
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._inner = httpx.AsyncHTTPTransport(trust_env=False)
        self._inner._pool._network_backend = _PinAsync()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        token = _approve(request, self._allow, self._mode, self._loopback)
        try:
            return await self._inner.handle_async_request(request)
        finally:
            _dial.reset(token)

    async def aclose(self) -> None:
        await self._inner.aclose()


class _CheckingTransport(httpx.BaseTransport):
    """Run the decision, then hand the original request to a test double."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
    ) -> None:
        self._inner = inner
        self._allow = allow
        self._mode = mode
        self._loopback = loopback

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        token = _approve(request, self._allow, self._mode, self._loopback)
        try:
            return self._inner.handle_request(request)
        finally:
            _dial.reset(token)

    def close(self) -> None:
        self._inner.close()


class _CheckingAsyncTransport(httpx.AsyncBaseTransport):
    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
    ) -> None:
        self._inner = inner
        self._allow = allow
        self._mode = mode
        self._loopback = loopback

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        token = _approve(request, self._allow, self._mode, self._loopback)
        try:
            return await self._inner.handle_async_request(request)
        finally:
            _dial.reset(token)

    async def aclose(self) -> None:
        await self._inner.aclose()


def sync_client(
    *,
    allow: list[str] | None = None,
    mode: str = "external",
    loopback: bool | None = None,
    timeout: float | httpx.Timeout | None = None,
    transport: httpx.BaseTransport | None = None,
    follow_redirects: bool = False,
    **kwargs: Any,
) -> httpx.Client:
    """A client whose transport refuses a URL the egress decision rejects."""
    _reject(kwargs)
    chosen = current_allow() if allow is None else list(allow)
    checked: httpx.BaseTransport
    if transport is None:
        checked = EgressTransport(allow=chosen, mode=_mode(mode), loopback=loopback)
    else:
        checked = _CheckingTransport(transport, allow=chosen, mode=_mode(mode), loopback=loopback)
    return httpx.Client(
        transport=checked, timeout=timeout, follow_redirects=follow_redirects, trust_env=False
    )


def async_client(
    *,
    allow: list[str] | None = None,
    mode: str = "external",
    loopback: bool | None = None,
    timeout: float | httpx.Timeout | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    follow_redirects: bool = False,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """Async form of :func:`sync_client`."""
    _reject(kwargs)
    chosen = current_allow() if allow is None else list(allow)
    checked: httpx.AsyncBaseTransport
    if transport is None:
        checked = AsyncEgressTransport(allow=chosen, mode=_mode(mode), loopback=loopback)
    else:
        checked = _CheckingAsyncTransport(
            transport, allow=chosen, mode=_mode(mode), loopback=loopback
        )
    return httpx.AsyncClient(
        transport=checked, timeout=timeout, follow_redirects=follow_redirects, trust_env=False
    )


def get(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One GET through :func:`sync_client`."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout, **kwargs) as client:
        return client.get(url)


def post(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One POST through :func:`sync_client`."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout, **kwargs) as client:
        return client.post(url)


http_get = get
http_post = post


def _reject(kwargs: dict[str, Any]) -> None:
    found = sorted(_REJECTED.intersection(kwargs))
    if found:
        raise EgressDenied(
            f"{', '.join(found)} is not accepted; it would skip the egress transport"
        )


def _mode(mode: str) -> str:
    if mode not in _MODES:
        raise ValueError(f"unknown egress mode {mode}")
    return mode


def _approve(
    request: httpx.Request,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
) -> Token[dict[str, str] | None]:
    host = request.url.host
    if not host:
        raise EgressDenied("url must name a host")
    addresses = resolve_host(host)
    problem = _judge(host, addresses, allow, mode, loopback)
    if problem is not None:
        raise EgressDenied(problem)
    return _dial.set({host: addresses[0]})


def _target(host: str) -> str:
    pins = _dial.get()
    chosen = pins.get(host) if pins else None
    if not chosen:
        raise httpcore.ConnectError(f"no approved address for {host}")
    return chosen


def _judge(
    host: str,
    addresses: list[str],
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
) -> str | None:
    if mode == "cluster":
        problem = decide(
            host,
            [host],
            resolve=lambda _name: addresses,
            closed=False,
            loopback=True if loopback is None else loopback,
            check_private=True,
            named_private=True,
        )
        if problem is not None and "private" not in problem and "deny list" not in problem:
            return problem
        if any(not _cluster_ip(item) for item in addresses):
            return f"{host} is a public address and a cluster client will not dial it"
        return None
    return decide(
        host,
        allow,
        resolve=lambda _name: addresses,
        closed=None,
        loopback=loopback,
        check_private=True,
    )


def _cluster_ip(address: str) -> bool:
    ip = canonical_ip(address)
    if ip is None:
        return False
    if ip.is_unspecified or ip.is_link_local:
        return False
    return bool(ip.is_private or ip.is_loopback)
