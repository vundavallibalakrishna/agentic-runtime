"""A provider or alias test reports what the endpoint did. Task: M38a-T02a."""

import uuid
from typing import TYPE_CHECKING

import pytest

from ar_domain.chat.service import ChatService, demo_id
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_testing.stand_in import StandIn

SCRIPT_SET = "m38a-t02a"
UNREACHABLE = "http://127.0.0.1:9/v1"


def _alias_on(store: ChatService, base_url: str, kind: str = "openai_compatible") -> uuid.UUID:
    tenant = demo_id("tenant")
    provider = store.create_provider(
        tenant, f"probe-{uuid.uuid4().hex[:6]}", kind, base_url, platform=False, api_key="key"
    )
    model = store.create_model(
        tenant, uuid.UUID(str(provider["id"])), "probe-model", "probe-model", "chat", platform=False
    )
    alias = store.create_alias(
        tenant,
        f"probe-{uuid.uuid4().hex[:6]}",
        "chat",
        uuid.UUID(str(model["id"])),
        platform=False,
    )
    return uuid.UUID(str(alias["id"]))


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["openai_compatible", "fake"])
async def test_an_alias_test_on_a_dead_endpoint_is_a_failure(kind: str) -> None:
    store = demo_store(allow_loopback=True)
    alias_id = _alias_on(store, UNREACHABLE, kind)
    tested = await store.test_alias(
        demo_id("tenant"), alias_id, [{"role": "user", "content": "ping"}]
    )
    assert tested["ok"] is False
    assert tested["output"] == "provider test failed"
    assert "fake:" not in str(tested), "no answer may be made up for a dead endpoint"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["openai_compatible", "fake"])
async def test_a_provider_test_on_a_dead_endpoint_is_a_failure(kind: str) -> None:
    store = demo_store(allow_loopback=True)
    provider = store.create_provider(
        demo_id("tenant"), "dead", kind, UNREACHABLE, platform=False, api_key="key"
    )
    tested = await store.test_provider(demo_id("tenant"), uuid.UUID(str(provider["id"])))
    assert tested["ok"] is False
    assert tested["output"] == "provider test failed"


@pytest.mark.asyncio
async def test_an_alias_test_returns_what_the_model_said(stand_in: StandIn) -> None:
    stand_in.script(
        SCRIPT_SET, [{"match": {"contains": "ping"}, "respond": {"text": "pong from the model"}}]
    )
    store = demo_store(allow_loopback=True)
    alias_id = _alias_on(store, stand_in.base_url(SCRIPT_SET))
    tested = await store.test_alias(
        demo_id("tenant"), alias_id, [{"role": "user", "content": "ping"}]
    )
    assert tested["ok"] is True
    assert tested["output"] == "pong from the model"
    assert tested["model_id"] == "probe-model"


@pytest.mark.asyncio
async def test_a_provider_test_passes_when_the_model_answers_pong(stand_in: StandIn) -> None:
    stand_in.script(SCRIPT_SET, [{"match": {"contains": "pong"}, "respond": {"text": "pong"}}])
    store = demo_store(allow_loopback=True)
    provider = store.create_provider(
        demo_id("tenant"),
        "live",
        "openai_compatible",
        stand_in.base_url(SCRIPT_SET),
        platform=False,
        api_key="key",
    )
    provider_id = uuid.UUID(str(provider["id"]))
    # With no model yet, the provider is asked which models it serves. No name is made up.
    listed = await store.test_provider(demo_id("tenant"), provider_id)
    assert listed["ok"] is True
    assert str(listed["output"]).startswith("The provider answered and lists ")
    assert listed["model_id"] == ""
    store.create_model(
        demo_id("tenant"), provider_id, "probe-model", "probe-model", "chat", platform=False
    )
    tested = await store.test_provider(demo_id("tenant"), provider_id)
    assert tested == {**tested, "ok": True, "output": "pong", "model_id": "probe-model"}


@pytest.mark.asyncio
async def test_an_embedding_model_is_tested_with_an_embedding(stand_in: StandIn) -> None:
    store = demo_store(allow_loopback=True)
    tenant = demo_id("tenant")
    provider = store.create_provider(
        tenant, "vectors", "openai_compatible", stand_in.base_url(SCRIPT_SET), platform=False
    )
    provider_id = uuid.UUID(str(provider["id"]))
    model = store.create_model(
        tenant, provider_id, "probe-embed", "probe-embed", "embedding", platform=False
    )
    alias = store.create_alias(
        tenant, "probe-embed", "embedding", uuid.UUID(str(model["id"])), platform=False
    )
    tested = await store.test_alias(tenant, uuid.UUID(str(alias["id"])), [])
    assert tested == {**tested, "ok": True, "output": "Returned a vector of 1024 numbers."}
    assert tested["model_id"] == "probe-embed"
    # A provider that only serves embeddings is tested the same way.
    assert (await store.test_provider(tenant, provider_id))["ok"] is True
    dead = store.create_provider(tenant, "gone", "openai_compatible", UNREACHABLE, platform=False)
    lost = store.create_model(
        tenant, uuid.UUID(str(dead["id"])), "lost-embed", "lost-embed", "embedding", platform=False
    )
    lost_alias = store.create_alias(
        tenant, "lost-embed", "embedding", uuid.UUID(str(lost["id"])), platform=False
    )
    failed = await store.test_alias(tenant, uuid.UUID(str(lost_alias["id"])), [])
    assert failed["ok"] is False
    assert "did not answer" in str(failed["output"])
