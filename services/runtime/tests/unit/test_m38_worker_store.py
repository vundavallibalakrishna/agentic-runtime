"""The runtime worker builds its store for the environment it runs in. Task: M38-T03."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from ar_common.settings import EnvName
from ar_domain.chat.service import ChatService
from ar_runtime import worker


@pytest.mark.parametrize(("env", "fixtures"), [(EnvName.PROD, False), (EnvName.DEV, True)])
async def test_worker_store_follows_the_environment(
    env: EnvName, fixtures: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    built: list[ChatService] = []
    settings = SimpleNamespace(env=env, database_url="postgresql://unused", model_gateway_url="")
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "bind_store", built.append)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", AsyncMock())

    await worker._prepare_store()

    store = built[0]
    assert isinstance(store, ChatService)
    assert store.fake_models_allowed is fixtures
    slugs = {str(row["slug"]) for row in store.tool_servers.values()}
    assert ("petstore" in slugs) is fixtures
    names = {str(row["qualified_name"]) for row in store.tool_versions.values()}
    assert ("control.checkpoint" in names) is fixtures
    assert "general.fetch" in names
