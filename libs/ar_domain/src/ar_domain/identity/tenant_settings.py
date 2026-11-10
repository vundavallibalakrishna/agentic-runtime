"""Read one tenant's settings from the store. Spec: docs/03-specs/02-identity-tenancy.md §3.1."""

import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


def settings_for(store: Any, tenant_id: object) -> dict[str, object]:
    """Return the settings row for ``tenant_id`` or an empty dict.

    Never fall back to another tenant's row. A missing row means the defaults in
    ``ar_contracts.tenants.TenantSettings`` apply.
    """
    rows = getattr(store, "tenant_settings", None)
    if not isinstance(rows, dict) or tenant_id is None:
        return {}
    key: object = tenant_id
    if not isinstance(key, uuid.UUID):
        try:
            key = uuid.UUID(str(tenant_id))
        except ValueError:
            return {}
    row = rows.get(key)
    return row if isinstance(row, dict) else {}


def feature_enabled(store: Any, tenant_id: object, name: str, *, default: bool) -> bool:
    """One ``features.<name>`` flag for the calling tenant, or its default."""
    value = section(settings_for(store, tenant_id), "features").get(name)
    return bool(value) if isinstance(value, bool) else default


def permissions_for_features(
    store: Any, tenant_id: object, permissions: frozenset[str]
) -> frozenset[str]:
    """Permissions after feature flags. Pack permissions are added separately."""
    del store, tenant_id
    return permissions


def section(settings: dict[str, object], *path: str) -> dict[str, object]:
    """Walk nested settings sections; return an empty dict when any level is missing."""
    current: object = settings
    for name in path:
        if not isinstance(current, dict):
            return {}
        current = current.get(name)
    return current if isinstance(current, dict) else {}


def dev_tenant_settings() -> dict[str, object]:
    """Settings the ``dev`` tenant starts with, wherever it is created.

    The database seed, the in-memory identity store and the demo catalogue must agree,
    or the first settings patch replaces one copy with another's defaults.
    """
    from ar_contracts.tenants import TenantSettings  # noqa: PLC0415

    return TenantSettings().model_dump(by_alias=False)
