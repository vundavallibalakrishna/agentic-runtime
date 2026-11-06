"""Provider, model and alias changes are saved, and every process sees them.

Task: M38b-T07a. Renaming or deleting a provider and deleting a model used to change one
process's memory only: they came back after a restart, and a worker kept using them.
"""

import os
import subprocess
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from ar_domain.chat.service import ChatService
from ar_domain.durable.bind import bind_store
from ar_domain.identity.seed import apply
from ar_domain.models import registry

pytestmark = pytest.mark.integration

_KEYS = "SELECT count(*) FROM secret_refs WHERE tenant_id = :t AND name = :name"


def _async_url(postgres_url: str) -> str:
    url = postgres_url.replace("postgresql+psycopg", "postgresql+asyncpg", 1)
    return url.replace("postgresql+psycopg2", "postgresql+asyncpg", 1)


@pytest.fixture(scope="module")
def database_url(postgres_url: str) -> str:
    url = _async_url(postgres_url)
    env = os.environ.copy()
    env["AR_DATABASE_URL"] = url
    subprocess.run(
        ["uv", "run", "alembic", "-c", "libs/ar_domain/alembic.ini", "upgrade", "head"],  # noqa: S607
        check=True,
        env=env,
    )
    return url


async def _process(database_url: str) -> ChatService:
    """A product store attached to the dev tenant, as one API or worker process holds it."""
    store = ChatService()
    assert await bind_store(store, database_url, tenant_slug="dev") is not None
    return store


async def _count(engine: object, sql: str, **params: object) -> int:
    async with engine.connect() as connection:  # type: ignore[attr-defined]
        return int(await connection.scalar(text(sql), params) or 0)


async def test_changes_are_saved_and_reach_every_process(
    database_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(registry, "_keyring", lambda: ({"k1": b"t" * 32}, "k1"))
    engine = create_async_engine(database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        await apply(session)
    api = await _process(database_url)
    worker = await _process(database_url)
    tenant = api.tenant_binding.tenant_id  # type: ignore[union-attr]
    who = {"actor_id": str(uuid.uuid4()), "actor_type": "user"}

    # The admin registers a provider, a model and an alias with a fallback.
    provider = api.create_provider(
        tenant,
        "Main",
        "openai_compatible",
        "https://models.example.com/v1",
        platform=False,
        api_key="first-key",
    )
    provider_id = uuid.UUID(str(provider["id"]))
    await registry.save_provider(
        api.durable_engine, api.providers[provider_id], api_key="first-key", **who
    )
    model_id = uuid.UUID(
        str(
            api.create_model(
                tenant, provider_id, "Main chat", "vendor/chat", "chat", platform=False
            )["id"]
        )
    )
    spare_id = uuid.UUID(
        str(
            api.create_model(tenant, provider_id, "Spare", "vendor/spare", "chat", platform=False)[
                "id"
            ]
        )
    )
    for saved in (model_id, spare_id):
        await registry.save_model(api.durable_engine, api.models[saved], **who)
    alias_id = uuid.UUID(
        str(
            api.create_alias(
                tenant, "drafting", "chat", model_id, platform=False, fallback_model_ids=[spare_id]
            )["id"]
        )
    )
    await registry.save_alias(api.durable_engine, api.aliases[alias_id], **who)

    # A worker that was already running sees all of it before its next turn.
    assert provider_id not in worker.providers
    await worker.refresh_models()
    assert worker.providers[provider_id]["name"] == "Main"
    assert worker.aliases[alias_id]["fallback_model_ids"] == [spare_id]
    assert await registry.read_api_key(engine, provider_id) == "first-key"

    # A rename, a new address and a new key are saved. The old key is gone, not orphaned.
    api.update_provider(
        tenant,
        provider_id,
        platform=False,
        name="Primary",
        base_url="https://models.example.com/v2",
        api_key="second-key",
    )
    await registry.save_provider(
        api.durable_engine, api.providers[provider_id], api_key="second-key", **who
    )
    await worker.refresh_models()
    assert worker.providers[provider_id]["name"] == "Primary"
    assert worker.providers[provider_id]["base_url"] == "https://models.example.com/v2"
    assert await worker._provider_key(worker.providers[provider_id]) == "second-key"
    assert await _count(engine, _KEYS, t=tenant, name=f"model-provider-{provider_id}") == 1

    # A model's name and price are saved.
    api.update_model(
        tenant, model_id, platform=False, name="Main chat v2", price_input_micros_per_mtok=250_000
    )
    await registry.save_model(api.durable_engine, api.models[model_id], **who)
    restarted = await _process(database_url)
    assert restarted.models[model_id]["name"] == "Main chat v2"
    assert restarted.models[model_id]["price_input_micros_per_mtok"] == 250_000
    assert restarted.providers[provider_id]["api_key"] == "second-key"

    # Another tenant's provider is never read into this tenant's process.
    other = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO tenants (id, slug, name, plan_id) "
                "SELECT :id, 'other-co', 'Other', plan_id FROM tenants WHERE id = :mine"
            ),
            {"id": other, "mine": tenant},
        )
        await connection.execute(
            text(
                "INSERT INTO model_providers (id, tenant_id, name, kind, base_url) "
                "VALUES (:id, :tenant, 'Theirs', 'openai_compatible', 'https://x.example/v1')"
            ),
            {"id": uuid.uuid4(), "tenant": other},
        )
    await worker.refresh_models()
    names = {row["name"] for row in worker.providers.values()}
    assert "Primary" in names
    assert "Theirs" not in names

    # Deleting is saved too, from the outside in, and the other processes drop the rows.
    api.delete_alias(tenant, alias_id, platform=False)
    await registry.delete_alias(api.durable_engine, alias_id, **who)
    for gone in (model_id, spare_id):
        api.delete_model(tenant, gone, platform=False)
        await registry.delete_model(api.durable_engine, gone, **who)
    api.delete_provider(tenant, provider_id, platform=False)
    await registry.delete_provider(api.durable_engine, provider_id, **who)
    await worker.refresh_models()
    after_restart = await _process(database_url)
    for store in (worker, after_restart):
        assert provider_id not in store.providers
        assert not {model_id, spare_id} & set(store.models)
        assert alias_id not in store.aliases
    assert await _count(engine, _KEYS, t=tenant, name=f"model-provider-{provider_id}") == 0

    # Each change left an audit row, in order.
    async with engine.connect() as connection:
        actions = [
            row[0]
            for row in await connection.execute(
                text(
                    "SELECT action FROM audit_events WHERE tenant_id = :t "
                    "AND target_id = ANY(:ids) ORDER BY tenant_seq"
                ),
                {
                    "t": tenant,
                    "ids": [str(provider_id), str(model_id), str(spare_id), str(alias_id)],
                },
            )
        ]
    assert actions == [
        "model_provider.created",
        "model.created",
        "model.created",
        "model_alias.created",
        "model_provider.updated",
        "model.updated",
        "model_alias.deleted",
        "model.deleted",
        "model.deleted",
        "model_provider.deleted",
    ]
    for process in (api, worker, restarted, after_restart):
        if process.durable_engine is not None:
            await process.durable_engine.dispose()
    await engine.dispose()
