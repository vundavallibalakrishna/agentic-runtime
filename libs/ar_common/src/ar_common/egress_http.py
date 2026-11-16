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

import asyncio
import ipaddress
import os
import socket
import ssl
import threading
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

import httpcore
import httpx

from ar_common.egress_policy import canonical_ip, decide, host_of

if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Any

_MODES = frozenset({"external", "cluster"})
_REJECTED = frozenset({"proxy", "mounts", "trust_env", "transport"})
_CLIENT_KEYS = frozenset(
    {"verify", "http2", "cert", "headers", "cookies", "auth", "base_url", "max_redirects", "limits"}
)
_pins_local = threading.local()
_allow: ContextVar[list[str] | None] = ContextVar("egress_http_allow", default=None)
_dial: ContextVar[dict[str, list[str]] | None] = ContextVar("egress_http_dial", default=None)


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


def host_key(host: str) -> str:
    """Lower-case IDNA form. A literal address is left in the form to dial."""
    text = host.strip().strip("[]").rstrip(".").lower()
    try:
        ipaddress.ip_address(text)
    except ValueError:
        parsed = canonical_ip(text)
        if parsed is not None:
            return str(parsed)
        try:
            return text.encode("idna").decode("ascii")
        except UnicodeError:
            return text
    return text


def resolve_host(host: str) -> list[str]:
    """Addresses to dial for ``host``. A failed lookup raises :class:`EgressDenied`.

    Tests replace this function. A literal is returned as written, so a NAT64
    address is dialled as IPv6. The policy decision unwraps it separately.
    """
    name = host_key(host)
    try:
        ipaddress.ip_address(name)
    except ValueError:
        pass
    else:
        return [name]
    try:
        infos = socket.getaddrinfo(name, None)
    except socket.gaierror as exc:
        raise EgressDenied(f"{name} could not be resolved") from exc
    found: list[str] = []
    for info in infos:
        address = str(info[4][0]).split("%", 1)[0]
        if address and address not in found:
            found.append(address)
    if not found:
        raise EgressDenied(f"{name} could not be resolved")
    return found


async def resolve_host_async(host: str, timeout: float | None) -> list[str]:  # noqa: ASYNC109
    """``resolve_host`` off the event loop. ``timeout`` bounds the wait."""
    try:
        if timeout is None:
            return await asyncio.to_thread(resolve_host, host)
        return await asyncio.wait_for(asyncio.to_thread(resolve_host, host), timeout)
    except TimeoutError as exc:
        raise EgressDenied(f"{host_key(host)} could not be resolved") from exc


def pinned_host(host: str, allow: list[str] | None = None) -> str:
    """The address a non-HTTP client dials. Open mode keeps the name.

    Closed mode resolves once and returns the approved address, or raises.
    """
    from ar_common.egress_policy import closed_egress  # noqa: PLC0415

    if not closed_egress():
        return host
    return approved_address(host, allow)


def approved_addresses(
    host: str,
    allow: list[str] | None = None,
    *,
    mode: str = "external",
    loopback: bool | None = None,
) -> list[str]:
    """Resolve ``host`` and return every address a non-HTTP client may dial."""
    name = host_key(host)
    addresses = resolve_host(name)
    problem = _judge(name, addresses, allow or current_allow(), mode, loopback)
    if problem is not None:
        raise EgressDenied(problem)
    return addresses


def approved_address(
    host: str,
    allow: list[str] | None = None,
    *,
    mode: str = "external",
    loopback: bool | None = None,
) -> str:
    """The first approved address for ``host``."""
    return approved_addresses(host, allow, mode=mode, loopback=loopback)[0]


