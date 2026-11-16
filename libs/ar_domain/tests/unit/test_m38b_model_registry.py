"""Rules for changing and removing providers, models and aliases. Task: M38b-T07a."""

import uuid

import pytest

from ar_common.errors import ArError, ConflictError, NotFoundError
from ar_domain.chat.service import ChatService


def _registry() -> tuple[ChatService, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """A tenant with one provider, one model and the alias ``reasoning``."""
    store = ChatService(allow_loopback=True)
    tenant = uuid.uuid4()
    provider = store.create_provider(
        tenant, "Main", "openai_compatible", "http://127.0.0.1:9/v1", platform=False, api_key="k1"
    )
    provider_id = uuid.UUID(str(provider["id"]))
    model = store.create_model(
        tenant, provider_id, "Main chat", "vendor/chat", "chat", platform=False
    )
    model_id = uuid.UUID(str(model["id"]))
    alias = store.create_alias(tenant, "reasoning", "chat", model_id, platform=False)
    return store, tenant, provider_id, model_id, uuid.UUID(str(alias["id"]))


def test_a_new_store_has_no_registry_and_a_tenant_builds_its_own() -> None:
    store, tenant, provider_id, model_id, alias_id = _registry()
    assert [row["name"] for row in store.list_providers(tenant)] == ["Main"]
    assert "api_key" not in store.list_providers(tenant)[0]
    assert store.list_providers(uuid.uuid4()) == []
    assert store.providers[provider_id]["api_key"] == "k1"
    assert store.aliases[alias_id]["primary_model_id"] == model_id


def test_a_provider_is_renamed_repointed_and_given_a_new_key() -> None:
    store, tenant, provider_id, _model_id, _alias_id = _registry()
    changed = store.update_provider(
        tenant,
        provider_id,
        platform=False,
        name="Primary",
        base_url="http://127.0.0.1:9/v2",
        api_key="k2",
    )
    assert (changed["name"], changed["base_url"]) == ("Primary", "http://127.0.0.1:9/v2")
    assert "api_key" not in changed
    assert store.providers[provider_id]["api_key"] == "k2"
    strict = ChatService()
    other = uuid.uuid4()
    created = strict.create_provider(
        other, "Cloud", "openai_compatible", "https://models.example.com/v1", platform=False
    )
    with pytest.raises(ArError, match="not allowed"):
        strict.update_provider(
            other, uuid.UUID(str(created["id"])), platform=False, base_url="http://127.0.0.1:9/v1"
        )


def test_things_are_removed_from_the_outside_in() -> None:
    store, tenant, provider_id, model_id, alias_id = _registry()
    with pytest.raises(ConflictError, match="still has models: Main chat"):
        store.delete_provider(tenant, provider_id, platform=False)
    with pytest.raises(ConflictError, match="still use this model: reasoning"):
        store.delete_model(tenant, model_id, platform=False)
    second = store.create_model(
        tenant, provider_id, "Spare", "vendor/spare", "chat", platform=False
    )
    second_id = uuid.UUID(str(second["id"]))
    store.update_alias(tenant, alias_id, second_id, platform=False, fallback_model_ids=[model_id])
    # A model that is only a fallback is still in use.
    with pytest.raises(ConflictError, match="still use this model: reasoning"):
        store.delete_model(tenant, model_id, platform=False)
    store.delete_alias(tenant, alias_id, platform=False)
    store.delete_model(tenant, model_id, platform=False)
    store.delete_model(tenant, second_id, platform=False)
    store.delete_provider(tenant, provider_id, platform=False)
    assert (store.providers, store.models, store.aliases) == ({}, {}, {})


def test_a_model_is_renamed_repriced_and_retargeted() -> None:
    store, tenant, _provider_id, model_id, _alias_id = _registry()
    changed = store.update_model(
        tenant,
        model_id,
        platform=False,
        name="Main chat v2",
        upstream_model="vendor/chat-2",
        price_input_micros_per_mtok=300_000,
        price_output_micros_per_mtok=900_000,
        request_options={"temperature": 0.1},
    )
    assert changed["name"] == "Main chat v2"
    assert changed["upstream_model"] == "vendor/chat-2"
    assert store.model_cost(tenant, "reasoning", 1_000_000, 1_000_000)[0] == 1_200_000
    assert store.request_options(tenant, "reasoning") == {"temperature": 0.1}


def test_another_tenant_cannot_see_or_change_any_of_it() -> None:
    store, _tenant, provider_id, model_id, alias_id = _registry()
    stranger = uuid.uuid4()
    for attempt in (
        lambda: store.update_provider(stranger, provider_id, platform=False, name="x"),
        lambda: store.delete_provider(stranger, provider_id, platform=False),
        lambda: store.update_model(stranger, model_id, platform=False, name="x"),
        lambda: store.delete_model(stranger, model_id, platform=False),
        lambda: store.update_alias(stranger, alias_id, model_id, platform=False),
        lambda: store.delete_alias(stranger, alias_id, platform=False),
        lambda: store.create_model(stranger, provider_id, "x", "x", "chat", platform=False),
        lambda: store.create_alias(stranger, "fast", "chat", model_id, platform=False),
    ):
        with pytest.raises(NotFoundError):
            attempt()
    assert store.providers[provider_id]["name"] == "Main"


async def test_a_store_without_a_database_keeps_its_registry_on_refresh() -> None:
    store, _tenant, provider_id, _model_id, _alias_id = _registry()
    await store.refresh_models()
    assert provider_id in store.providers


def test_an_alias_points_only_at_models_of_its_own_kind() -> None:
    store, tenant, provider_id, model_id, alias_id = _registry()
    embedder = store.create_model(
        tenant, provider_id, "Embedder", "vendor/embed", "embedding", platform=False
    )
    embedder_id = uuid.UUID(str(embedder["id"]))
    with pytest.raises(ArError, match="of kind chat, and Embedder is of kind embedding"):
        store.update_alias(tenant, alias_id, embedder_id, platform=False)
    with pytest.raises(ArError, match="Choose a model of kind chat"):
        store.update_alias(
            tenant, alias_id, model_id, platform=False, fallback_model_ids=[embedder_id]
        )
    with pytest.raises(ArError, match="of kind embedding, and Main chat is of kind chat"):
        store.create_alias(tenant, "embed", "embedding", model_id, platform=False)
    created = store.create_alias(tenant, "embed", "embedding", embedder_id, platform=False)
    assert store.aliases[uuid.UUID(str(created["id"]))]["primary_model_id"] == embedder_id


def test_an_alias_a_published_agent_names_is_not_removed() -> None:
    from ar_domain.agents.service import AgentLifecycle

    store, tenant, _provider_id, _model_id, alias_id = _registry()
    AgentLifecycle(store).ensure_builtins(tenant, uuid.uuid4())
    with pytest.raises(ConflictError, match="published agents use this alias: Assistant"):
        store.delete_alias(tenant, alias_id, platform=False)
    assert alias_id in store.aliases
