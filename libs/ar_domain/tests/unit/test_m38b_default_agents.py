"""A tenant's default agents come from its seed. No request creates them. Task: M38b-T04a."""

import uuid

import pytest

from ar_common.errors import NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.agents.builder import BuilderService
from ar_domain.agents.service import AgentLifecycle
from ar_domain.bundles.export import export_bundle
from ar_domain.chat.service import ChatService
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_testing.demo import demo_store


def _slugs(store: ChatService, tenant_id: uuid.UUID) -> list[str]:
    return sorted(
        str(row["slug"]) for row in store.agents.values() if row["tenant_id"] == tenant_id
    )


def test_the_seed_gives_a_tenant_the_assistant_and_the_builder() -> None:
    store = ChatService()
    tenant, admin = uuid.uuid4(), uuid.uuid4()
    AgentLifecycle(store).ensure_builtins(tenant, admin)
    AgentLifecycle(store).ensure_builtins(tenant, admin)
    assert _slugs(store, tenant) == ["assistant", "builder"]
    assert {row["owner_user_id"] for row in store.agents.values()} == {admin}
    actor = Actor(tenant, admin, PERMISSION_KEYS)
    listed = {row["slug"]: row for row in AgentLifecycle(store).list_agents(actor)}
    assert listed["assistant"]["builtin"] is True
    assert listed["builder"]["builtin"] is True


def test_reading_creates_nothing_for_a_tenant_that_was_not_seeded() -> None:
    store = ChatService()
    tenant, user = uuid.uuid4(), uuid.uuid4()
    actor = Actor(tenant, user, PERMISSION_KEYS)
    assert AgentLifecycle(store).list_agents(actor) == []
    assert store.list_agents(tenant, user) == []
    export_bundle(store, actor)
    with pytest.raises(NotFoundError, match="no assistant"):
        store.create_conversation(tenant, user, None)
    with pytest.raises(NotFoundError, match="no builder agent"):
        BuilderService(store)._builder_agent(actor)
    assert store.agents == {}


def test_only_the_demo_tenant_has_the_helpdesk_example() -> None:
    store = demo_store()
    assert "helpdesk" in _slugs(store, demo_id("tenant"))
    tenant, admin = uuid.uuid4(), uuid.uuid4()
    AgentLifecycle(store).ensure_builtins(tenant, admin)
    assert _slugs(store, tenant) == ["assistant", "builder"]