@contextmanager
def pin_dns(host: str, addresses: list[str]) -> Iterator[None]:
    """While this thread looks up ``host``, return ``addresses`` and nothing else.

    The URL keeps the hostname, so TLS checks that name. The socket dials the
    approved address. Other threads are unchanged.
    """
    name = host_key(host)
    current = getattr(_pins_local, "pins", None)
    stacked = dict(current) if isinstance(current, dict) else {}
    stacked[name] = list(addresses)
    _pins_local.pins = stacked
    _install_pin()
    try:
        yield
    finally:
        if current is None:
            _pins_local.pins = None
        else:
            _pins_local.pins = current


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
        return _dial_one(
            self._inner,
            host,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
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
        return await _dial_one_async(
            self._inner,
            host,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
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

    def __init__(
        self,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
        timeout: float | None,
        verify: ssl.SSLContext | str | bool,
        http2: bool,
    ) -> None:
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._timeout = timeout
        self._inner = httpx.HTTPTransport(trust_env=False, verify=verify, http2=http2)
        self._inner._pool._network_backend = _PinSync()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        token = _approve(request, self._allow, self._mode, self._loopback, timeout=self._timeout)
        try:
            return self._inner.handle_request(request)
        finally:
            _dial.reset(token)

    def close(self) -> None:
        self._inner.close()


class AsyncEgressTransport(httpx.AsyncBaseTransport):
    """Async transport. The pin is on this task, not on ``socket.getaddrinfo``."""

    def __init__(
        self,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
        timeout: float | None,
        verify: ssl.SSLContext | str | bool,
        http2: bool,
    ) -> None:
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._timeout = timeout
        self._inner = httpx.AsyncHTTPTransport(trust_env=False, verify=verify, http2=http2)
        self._inner._pool._network_backend = _PinAsync()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        token = await _approve_async(
            request, self._allow, self._mode, self._loopback, timeout=self._timeout
        )
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
        token = _approve(request, self._allow, self._mode, self._loopback, timeout=None)
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
        token = await _approve_async(request, self._allow, self._mode, self._loopback, timeout=None)
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
    client_kwargs = _client_kwargs(kwargs)
    _real_transport(transport)
    chosen = current_allow() if allow is None else list(allow)
    verify = _ca_bundle(client_kwargs.pop("verify", True))
    http2 = bool(client_kwargs.pop("http2", False))
    checked: httpx.BaseTransport
    if transport is None:
        checked = EgressTransport(
            allow=chosen,
            mode=_mode(mode),
            loopback=loopback,
            timeout=_seconds(timeout),
            verify=verify,
            http2=http2,
        )
    else:
        checked = _CheckingTransport(transport, allow=chosen, mode=_mode(mode), loopback=loopback)
    return httpx.Client(
        transport=checked,
        timeout=timeout,
        follow_redirects=follow_redirects,
        trust_env=False,
        **client_kwargs,
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
    client_kwargs = _client_kwargs(kwargs)
    _real_transport(transport)
    chosen = current_allow() if allow is None else list(allow)
    verify = _ca_bundle(client_kwargs.pop("verify", True))
    http2 = bool(client_kwargs.pop("http2", False))
    checked: httpx.AsyncBaseTransport
    if transport is None:
        checked = AsyncEgressTransport(
            allow=chosen,
            mode=_mode(mode),
            loopback=loopback,
            timeout=_seconds(timeout),
            verify=verify,
            http2=http2,
        )
    else:
        checked = _CheckingAsyncTransport(
            transport, allow=chosen, mode=_mode(mode), loopback=loopback
        )
    return httpx.AsyncClient(
        transport=checked,
        timeout=timeout,
        follow_redirects=follow_redirects,
        trust_env=False,
        **client_kwargs,
    )


def get(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One GET through :func:`sync_client`. Remaining keywords go to the request."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout) as client:
        return client.get(url, **kwargs)


def post(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One POST through :func:`sync_client`. Remaining keywords go to the request."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout) as client:
        return client.post(url, **kwargs)


http_get = get
http_post = post


def _client_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    found = sorted(_REJECTED.intersection(kwargs))
    if found:
        raise EgressDenied(
            f"{', '.join(found)} is not accepted; it would skip the egress transport"
        )
    unknown = sorted(set(kwargs) - _CLIENT_KEYS)
    if unknown:
        raise TypeError(f"unexpected keyword argument {unknown[0]}")
    return dict(kwargs)


def _real_transport(transport: object) -> None:
    if isinstance(transport, httpx.HTTPTransport | httpx.AsyncHTTPTransport):
        raise EgressDenied("transport is not accepted; it would dial without the pin")


def _mode(mode: str) -> str:
    if mode not in _MODES:
        raise ValueError(f"unknown egress mode {mode}")
    return mode


def _approve(
    request: httpx.Request,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
    *,
    timeout: float | None,
) -> Token[dict[str, list[str]] | None]:
    del timeout
    host = request.url.host
    if not host:
        raise EgressDenied("url must name a host")
    name = host_key(host)
    addresses = resolve_host(name)
    problem = _judge(name, addresses, allow, mode, loopback)
    if problem is not None:
        raise EgressDenied(problem)
    return _dial.set({name: addresses, host: addresses})


async def _approve_async(
    request: httpx.Request,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
    *,
    timeout: float | None,  # noqa: ASYNC109
) -> Token[dict[str, list[str]] | None]:
    host = request.url.host
    if not host:
        raise EgressDenied("url must name a host")
    name = host_key(host)
    addresses = await resolve_host_async(name, timeout)
    problem = _judge(name, addresses, allow, mode, loopback)
    if problem is not None:
        raise EgressDenied(problem)
    return _dial.set({name: addresses, host: addresses})


def _targets(host: str) -> list[str]:
    pins = _dial.get()
    if not pins:
        raise httpcore.ConnectError(f"no approved address for {host}")
    chosen = pins.get(host) or pins.get(host_key(host))
    if not chosen:
        raise httpcore.ConnectError(f"no approved address for {host}")
    return chosen


def _dial_one(
    inner: httpcore.SyncBackend,
    host: str,
    port: int,
    *,
    timeout: float | None,
    local_address: str | None,
    socket_options: object,
) -> httpcore.NetworkStream:
    last: Exception | None = None
    for address in _targets(host):
        try:
            return inner.connect_tcp(
                address,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,  # type: ignore[arg-type]
            )
        except Exception as exc:  # noqa: BLE001 — the next address may answer
            last = exc
    raise last or httpcore.ConnectError(f"no approved address for {host}")


async def _dial_one_async(
    inner: httpcore.AnyIOBackend,
    host: str,
    port: int,
    *,
    timeout: float | None,  # noqa: ASYNC109
    local_address: str | None,
    socket_options: object,
) -> httpcore.AsyncNetworkStream:
    last: Exception | None = None
    for address in _targets(host):
        try:
            return await inner.connect_tcp(
                address,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,  # type: ignore[arg-type]
            )
        except Exception as exc:  # noqa: BLE001 — the next address may answer
            last = exc
    raise last or httpcore.ConnectError(f"no approved address for {host}")


_PIN_INSTALLED = False
_PIN_PREVIOUS: Any = None


def _install_pin() -> None:
    global _PIN_INSTALLED, _PIN_PREVIOUS  # noqa: PLW0603
    if _PIN_INSTALLED and socket.getaddrinfo is _pinned_getaddrinfo:
        return
    _PIN_PREVIOUS = socket.getaddrinfo
    socket.getaddrinfo = _pinned_getaddrinfo  # type: ignore[assignment]
    _PIN_INSTALLED = True


def _pinned_getaddrinfo(  # noqa: PLR0917
    host: str | bytes,
    port: int | str | None,
    family: int = 0,
    type: int = 0,  # noqa: A002
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[int, int, int, str, tuple[object, ...]]]:
    pins = getattr(_pins_local, "pins", None)
    text = host.decode() if isinstance(host, bytes) else str(host)
    chosen = pins.get(host_key(text)) if isinstance(pins, dict) else None
    if chosen:
        return [_answer(address, port) for address in chosen]
    found = _PIN_PREVIOUS(host, port, family, type, proto, flags)
    return list(found)


def _answer(address: str, port: int | str | None) -> tuple[int, int, int, str, tuple[object, ...]]:
    number = int(port or 0)
    if ":" in address:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (address, number, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, number))


def _seconds(timeout: float | httpx.Timeout | None) -> float | None:
    if timeout is None:
        return None
    if isinstance(timeout, int | float):
        return float(timeout)
    connect = getattr(timeout, "connect", None)
    if isinstance(connect, int | float):
        return float(connect)
    return None


def _ca_bundle(verify: object) -> ssl.SSLContext | str | bool:
    """The trust store. ``SSL_CERT_FILE``, ``SSL_CERT_DIR`` and ``AR_CA_BUNDLE`` count."""
    if verify is False:
        return False
    if isinstance(verify, ssl.SSLContext | str):
        return verify
    configured = ""
    try:
        from ar_common.settings import get_settings  # noqa: PLC0415

        configured = str(get_settings().ca_bundle or "")
    except Exception:  # noqa: BLE001 — settings are optional while the process boots
        configured = ""
    if configured:
        return configured
    bundle = os.environ.get("SSL_CERT_FILE") or ""
    if bundle:
        return bundle
    directory = os.environ.get("SSL_CERT_DIR") or ""
    if directory:
        context = ssl.create_default_context()
        context.load_verify_locations(capath=directory)
        return context
    return True


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
