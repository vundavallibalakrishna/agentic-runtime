"""Factories for M2 rows."""

import uuid
from typing import TYPE_CHECKING

from ar_common.ids import new_id

if TYPE_CHECKING:
    from typing import Any


def provider_factory(**overrides: Any) -> dict[str, Any]:
    """Return a model provider payload."""
    row: dict[str, Any] = {
        "id": new_id(),
        "tenant_id": uuid.uuid4(),
        "name": "local",
        "kind": "fake",
        "base_url": "http://127.0.0.1:8099/v1",
        "status": "active",
    }
    row.update(overrides)
    return row


def agent_factory(**overrides: Any) -> dict[str, Any]:
    """Return an agent payload."""
    row: dict[str, Any] = {
        "id": new_id(),
        "tenant_id": uuid.uuid4(),
        "slug": "assistant",
        "name": "Assistant",
        "visibility": "tenant",
        "status": "published",
    }
    row.update(overrides)
    return row
