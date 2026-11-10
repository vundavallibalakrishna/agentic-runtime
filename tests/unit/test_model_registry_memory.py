"""Unit coverage for the model registry writes. Proof label: unit.

The statements run against a session double. No database and no network.
"""

from __future__ import annotations

import base64
import uuid
from types import SimpleNamespace

import orjson
import pytest
from pydantic import SecretStr

from ar_common.errors import ArError
from ar_common.settings import BaseServiceSettings, set_settings
from ar_domain.models.registry import (
    _as_int,
    _keyring,
    _secret_aad,
    _secret_path,
    delete_alias,
    delete_model,
    delete_provider,
    load_registry,
    lookup_upstream,
    read_api_key,
    save_alias,
    save_model,
    save_provider,
)


class _Result:
    def __init__(self, row: object | None = None) -> None:
        self.row = row

    def first(self) -> object | None:
        return self.row

    def mappings(self) -> _Result:
        return self


class _Scalars:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class _Session:
    lookup: dict[str, object] | None = None

    def __init__(self, found: object | None, rows: list[list[object]]) -> None:
        self.found = found
        self.rows = rows
        self.calls = 0

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def begin(self) -> _Session:
        return self

    async def get(self, _model: object, _key: object) -> object | None:
        return self.found

    def add(self, _obj: object) -> None:
        return None

    async def delete(self, _obj: object) -> None:
        return None

    async def flush(self) -> None:
        return None

    async def execute(self, statement: object, *_args: object, **_kwargs: object) -> _Result:
        sql = str(statement)
        if "upstream_model" in sql and _Session.lookup is not None:
            return _Result(_Session.lookup)
        return _Result()

    async def scalar(self, *_args: object, **_kwargs: object) -> object | None:
        return None

    async def scalars(self, *_args: object, **_kwargs: object) -> _Scalars:
        rows = self.rows[self.calls] if self.calls < len(self.rows) else []
        self.calls += 1
        return _Scalars(rows)


def _install(
    monkeypatch: pytest.MonkeyPatch, found: object | None, rows: list[list[object]]
) -> None:
    def factory(*_args: object, **_kwargs: object) -> _Session:
        return _Session(found, rows)

    monkeypatch.setattr("ar_domain.models.registry.AsyncSession", factory)


def _ids() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


