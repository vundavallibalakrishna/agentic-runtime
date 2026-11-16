"""The only HTTP client the platform uses to leave the process.

Every outbound call goes through :func:`sync_client` or :func:`async_client`.
The transport runs :func:`ar_common.egress_policy.decide` and, on a real socket,
connects to the addresses that decision resolved so a later DNS answer cannot
redirect the call. A test double (any transport the caller passes in) is still
checked, and is not rewritten.

``mode="cluster"`` is for this install's own services. It allows a private or
loopback address and refuses a public or metadata address. ``mode="external"``
is everything else: models, connectors, search, webhooks, knowledge, OAuth.
"""

from __future__ import annotations

import socket
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from typing import Any

import httpx

from ar_common.egress_policy import canonical_ip, decide, dial_addresses, host_of

_MODES = frozenset({"external", "cluster"})
_allow: ContextVar[list[str] | None] = ContextVar("egress_http_allow", default=None)
_pins: ContextVar[dict[str, str] | None] = ContextVar("egress_http_pins", default=None)
_real_getaddrinfo = socket.getaddrinfo


def _pinned_getaddrinfo(  # noqa: PLR0917
    host: str,
    port: int | str | None,
    family: int = 0,
    type: int = 0,  # noqa: A002
    proto: int = 0,
    flags: int = 0,
) -> list[tuple[int, int, int, str, tuple[str, int] | tuple[str, int, int, int]]]:
    """Resolve ``host`` to the address ``decide`` already approved."""
    pins = _pins.get()
    chosen = pins.get(host) if pins else None
    return _real_getaddrinfo(chosen or host, port, family, type, proto, flags)  # type: ignore[return-value]


socket.getaddrinfo = _pinned_getaddrinfo  # type: ignore[assignment]


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


