"""Memory mode when Postgres is absent or not migrated yet."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from ar_api.deps import get_identity, get_tenant_writer
from ar_api.middleware.durable import DurableMiddleware
from ar_common.settings import EnvName
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.db.context import Principal
from ar_domain.durable.bind import SchemaNotReadyError


def _scope(store: ChatService, path: str) -> dict[str, object]:
    app = SimpleNamespace(
        state=SimpleNamespace(
            chat=store,
            settings=SimpleNamespace(
                env=EnvName.CI,
                database_url="postgresql+asyncpg://ar:ar@localhost:1/ar",
                model_gateway_url="",
                temporal_address="localhost:1",
            ),
            demo_tenant_id=None,
            demo_user_id=None,
        )
    )
    return {"type": "http", "path": path, "app": app, "method": "GET", "headers": [], "state": {}}


def _request(store: ChatService) -> Request:
    principal = Principal(
        kind="user",
        id=str(demo_id("admin")),
        tenant_id=demo_id("tenant"),
        email="admin@dev.local",
    )
    app = SimpleNamespace(state=SimpleNamespace(chat=store))
    return Request(
        {
            "type": "http",
            "app": app,
            "headers": [],
            "state": {"principal": principal, "request_id": "req-memory"},
        }
    )


@pytest.mark.parametrize("path", ["/healthz", "/readyz", "/metrics"])
async def test_probes_do_not_bind(path: str, monkeypatch: pytest.MonkeyPatch) -> None:
    called = False

    async def bind_store(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("ar_domain.durable.bind.should_bind", lambda: True)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", bind_store)
    store = ChatService()
    sent: list[dict[str, object]] = []

    async def app(scope: object, receive: object, send: object) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def capture(message: dict[str, object]) -> None:
        sent.append(message)

    await DurableMiddleware(app)(_scope(store, path), AsyncMock(), capture)
    assert sent and sent[0]["status"] == 200
    assert called is False
    assert getattr(store, "_bind_attempted", False) is False


async def test_missing_schema_retries_and_unavailable_database_seeds_showcase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = {"n": 0}

    async def bind_store(*_args: object, **_kwargs: object) -> object:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise SchemaNotReadyError()
        return None

    monkeypatch.setattr("ar_domain.durable.bind.should_bind", lambda: True)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", bind_store)
    store = ChatService()

    async def app(scope: object, receive: object, send: object) -> None:
        del scope, receive
        await send({"type": "http.response.start", "status": 204, "headers": []})

    middleware = DurableMiddleware(app)
    await middleware(_scope(store, "/api/v1/conversations"), AsyncMock(), AsyncMock())
    assert getattr(store, "_bind_attempted", False) is False
    await middleware(_scope(store, "/api/v1/conversations"), AsyncMock(), AsyncMock())
    assert store._bind_attempted is True
    assert attempts["n"] == 2
    titles = {row.get("title") for row in store.conversations.values()}
    assert "Weekly status for the platform" in titles


async def test_memory_identity_lists_users_and_enables_widget() -> None:
    store = ChatService()
    store._bind_attempted = True
    request = _request(store)
    async for identity in get_identity(request):
        users = await identity.store.list_users(status="active", query="admin")
        assert users[0].email == "admin@dev.local"
        assert (await identity.current_user()).display_name == "Dev Admin"
    async for writer in get_tenant_writer(request):
        tenant = await writer.update_tenant(
            name=None, settings_patch={"features": {"widget": True}}
        )
    assert tenant.settings["features"]["widget"] is True
    same = getattr(store, "_memory_identity", None)
    assert same is not None
    assert await same.get_user_by_email("missing@dev.local") is None
    assert await same.get_plan(demo_id("other")) is None