@pytest.mark.unit
async def test_registry_writes_without_a_database(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant, provider_id, model_id = _ids()
    alias_id = uuid.uuid4()
    _install(monkeypatch, None, [])
    engine = object()
    await save_provider(None, {"id": provider_id}, api_key=None, actor_id="a")
    await save_provider(
        engine,  # type: ignore[arg-type]
        {
            "id": provider_id,
            "tenant_id": tenant,
            "name": "Local",
            "kind": "openai",
            "base_url": "http://models",
            "timeout_s": 30,
        },
        api_key=None,
        actor_id="a",
        actor_type="admin",
    )
    await delete_provider(None, provider_id, actor_id="a")
    await delete_provider(engine, provider_id, actor_id="a")  # type: ignore[arg-type]
    await save_model(
        engine,  # type: ignore[arg-type]
        {
            "id": model_id,
            "tenant_id": tenant,
            "provider_id": provider_id,
            "name": "chat",
            "upstream_model": "chat",
            "kind": "chat",
            "capabilities": ["text"],
        },
        actor_id="a",
    )
    await delete_model(engine, model_id, actor_id="a")  # type: ignore[arg-type]
    await save_alias(
        engine,  # type: ignore[arg-type]
        {
            "id": alias_id,
            "tenant_id": tenant,
            "alias": "reasoning",
            "kind": "chat",
            "primary_model_id": model_id,
            "fallback_model_ids": [model_id],
            "default_params": {"temperature": 0},
        },
        actor_id="a",
    )
    await delete_alias(engine, alias_id, actor_id="a")  # type: ignore[arg-type]
    assert await read_api_key(engine, provider_id) == ""  # type: ignore[arg-type]


@pytest.mark.unit
async def test_registry_updates_an_existing_row(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant, provider_id, model_id = _ids()
    existing = SimpleNamespace(
        name="Old",
        kind="openai",
        base_url="http://old",
        api_key_ref_id=None,
        tenant_id=tenant,
        upstream_model="old",
        price_input_micros_per_mtok=0,
        price_output_micros_per_mtok=0,
        embedding_dimensions=None,
        capabilities=[],
        request_options={},
        primary_model_id=model_id,
        fallback_model_ids=[],
        default_params={},
        alias="reasoning",
    )
    _install(monkeypatch, existing, [])
    engine = object()
    await save_provider(
        engine,  # type: ignore[arg-type]
        {
            "id": provider_id,
            "tenant_id": tenant,
            "name": "New",
            "kind": "openai",
            "base_url": "http://new",
        },
        api_key=None,
        actor_id="a",
    )
    await save_model(
        engine,  # type: ignore[arg-type]
        {
            "id": model_id,
            "tenant_id": tenant,
            "provider_id": provider_id,
            "name": "chat",
            "upstream_model": "chat",
            "request_options": {},
        },
        actor_id="a",
    )
    alias_id = uuid.uuid4()
    await save_alias(
        engine,  # type: ignore[arg-type]
        {
            "id": alias_id,
            "tenant_id": tenant,
            "alias": "reasoning",
            "primary_model_id": model_id,
        },
        actor_id="a",
    )
    await delete_provider(engine, provider_id, actor_id="a")  # type: ignore[arg-type]
    await delete_model(engine, model_id, actor_id="a")  # type: ignore[arg-type]
    await delete_alias(engine, alias_id, actor_id="a")  # type: ignore[arg-type]
    assert existing.upstream_model == "chat"


@pytest.mark.unit
async def test_load_registry_replaces_the_store(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = uuid.uuid4()
    provider_id = uuid.uuid4()
    model_id = uuid.uuid4()
    alias_id = uuid.uuid4()
    provider = SimpleNamespace(
        id=provider_id,
        tenant_id=tenant,
        name="Local",
        kind="openai",
        base_url="http://models",
        status="active",
        timeout_s=30,
        health={},
        api_key_ref_id=None,
    )
    model = SimpleNamespace(
        id=model_id,
        tenant_id=tenant,
        provider_id=provider_id,
        name="chat",
        upstream_model="chat",
        kind="chat",
        capabilities=["text"],
        price_input_micros_per_mtok=1,
        price_output_micros_per_mtok=2,
        request_options={},
        embedding_dimensions=None,
        status="active",
    )
    alias = SimpleNamespace(
        id=alias_id,
        tenant_id=tenant,
        alias="reasoning",
        kind="chat",
        primary_model_id=model_id,
        fallback_model_ids=[],
        default_params={},
        status="active",
    )
    _install(monkeypatch, None, [[provider], [model], [alias]])
    store = SimpleNamespace(providers={uuid.uuid4(): {"name": "stale"}}, models={}, aliases={})
    await load_registry(object(), store, tenant)  # type: ignore[arg-type]
    assert provider_id in store.providers
    assert store.providers[provider_id]["name"] == "Local"
    assert model_id in store.models
    assert alias_id in store.aliases
    secret = uuid.uuid4()
    assert str(secret) in _secret_path(tenant, secret)
    assert _secret_aad(tenant, secret)
    assert _as_int(True, 3) == 3
    assert _as_int(4, 3) == 4
    bare = BaseServiceSettings(_env_file=None)
    set_settings(bare)
    with pytest.raises(ArError):
        _keyring()
    raw = orjson.dumps({"k1": base64.b64encode(b"k" * 32).decode()}).decode()
    set_settings(
        BaseServiceSettings(
            _env_file=None,
            db_encryption_keys=SecretStr(raw),
            db_encryption_active_key="k1",
        )
    )
    ring, active = _keyring()
    assert active == "k1" and "k1" in ring
    assert await lookup_upstream("") is None
    assert await lookup_upstream("fake-chat") is None
    _Session.lookup = {
        "id": provider_id,
        "base_url": "http://models",
        "kind": "openai",
        "timeout_s": 30,
        "upstream_model": "chat",
        "request_options": {},
    }

    def engine() -> object:
        return object()

    monkeypatch.setattr("ar_domain.models.registry._shared_engine", engine)
    found = await lookup_upstream("chat")
    assert found is not None
    assert found.upstream_model == "chat"
    _Session.lookup = None