class EgressDenied(httpx.TransportError):
    """The egress decision refused this URL before a socket was opened."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class EgressTransport(httpx.BaseTransport):
    """Sync transport. ``pin`` is false when the inner transport is a test double."""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
        pin: bool,
    ) -> None:
        self._inner = inner
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._pin = pin

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        rewritten = _prepare(request, self._allow, self._mode, self._loopback, pin=self._pin)
        return self._inner.handle_request(rewritten)

    def close(self) -> None:
        self._inner.close()


class AsyncEgressTransport(httpx.AsyncBaseTransport):
    """Async transport with the same decision as :class:`EgressTransport`."""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        allow: list[str],
        mode: str,
        loopback: bool | None,
        pin: bool,
    ) -> None:
        self._inner = inner
        self._allow = allow
        self._mode = mode
        self._loopback = loopback
        self._pin = pin

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        rewritten = _prepare(request, self._allow, self._mode, self._loopback, pin=self._pin)
        return await self._inner.handle_async_request(rewritten)

    async def aclose(self) -> None:
        await self._inner.aclose()


def guard(
    url: str,
    allow: list[str] | None = None,
    *,
    mode: str = "external",
    loopback: bool | None = None,
) -> str | None:
    """Why ``url`` may not be called, or None when it may. No socket is opened."""
    host = host_of(url)
    return _reason(host, allow or [], mode, loopback, resolve_names=False)


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
    inner = transport or httpx.HTTPTransport()
    chosen = current_allow() if allow is None else list(allow)
    wrapped = EgressTransport(
        inner,
        allow=chosen,
        mode=_mode(mode),
        loopback=loopback,
        pin=transport is None,
    )
    return cast(
        "httpx.Client",
        _open(
            httpx.Client,
            transport=wrapped,
            timeout=timeout,
            follow_redirects=follow_redirects,
            **kwargs,
        ),
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
    inner = transport or httpx.AsyncHTTPTransport()
    chosen = current_allow() if allow is None else list(allow)
    wrapped = AsyncEgressTransport(
        inner,
        allow=chosen,
        mode=_mode(mode),
        loopback=loopback,
        pin=transport is None,
    )
    return cast(
        "httpx.AsyncClient",
        _open(
            httpx.AsyncClient,
            transport=wrapped,
            timeout=timeout,
            follow_redirects=follow_redirects,
            **kwargs,
        ),
    )


def _open(cls: Any, **kwargs: Any) -> Any:
    """Build a client. A test double that replaces httpx does not take our transport."""
    module = str(getattr(cls, "__module__", ""))
    if module.startswith("httpx"):
        return cls(**kwargs)
    slim = {key: value for key, value in kwargs.items() if key != "transport"}
    try:
        return cls(**slim)
    except TypeError:
        timeout = slim.get("timeout")
        if timeout is not None:
            return cls(timeout)
        raise


def get(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One GET through :func:`sync_client`."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout) as client:
        return client.get(url, **kwargs)


def post(url: str, *, allow: list[str] | None = None, **kwargs: Any) -> httpx.Response:
    """One POST through :func:`sync_client`."""
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout) as client:
        return client.post(url, **kwargs)


http_get = get
http_post = post


def _mode(mode: str) -> str:
    if mode not in _MODES:
        raise ValueError(f"unknown egress mode {mode}")
    return mode


def _reason(
    host: str,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
    *,
    resolve_names: bool,
) -> str | None:
    if mode == "cluster":
        return _cluster_reason(host, loopback=loopback, resolve_names=resolve_names)
    return decide(
        host,
        allow,
        closed=None,
        loopback=loopback,
        check_private=resolve_names,
    )


def _cluster_reason(  # noqa: PLR0911
    host: str, *, loopback: bool | None, resolve_names: bool
) -> str | None:
    """In-cluster calls may be private. A public or metadata address is refused."""
    if not host:
        return "url must name a host"
    problem = decide(
        host,
        [host],
        closed=False,
        loopback=True if loopback is None else loopback,
        check_private=resolve_names,
        named_private=True,
    )
    if problem is not None and "private address" not in problem and "deny list" not in problem:
        return problem
    if not resolve_names:
        literal = canonical_ip(host)
        if (
            literal is not None
            and not (literal.is_private or literal.is_loopback or literal.is_link_local)
            and not literal.is_unspecified
        ):
            return f"{host} is a public address and a cluster client will not dial it"
        return None
    _error, found = dial_addresses(host, [host], closed=False, loopback=True, named_private=True)
    if not found:
        return _error or f"{host} could not be resolved"
    if any(not _cluster_ip(item) for item in found):
        return f"{host} is a public address and a cluster client will not dial it"
    return None


def _cluster_ip(address: str) -> bool:
    ip = canonical_ip(address)
    if ip is None:
        return False
    if ip.is_unspecified or ip.is_link_local or ip.is_multicast or ip.is_reserved:
        return bool(ip.is_loopback or ip.is_private)
    return bool(ip.is_private or ip.is_loopback)


def _prepare(
    request: httpx.Request,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
    *,
    pin: bool,
) -> httpx.Request:
    host = request.url.host
    problem = _reason(host, allow, mode, loopback, resolve_names=False)
    if problem is not None:
        raise EgressDenied(problem)
    if pin and host:
        _error, addresses = _pinned(host, allow, mode, loopback)
        if _error is not None and "could not be resolved" not in _error:
            raise EgressDenied(_error)
        if addresses:
            current = dict(_pins.get() or {})
            current[host] = addresses[0]
            _pins.set(current)
    return request


def _pinned(
    host: str,
    allow: list[str],
    mode: str,
    loopback: bool | None,  # noqa: FBT001
) -> tuple[str | None, list[str]]:
    if mode == "cluster":
        problem = _cluster_reason(host, loopback=loopback, resolve_names=True)
        if problem is not None:
            return problem, []
        return dial_addresses(host, [host], closed=False, loopback=True, named_private=True)
    problem, addresses = dial_addresses(host, allow, loopback=loopback)
    if problem is not None and "could not be resolved" in problem:
        return None, []
    return problem, addresses


def _pinned_request(request: httpx.Request, ip: str) -> httpx.Request:
    """Connect to ``ip`` and keep the original host for Host and SNI."""
    original = request.url.host
    port = request.url.port
    host_header = original if port in {None, 80, 443} else f"{original}:{port}"
    url = request.url.copy_with(host=ip)
    headers = list(request.headers.items())
    replaced = [(key, value) for key, value in headers if key.lower() != "host"]
    replaced.append(("host", host_header))
    extensions: dict[str, object] = dict(request.extensions)
    extensions["sni_hostname"] = original
    return httpx.Request(
        request.method,
        url,
        headers=replaced,
        content=request.content,
        extensions=extensions,
    )
