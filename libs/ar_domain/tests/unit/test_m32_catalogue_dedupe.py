"""Durable hydrate must not list the seeded platform catalogue twice."""

import uuid

from ar_domain.chat.service import ChatService, demo_id
from ar_domain.durable.m23 import drop_catalogue_shadows


def test_database_rows_replace_demo_ids_for_the_same_name() -> None:
    store = ChatService()
    db_provider = uuid.uuid4()
    db_chat = uuid.uuid4()
    db_embed = uuid.uuid4()
    db_rerank = uuid.uuid4()
    alias_ids = {name: uuid.uuid4() for name in ("reasoning", "fast", "vision", "embed", "rerank")}
    db_providers = [
        {"id": db_provider, "tenant_id": None, "name": "fake-llm", "kind": "fake", "base_url": "db"}
    ]
    db_models = [
        {
            "id": db_chat,
            "tenant_id": None,
            "provider_id": db_provider,
            "name": "fake-chat",
            "kind": "chat",
        },
        {
            "id": db_embed,
            "tenant_id": None,
            "provider_id": db_provider,
            "name": "fake-embed",
            "kind": "embedding",
        },
        {
            "id": db_rerank,
            "tenant_id": None,
            "provider_id": db_provider,
            "name": "fake-rerank",
            "kind": "rerank",
        },
    ]
    db_aliases = [
        {
            "id": alias_ids["reasoning"],
            "tenant_id": None,
            "alias": "reasoning",
            "kind": "chat",
            "primary_model_id": db_chat,
        },
        {
            "id": alias_ids["fast"],
            "tenant_id": None,
            "alias": "fast",
            "kind": "chat",
            "primary_model_id": db_chat,
        },
        {
            "id": alias_ids["vision"],
            "tenant_id": None,
            "alias": "vision",
            "kind": "chat",
            "primary_model_id": db_chat,
        },
        {
            "id": alias_ids["embed"],
            "tenant_id": None,
            "alias": "embed",
            "kind": "embedding",
            "primary_model_id": db_embed,
        },
        {
            "id": alias_ids["rerank"],
            "tenant_id": None,
            "alias": "rerank",
            "kind": "rerank",
            "primary_model_id": db_rerank,
        },
    ]
    drop_catalogue_shadows(
        store.providers,
        store.models,
        store.aliases,
        db_providers=db_providers,
        db_models=db_models,
        db_aliases=db_aliases,
    )
    for bucket, rows in (
        (store.providers, db_providers),
        (store.models, db_models),
        (store.aliases, db_aliases),
    ):
        for row in rows:
            bucket[row["id"]] = dict(row)

    fake = [row for row in store.providers.values() if row.get("name") == "fake-llm"]
    reasoning = [row for row in store.aliases.values() if row.get("alias") == "reasoning"]
    assert len(fake) == 1
    assert fake[0]["id"] == db_provider
    assert len(reasoning) == 1
    assert reasoning[0]["id"] == alias_ids["reasoning"]
    assert reasoning[0]["primary_model_id"] == db_chat
    assert demo_id("provider") not in store.providers
    assert demo_id("alias-reasoning") not in store.aliases
    assert demo_id("model-chat") not in store.models
