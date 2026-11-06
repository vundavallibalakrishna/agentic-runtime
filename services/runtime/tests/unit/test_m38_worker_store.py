"""The runtime worker builds its store for the environment it runs in.

Tasks: M38-T03 (fixtures follow the environment), M38b-T03 (a worker attached to a
database holds no demo tenant).
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from ar_common.settings import EnvName
from ar_domain.durable.bind import TenantBinding
from ar_runtime import worker

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _prepare(monkeypatch: pytest.MonkeyPatch, env: EnvName, answer: object) -> list[ChatService]:
    built: list[ChatService] = []
    settings = SimpleNamespace(env=env, database_url="postgresql://unused", model_gateway_url="")

    async def bind(store: object, url: str) -> object:
        del store, url
        return answer

    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "bind_store", built.append)
    monkeypatch.setattr("ar_domain.durable.bind.bind_store", bind)
    return built


@pytest.mark.parametrize("env", [EnvName.PROD, EnvName.DEV])
async def test_a_worker_with_a_database_holds_no_demo_tenant(
    env: EnvName, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = TenantBinding(SimpleNamespace(), "acme", "Acme", "self_hosted", {})  # type: ignore[arg-type]
    built = _prepare(monkeypatch, env, found)

    await worker._prepare_store()

    store = built[0]
    assert store.fake_models_allowed is (env is EnvName.DEV)
    assert store.agents == {}
    assert store.user_roles == {}
    slugs = {str(row["slug"]) for row in store.tool_servers.values()}
    assert "petstore" not in slugs
    names = {str(row["qualified_name"]) for row in store.tool_versions.values()}
    assert "general.fetch" in names
    assert ("control.checkpoint" in names) is (env is EnvName.DEV)


async def test_a_dev_worker_without_a_database_gets_the_demo_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = _prepare(monkeypatch, EnvName.DEV, None)

    await worker._prepare_store()

    store = built[0]
    assert {str(row["slug"]) for row in store.agents.values()} >= {"assistant", "builder"}
    assert "petstore" in {str(row["slug"]) for row in store.tool_servers.values()}
