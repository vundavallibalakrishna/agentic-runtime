"""A routine's webhook has no sign-in, so its address says whose data the request reads."""

import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from ar_api.middleware.read_model import ReadModelMiddleware
from ar_domain.readmodel.model import RepositoryReadModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

_TENANT = uuid.uuid4()


class _Model(RepositoryReadModel):
    def __init__(self) -> None:
        super().__init__(database_url="postgresql+asyncpg://unused/unused")
        self.opened: list[uuid.UUID] = []
        self.asked: list[str] = []

    async def tenant_of_hook(self, token: str) -> uuid.UUID | None:
        self.asked.append(token)
        return _TENANT if token == "known-token" else None  # noqa: S105 - an address, not a key

    @asynccontextmanager
    async def open(self, tenant_id: uuid.UUID, **_options: Any) -> AsyncIterator[Any]:
        self.opened.append(tenant_id)
        yield SimpleNamespace(tenant_id=tenant_id)


async def _call(model: _Model, path: str) -> object:
    seen: list[object] = []

    async def app(scope: dict[str, Any], _receive: object, send: Any) -> None:
        seen.append(scope["state"].get("read_unit"))
        await send({"type": "http.response.start", "status": 202, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(_message: dict[str, object]) -> None:
        return None

    async def receive() -> dict[str, object]:
        return {"type": "http.request"}

    scope = {
        "type": "http",
        "path": path,
        "state": {},
        "app": SimpleNamespace(state=SimpleNamespace(chat=model)),
    }
    await ReadModelMiddleware(app)(scope, receive, send)  # type: ignore[arg-type]
    return seen[0]


@pytest.mark.asyncio
async def test_a_webhook_call_reads_the_tenant_that_owns_the_address() -> None:
    model = _Model()
    unit = await _call(model, "/api/v1/hooks/routines/known-token")
    assert getattr(unit, "tenant_id", None) == _TENANT
    assert model.opened == [_TENANT]


@pytest.mark.asyncio
async def test_an_unknown_address_and_other_public_paths_load_no_tenant() -> None:
    model = _Model()
    assert await _call(model, "/api/v1/hooks/routines/nobody") is None
    assert await _call(model, "/api/v1/auth/login") is None
    assert model.opened == []
    assert model.asked == ["nobody"]
