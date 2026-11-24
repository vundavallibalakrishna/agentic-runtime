"""HTTP between services of this install.

A call is internal only when its scheme, host and port are one of the
configured service URLs. That call uses the cluster client and carries
``X-AR-Internal``. A URL a tenant saved is never internal and is never signed,
including when its host is one of this install's service names or a loopback
address.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ar_common.egress_http import async_client, sync_client
from ar_common.internal_auth import headers_from_env

if TYPE_CHECKING:
    from typing import Any

    import httpx

# Hostnames of this install's own services. A tenant URL on one of these
# names is refused. It is not, by itself, an internal hop.
_SERVICE_HOSTS = frozenset(
    {
        "api",
        "channels",
        "ingest-worker",
        "mcp-gateway",
        "model-gateway",
        "opa",
        "otel",
        "qdrant",
        "runtime-worker",
        "sandbox-manager",
        "seaweedfs",
        "squid",
        "system-worker",
    }
)

_SERVICE_ENV = (
    "AR_API_INTERNAL_URL",
    "AR_CHANNELS_URL",
    "AR_DOC_INTEL_URL",
    "AR_INGEST_URL",
    "AR_MCP_GATEWAY_URL",
    "AR_MODEL_GATEWAY_URL",
    "AR_OCR_URL",
    "AR_OPA_URL",
    "AR_QDRANT_URL",
    "AR_SANDBOX_MANAGER_URL",
    "AR_SYSTEM_URL",
)


def service_host(url: str) -> str:
    """The hostname of ``url``, or an empty string."""
    return (urlsplit(url).hostname or "").lower()


def _endpoint(url: str) -> tuple[str, str, int] | None:
    """Scheme, host and port. A missing port is 443 for https and 80 for http."""
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        return None
    default = 443 if scheme == "https" else 80
    port = default if parts.port is None else parts.port
    return scheme, host, port


def configured_endpoints() -> frozenset[tuple[str, str, int]]:
    """Service URLs from the environment, matched on scheme, host and port."""
    found: set[tuple[str, str, int]] = set()
    for name in _SERVICE_ENV:
        configured = os.environ.get(name, "").strip()
        if not configured:
            continue
        endpoint = _endpoint(configured)
        if endpoint is not None:
            found.add(endpoint)
    return frozenset(found)


def _cluster_host(host: str) -> bool:
    """A Docker service name or a private address. A public DNS name is not."""
    if host in _SERVICE_HOSTS:
        return True
    from ar_common.egress_policy import canonical_ip  # noqa: PLC0415

    address = canonical_ip(host)
    if address is None:
        return False
    return bool(address.is_private or address.is_loopback or address.is_link_local)


def is_internal_service(url: str) -> bool:
    """True only when ``url`` is one configured service endpoint on the cluster.

    The match is scheme, host and port. A public hostname that is configured
    as Qdrant or a model host stays on the external client. A name that only
    shares a label with a service, or the right host on another port, is not
    internal and is not signed.
    """
    endpoint = _endpoint(url)
    if endpoint is None or endpoint not in configured_endpoints():
        return False
    return _cluster_host(endpoint[1])


def tenant_loopback_denied(url: str) -> str | None:
    """Loopback is refused for a tenant URL outside dev and ci.

    The dev and test runs reach a stand-in on this machine. Staging and
    production do not, even when ``AR_EGRESS_ALLOW_LOOPBACK`` was left on.
    """
    from ar_common.egress_policy import canonical_ip  # noqa: PLC0415
    from ar_common.settings import EnvName, get_settings  # noqa: PLC0415

    if get_settings().env in {EnvName.DEV, EnvName.CI}:
        return None
    endpoint = _endpoint(url)
    if endpoint is None:
        return None
    host = endpoint[1]
    if host in {"localhost", "localhost.localdomain"}:
        return "that URL is a loopback address"
    address = canonical_ip(host)
    if address is not None and address.is_loopback:
        return "that URL is a loopback address"
    return None


def tenant_supplied_url_denied(url: str) -> str | None:
    """Why a tenant-supplied URL must not be called, or None when it may.

    Install service names and this install's configured service endpoints are
    refused on any port. The URL is never treated as internal and never signed.
    Loopback is refused by the egress check unless the install explicitly
    allows it, which it does not outside dev.
    """
    endpoint = _endpoint(url)
    if endpoint is None:
        return "that URL is not an http or https URL"
    _scheme, host, _port = endpoint
    if host in _SERVICE_HOSTS:
        return "that URL names a service of this install"
    if is_internal_service(url):
        return "that URL is a service of this install"
    return None


def signed_headers(method: str, url: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    """Caller headers plus ``X-AR-Internal`` when this install has a secret."""
    merged = dict(headers or {})
    for key, value in headers_from_env(method, url).items():
        merged.setdefault(key, value)
    return merged


def _allow_with_host(allow: list[str] | None, url: str) -> list[str]:
    """The caller's allow list, with this URL's host named explicitly.

    A model the tenant saved is a host they asked us to call. Naming it lets
    ``AR_EGRESS_ALLOW_NAMED_PRIVATE`` reach an in-network provider. A public
    provider is unchanged.
    """
    listed = list(allow or [])
    host = service_host(url)
    if host and host not in listed:
        listed.append(host)
    return listed


def internal_post(url: str, **kwargs: Any) -> httpx.Response:
    """One POST on the cluster client, signed for this install."""
    timeout = kwargs.pop("timeout", None)
    headers = signed_headers("POST", url, kwargs.pop("headers", None))
    with sync_client(mode="cluster", timeout=timeout) as client:
        return client.post(url, headers=headers, **kwargs)


def internal_get(url: str, **kwargs: Any) -> httpx.Response:
    """One GET on the cluster client, signed for this install."""
    timeout = kwargs.pop("timeout", None)
    headers = signed_headers("GET", url, kwargs.pop("headers", None))
    with sync_client(mode="cluster", timeout=timeout) as client:
        return client.get(url, headers=headers, **kwargs)


def internal_sync_client(**kwargs: Any) -> httpx.Client:
    """A cluster client. Callers add the HMAC header themselves."""
    kwargs["mode"] = "cluster"
    return sync_client(**kwargs)


def internal_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """Async form of :func:`internal_sync_client`."""
    kwargs["mode"] = "cluster"
    return async_client(**kwargs)


def _refuse_supplied(url: str) -> None:
    """Refuse a tenant URL before a socket is opened."""
    from ar_common.egress_http import EgressDenied  # noqa: PLC0415

    reason = tenant_supplied_url_denied(url) or tenant_loopback_denied(url)
    if reason is not None:
        raise EgressDenied(reason)


def client_for(
    url: str,
    *,
    timeout: float | None = None,
    allow: list[str] | None = None,
    supplied: bool = False,
) -> httpx.Client:
    """Cluster client for a configured service, external client otherwise.

    ``supplied`` is a URL a tenant saved. It is never a cluster client and
    never carries the install HMAC, even when it names one of our services.
    """
    if supplied:
        _refuse_supplied(url)
        return sync_client(timeout=timeout, allow=_allow_with_host(allow, url))
    if is_internal_service(url):
        return internal_sync_client(timeout=timeout)
    return sync_client(timeout=timeout, allow=_allow_with_host(allow, url))


def post(url: str, **kwargs: Any) -> httpx.Response:
    """POST through the internal client when ``url`` is a configured service."""
    supplied = bool(kwargs.pop("supplied", False))
    if supplied:
        _refuse_supplied(url)
    elif is_internal_service(url):
        return internal_post(url, **kwargs)

    allow = _allow_with_host(kwargs.pop("allow", None), url)
    timeout = kwargs.pop("timeout", None)
    with sync_client(allow=allow, timeout=timeout) as client:
        return client.post(url, **kwargs)


async def async_post(
    url: str,
    *,
    allow: list[str] | None = None,
    timeout_s: float | None = None,
    supplied: bool = False,
    **kwargs: Any,
) -> httpx.Response:
    """POST to a configured service in cluster mode, or to anyone else externally.

    ``supplied`` is a tenant URL: external client, no HMAC, and refused when
    it names an install service or a loopback address.
    """
    if supplied:
        _refuse_supplied(url)
    elif is_internal_service(url):
        headers = signed_headers("POST", url, kwargs.pop("headers", None))
        async with internal_async_client(timeout=timeout_s) as client:
            return await client.post(url, headers=headers, **kwargs)
    headers = kwargs.pop("headers", None)
    async with async_client(timeout=timeout_s, allow=_allow_with_host(allow, url)) as client:
        return await client.post(url, headers=headers, **kwargs)
