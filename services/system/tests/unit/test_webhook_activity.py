"""The webhook activity reads the tenant unit, not the empty process handle.

Label: unit
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest

from ar_domain.readmodel.model import RepositoryReadModel
from ar_system.routines_store import bind_store
from ar_system.workflows.webhook_run import deliver_webhook_activity
from ar_testing.demo import demo_store


@pytest.mark.asyncio
async def test_the_activity_loads_the_delivery_from_the_tenant_unit() -> None:
    tenant = uuid.uuid4()
    delivery_id = uuid.uuid4()
    unit = demo_store()
    unit.webhook_deliveries[delivery_id] = {
        "id": delivery_id,
        "tenant_id": tenant,
        "status": "succeeded",
    }
    model = RepositoryReadModel(database_url="postgresql://unused")

    async def resolve(payload: object) -> uuid.UUID | None:
        assert isinstance(payload, dict)
        assert payload["tenant_id"] == str(tenant)
        return tenant

    @asynccontextmanager
    async def opened(tenant_id: uuid.UUID, **_kwargs: object) -> object:
        assert tenant_id == tenant
        yield unit

    model.resolve_tenant = resolve  # type: ignore[method-assign]
    model.open = opened  # type: ignore[method-assign]
    bind_store(model)
    try:
        result = await deliver_webhook_activity(
            {"delivery_id": str(delivery_id), "tenant_id": str(tenant)}
        )
    finally:
        bind_store(demo_store())
    assert result["status"] == "succeeded"
