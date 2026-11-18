"""Tenant allowlist plus the install closed-egress switch."""

from __future__ import annotations

import uuid
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

from ar_common.egress_policy import closed_egress, decide_url

if TYPE_CHECKING:
    from typing import Any

_tenant: ContextVar[object] = ContextVar("egress_tenant", default=None)


def bind_tenant(tenant_id: object) -> Token[object]:
    """Remember which tenant an AWS call belongs to. Reset the token afterwards."""
    return _tenant.set(tenant_id)


def reset_tenant(token: Token[object]) -> None:
    """Drop the tenant bound by ``bind_tenant``."""
    _tenant.reset(token)


def current_tenant() -> object:
    """The tenant bound for the current call, if a connector set one."""
    return _tenant.get()


def tenant_hosts(store: Any, tenant_id: object) -> list[str]:
    """Hosts this tenant has listed. Missing settings mean an empty list."""
    book = getattr(store, "tenant_settings", None)
    if not isinstance(book, dict):
        return []
    key: object = tenant_id
    if isinstance(tenant_id, str):
        try:
            key = uuid.UUID(tenant_id)
        except ValueError:
            key = tenant_id
    row = book.get(key)
    if not isinstance(row, dict) and isinstance(tenant_id, uuid.UUID):
        row = book.get(str(tenant_id))
    if not isinstance(row, dict):
        return []
    allow = row.get("egress_allowlist")
    if not isinstance(allow, list):
        return []
    return [str(item) for item in allow if str(item).strip()]


def dial_allow(store: Any, tenant_id: object) -> list[str]:
    """Allowlist passed to ``guard_public``.

    Closed mode drops the star, so only listed hosts are dialled. Otherwise the
    star keeps today's public-host behaviour and exact names may be private.
    """
    hosts = tenant_hosts(store, tenant_id)
    if closed_egress():
        return hosts
    return ["*", *hosts]


def residency_of(store: Any, tenant_id: object) -> str:
    """The residency that applies to this tenant.

    ``AR_DATA_RESIDENCY`` wins for the whole install. Otherwise the value is the
    tenant row loaded into ``tenant_profiles``. ``in`` does not block a cloud model.
    """
    from ar_common.settings import get_settings  # noqa: PLC0415

    configured = get_settings().data_residency.strip()
    if configured:
        return configured
    profiles = getattr(store, "tenant_profiles", None)
    if isinstance(profiles, dict) and tenant_id is not None:
        row = profiles.get(tenant_id)
        if not isinstance(row, dict):
            row = profiles.get(str(tenant_id))
        if isinstance(row, dict) and str(row.get("data_residency") or "").strip():
            return str(row["data_residency"])
    return "in"


def model_refusal(
    store: Any,
    tenant_id: object,
    url: str,
    *,
    residency: str = "in",
    loopback: bool | None = None,
) -> str | None:
    """Why a model or embedding URL may not be called.

    ``residency`` of ``cluster`` requires a private or loopback address.
    ``in`` does not, so an existing cloud provider is unchanged. Closed egress
    applies either way: the host must be listed. A tenant URL that names an
    install service or a loopback address is refused before either of those.
    """
    from ar_common.internal_http import (  # noqa: PLC0415
        tenant_loopback_denied,
        tenant_supplied_url_denied,
    )

    blocked = tenant_supplied_url_denied(url) or tenant_loopback_denied(url)
    if blocked is not None:
        return blocked
    hosts = tenant_hosts(store, tenant_id)
    if closed_egress():
        problem = decide_url(url, hosts, closed=True, check_private=True, loopback=loopback)
        if problem is not None:
            return problem
    elif residency != "cluster":
        return decide_url(url, [], closed=False, check_private=False, loopback=loopback)
    if residency == "cluster":
        return _cluster(url)
    return None


def _cluster(url: str) -> str | None:
    """Refuse a public address. A private or loopback address is the local path."""
    from ar_common.egress_policy import (  # noqa: PLC0415
        host_of,
        metadata_address,
        private_address,
        resolved_addresses,
    )

    host = host_of(url)
    if not host:
        return "url must name a host"
    if metadata_address(host) or host in {"169.254.169.254", "metadata.google.internal"}:
        return f"{host} is a metadata address and is denied"
    found = resolved_addresses(host)
    if not found:
        return f"{host} could not be resolved"
    if any(metadata_address(item) for item in found):
        return f"{host} is a metadata address and is denied"
    if all(private_address(item) for item in found):
        return None
    return f"{host} is a public address. data_residency cluster only calls a private model."
