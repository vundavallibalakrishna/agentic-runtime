"""Factories for identity rows used by isolation tests."""

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id

if TYPE_CHECKING:
    from typing import Any


def user_factory(**overrides: Any) -> dict[str, Any]:
    """Return a user insert payload."""
    row: dict[str, Any] = {
        "id": new_id(),
        "tenant_id": uuid.uuid4(),
        "idp_subject": "user@example.com",
        "email": "user@example.com",
        "display_name": "User",
        "status": "active",
    }
    row.update(overrides)
    return row


def tenant_factory(**overrides: Any) -> dict[str, Any]:
    """Return a tenant insert payload."""
    row: dict[str, Any] = {
        "id": new_id(),
        "slug": "acme",
        "name": "Acme",
        "status": "active",
    }
    row.update(overrides)
    return row
