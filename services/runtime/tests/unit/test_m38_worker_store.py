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
from ar_testing.sleeping import in_this_thread

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def _prepare(
    monkeypatch: pytest.MonkeyPatch, env: EnvName, answer: object, *, loopback: bool = False
) -> list[ChatService]:
    built: list[ChatService] = []
    settings = SimpleNamespace(
        env=env,
        egress_allow_loopback=loopback,
        database_url="postgresql://unused",
        model_gateway_url="",
        valkey_url="redis://shared/0",
    )

    class _Valkey:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr("redis.Redis.from_url", lambda *_a, **_k: _Valkey())
    if env not in {EnvName.DEV, EnvName.CI}:
        monkeypatch.setenv("AR_SANDBOX_MANAGER_URL", "http://sandbox-manager:8003")

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
    if env is EnvName.PROD:
        from ar_domain.chat.service import ChatService
        from ar_domain.readmodel.model import RepositoryReadModel

        assert isinstance(store, RepositoryReadModel)
        assert not isinstance(store, ChatService)
        assert store.holds_tenant_state() is False
        assert store.allow_loopback is False
        return
    assert store.fake_models_allowed is (env is EnvName.DEV)
    # A tool call runs in this process. Whether it may reach a loopback address is the
    # install's setting, off unless set, whatever the environment is called.
    assert store.allow_loopback is False
    assert store.agents == {}
    assert store.user_roles == {}
    slugs = {str(row["slug"]) for row in store.tool_servers.values()}
    assert "petstore" not in slugs
    names = {str(row["qualified_name"]) for row in store.tool_versions.values()}
    assert "general.fetch" in names
    assert ("session.checkpoint" in names) is (env is EnvName.DEV)


async def test_a_worker_without_a_database_waits_and_gets_no_demo_tenant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task: M38b-T04b. No process falls back to a demo tenant, in any environment."""
    found = TenantBinding(SimpleNamespace(), "acme", "Acme", "self_hosted", {})  # type: ignore[arg-type]
    answers: list[object] = [None, None, found]
    built = _prepare(monkeypatch, EnvName.DEV, None)

    async def bind(store: object, url: str) -> object:
        del store, url
        return answers.pop(0)

    async def no_pause(seconds: float) -> None:
        del seconds

    monkeypatch.setattr("ar_domain.durable.bind.bind_store", bind)
    monkeypatch.setattr("ar_domain.durable.bind.asyncio.sleep", in_this_thread(no_pause))

    await worker._prepare_store()

    assert answers == []
    assert built[0].agents == {}
    assert built[0].demo_tenant_seeded is False


@pytest.mark.parametrize("env", [EnvName.PROD, EnvName.DEV])
async def test_loopback_follows_the_installs_setting_not_the_environments_name(
    env: EnvName, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = TenantBinding(SimpleNamespace(), "acme", "Acme", "self_hosted", {})  # type: ignore[arg-type]
    built = _prepare(monkeypatch, env, found, loopback=True)

    await worker._prepare_store()

    store = built[0]
    if env is EnvName.PROD:
        from ar_domain.readmodel.model import RepositoryReadModel

        assert isinstance(store, RepositoryReadModel)
        assert store.allow_loopback is True
        assert store.holds_tenant_state() is False
        return
    assert store.allow_loopback is True
