"""Which tenants a password matches. Used by the sign-in picker and the switcher."""

from __future__ import annotations

from typing import Any  # noqa: TC003

from ar_domain.identity.passwords import verify_password
from ar_domain.identity.recovery import people_for


def password_matches(store: Any, email: str, password: str) -> list[dict[str, object]]:
    """Tenants whose stored hash matches. The hash is not returned."""
    found: list[dict[str, object]] = []
    for row in people_for(store, email):
        secret = str(row.get("password_hash") or "")
        if not verify_password(secret, password):
            continue
        found.append(
            {
                "tenant_id": str(row.get("tenant_id")),
                "tenant_name": str(row.get("tenant_name") or row.get("tenant_id")),
                "user_id": str(row.get("user_id")),
                "email": str(row.get("email")),
                "display_name": str(row.get("display_name") or row.get("email")),
                "permissions": _strings(row.get("permissions")),
                "roles": _strings(row.get("roles")),
            }
        )
    found.sort(key=lambda item: str(item["tenant_name"]))
    return found


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def memberships(store: Any, email: str) -> list[dict[str, str]]:
    """Tenants that already know this address. No password check."""
    rows = [
        {
            "tenant_id": str(row.get("tenant_id")),
            "tenant_name": str(row.get("tenant_name") or row.get("tenant_id")),
            "user_id": str(row.get("user_id")),
        }
        for row in people_for(store, email)
    ]
    rows.sort(key=lambda item: item["tenant_name"])
    return rows
