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
    tested = await store.test_provider(demo_id("tenant"), uuid.UUID(str(provider["id"])))
    assert tested == {**tested, "ok": True, "output": "pong"}
