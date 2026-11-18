"""HTTP between services of this install.

Cluster egress allows the private addresses Docker assigns on the install
network. Each call carries ``X-AR-Internal`` (empty when the install has no
shared secret). A tenant's model or any other public host stays on the
external client.
"""

from __future__ import annotations

import ipaddress
import os
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from ar_common.egress_http import async_client, sync_client
from ar_common.internal_auth import headers_from_env

if TYPE_CHECKING:
    from typing import Any

    import httpx

# Hostnames of this install's own services. A URL whose host is one of these
# is an internal hop even when an env file still says localhost.
_SERVICE_HOSTS = frozenset(
    {
        "api",
        "channels",
        "ingest-worker",
        "mcp-gateway",
        "mcp-openapi",
        "mcp-sql",
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
    "AR_MCP_OPENAPI_URL",
    "AR_MCP_SQL_URL",
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


def _private_host(host: str) -> bool:
    """True for loopback names and private or loopback addresses."""
    if host in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local


def is_internal_service(url: str) -> bool:
    """True when ``url`` names a service of this install.

    A Docker service name is internal. A configured service URL is internal
    only when its host is a private or loopback address. A public hostname
    that happens to be the configured Qdrant or model host stays on the
    external client.
    """
    host = service_host(url)
    if not host:
        return False
    if host in _SERVICE_HOSTS:
        return True
    if not _private_host(host):
        return False
    for name in _SERVICE_ENV:
        configured = os.environ.get(name, "").strip()
        if configured and service_host(configured) == host:
            return True
    return False


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


def client_for(
    url: str, *, timeout: float | None = None, allow: list[str] | None = None
) -> httpx.Client:
    """Cluster client for an internal service, external client otherwise."""
    if is_internal_service(url):
        return internal_sync_client(timeout=timeout)
    return sync_client(timeout=timeout, allow=_allow_with_host(allow, url))


def post(url: str, **kwargs: Any) -> httpx.Response:
    """POST through the internal client when ``url`` is one of our services."""
    if is_internal_service(url):
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
    **kwargs: Any,
) -> httpx.Response:
    """POST to an internal service in cluster mode, or to anyone else externally."""
    if is_internal_service(url):
        headers = signed_headers("POST", url, kwargs.pop("headers", None))
        async with internal_async_client(timeout=timeout_s) as client:
            return await client.post(url, headers=headers, **kwargs)
    headers = kwargs.pop("headers", None)
    async with async_client(timeout=timeout_s, allow=_allow_with_host(allow, url)) as client:
        return await client.post(url, headers=headers, **kwargs)
