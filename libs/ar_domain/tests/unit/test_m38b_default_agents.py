"""A tenant's default agents come from its seed. No request creates them. Task: M38b-T04a."""

import importlib
import uuid

import pytest
import sqlalchemy as sa

from ar_common.errors import ArError, NotFoundError
from ar_domain.agents.access import Actor
from ar_domain.agents.builder import BuilderService
from ar_domain.agents.logic import BUILTIN_AGENT_SLUGS
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
    actor = Actor(tenant, admin, PERMISSION_KEYS)
    listed = {row["slug"]: row for row in AgentLifecycle(store).list_agents(actor)}
    assert listed["assistant"]["builtin"] is True
    assert listed["builder"]["builtin"] is True


def test_a_built_in_agent_has_no_owner_and_the_person_seeded_for_wrote_version_one() -> None:
    store = ChatService()
    tenant, admin = uuid.uuid4(), uuid.uuid4()
    AgentLifecycle(store).ensure_builtins(tenant, admin)
    rows = [row for row in store.agents.values() if row["tenant_id"] == tenant]
    assert {row["slug"] for row in rows} == BUILTIN_AGENT_SLUGS
    for row in rows:
        assert row["owner_user_id"] is None
        assert row["owner_team_id"] is None
        assert row["builtin"] is True
        assert row["visibility"] == "tenant"
        assert store.versions[row["published_version_id"]]["created_by"] == admin
    alone = ChatService().ensure_assistant(tenant, admin)
    assert alone["owner_user_id"] is None
    assert alone["builtin"] is True


def test_a_built_in_agent_is_shown_to_everyone_and_edited_by_whoever_manages_agents() -> None:
    store = ChatService()
    tenant, admin, member = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    lifecycle = AgentLifecycle(store)
    lifecycle.ensure_builtins(tenant, admin)
    reader = Actor(tenant, member, frozenset({"agents:read"}))
    seen = {row["slug"]: row for row in lifecycle.list_agents(reader)}
    assert set(seen) == BUILTIN_AGENT_SLUGS
    assert seen["assistant"]["owner"] == {"id": None, "display_name": None}
    assert seen["assistant"]["can_edit"] is False
    # Without the manage permission, the person the seed ran for is not an editor either.
    plain_admin = Actor(tenant, admin, frozenset({"agents:read", "agents:edit"}))
    assert {row["can_edit"] for row in lifecycle.list_agents(plain_admin)} == {False}
    assert lifecycle.list_agents(plain_admin, owner="me") == []
    manager = Actor(tenant, member, PERMISSION_KEYS)
    assistant = next(row for row in lifecycle.list_agents(manager) if row["slug"] == "assistant")
    assert assistant["can_edit"] is True
    agent_id = uuid.UUID(str(assistant["id"]))
    renamed = lifecycle.update(
        manager, agent_id, if_match=str(assistant["etag"]), fields={"description": "Ours"}
    )
    assert renamed["description"] == "Ours"
    assert renamed["owner"] == {"id": None, "display_name": None}


def test_nobody_can_be_made_the_owner_of_a_built_in_agent() -> None:
    store = ChatService()
    tenant, admin = uuid.uuid4(), uuid.uuid4()
    lifecycle = AgentLifecycle(store)
    lifecycle.ensure_builtins(tenant, admin)
    actor = Actor(tenant, admin, PERMISSION_KEYS)
    assistant = next(row for row in lifecycle.list_agents(actor) if row["slug"] == "assistant")
    agent_id = uuid.UUID(str(assistant["id"]))
    with pytest.raises(ArError, match="a built-in agent has no owner"):
        lifecycle.update(
            actor, agent_id, if_match=str(assistant["etag"]), fields={"owner_user_id": admin}
        )
    assert store.agents[agent_id]["owner_user_id"] is None
    assert "agent.updated" not in [row["action"] for row in store.audit_log]


def test_an_agent_a_person_builds_is_theirs() -> None:
    store = demo_store()
    helpdesk = next(row for row in store.agents.values() if row["slug"] == "helpdesk")
    assert helpdesk["owner_user_id"] == demo_id("admin")
    assert not helpdesk["builtin"]
    builtins = [row for row in store.agents.values() if row["slug"] in BUILTIN_AGENT_SLUGS]
    assert len(builtins) == len(BUILTIN_AGENT_SLUGS)
    assert {row["owner_user_id"] for row in builtins} == {None}


def test_the_migration_clears_the_owner_of_built_in_agents_only() -> None:
    migration = importlib.import_module(
        "ar_domain.migrations.versions.20261118_0052_builtin_agents_no_owner"
    )
    assert migration.down_revision == "0051"
    assert frozenset(migration.BUILTIN_SLUGS) == BUILTIN_AGENT_SLUGS
    statement = " ".join(str(migration.CLEAR_OWNER).split())
    assert statement == (
        "UPDATE agents SET owner_user_id = NULL WHERE slug IN :slugs AND owner_user_id IS NOT NULL"
    )
    # Run the statement on a table of the same shape: only the built-in rows change.
    engine = sa.create_engine("sqlite://")
    owner = "u1"
    with engine.begin() as bind:
        bind.execute(sa.text("CREATE TABLE agents (tenant TEXT, slug TEXT, owner_user_id TEXT)"))
        for tenant in ("t1", "t2"):
            for slug in ("assistant", "builder", "helpdesk", "assistant-two"):
                bind.execute(
                    sa.text("INSERT INTO agents VALUES (:tenant, :slug, :owner)"),
                    {"tenant": tenant, "slug": slug, "owner": owner},
                )
        bind.execute(
            sa.text(migration.CLEAR_OWNER).bindparams(sa.bindparam("slugs", expanding=True)),
            {"slugs": list(migration.BUILTIN_SLUGS)},
        )
        rows = bind.execute(sa.text("SELECT tenant, slug, owner_user_id FROM agents")).all()
        migration.downgrade()
    assert len(rows) == 8
    for _tenant, slug, kept in rows:
        assert kept == (None if slug in BUILTIN_AGENT_SLUGS else owner)


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
