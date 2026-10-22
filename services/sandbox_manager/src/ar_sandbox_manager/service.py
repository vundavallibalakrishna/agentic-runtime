"""Sandbox start checks. Spec: docs/03-specs/17-audit-usage-metering.md §2.2."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.usage.service import UsageBook

if TYPE_CHECKING:
    import uuid
    from typing import Any


def assert_sandbox_start(
    store: Any,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    agent_id: uuid.UUID | None,
) -> None:
    """Raise when a new computer would pass the sandbox quota."""
    UsageBook(store).assert_sandbox(tenant_id, user_id, agent_id)
