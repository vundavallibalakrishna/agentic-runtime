"""Skills, delegation and prompt blocks. Spec: docs/03-specs/14-skills.md §7."""

import uuid

import pytest

from ar_common.errors import (
    ArError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import ChatService, demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.session import prepare_prompt
from ar_domain.policy.logic import rule_matches
from ar_domain.skills.book import SkillBook
from ar_domain.skills.delegate import cancel_children, delegate, plan_child
from ar_domain.skills.load import load_skill
from ar_domain.skills.logic import (
    asset_path_error,
    budget_exhausted,
    chain_too_deep,
    child_budget,
    constraint_matches,
    highest_match,
    platform_max_depth,
    reaches,
    skill_hash,
    split_skill_ref,
)
from ar_domain.skills.showcase import seed_composition

_ACTOR_PERMS = PERMISSION_KEYS


def _actor(store: ChatService) -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), _ACTOR_PERMS, display_name="Admin")


def test_constraints_hash_paths_cycles_and_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    assert asset_path_error("letterhead.md") == ""
    assert asset_path_error("../secret") != ""
    assets = [{"path": "b.md", "sha256": "b"}, {"path": "a.md", "sha256": "a"}]
    first = skill_hash("Write.", assets, ["sandbox.exec"])
    second = skill_hash("Write.", list(reversed(assets)), ["sandbox.exec"])
    assert first == second
    assert split_skill_ref("brand@^1") == ("brand", "^1")
    assert constraint_matches(1, "^1") is True
    assert constraint_matches(2, "^1") is False
    assert constraint_matches(0, "^1") is False
    assert constraint_matches(1, "nope") is False
    assert constraint_matches(1, "1") is True
    assert constraint_matches(1, "~1") is True
    assert constraint_matches(1, "*") is True
    monkeypatch.setenv("AR_MAX_DEPTH", "nope")
    assert platform_max_depth() == 3
    monkeypatch.setenv("AR_MAX_DEPTH", "9")
    assert platform_max_depth() == 3
    assert child_budget({"max_tokens": 4}, {"max_tokens": 9})["max_tokens"] == 4
    assert highest_match([1, 2], "") == 2
    assert highest_match([1, 2], "^1") == 1
    edges = {"researcher": ("research-lead",)}
    assert reaches("researcher", "research-lead", edges) is True
    assert chain_too_deep("lead", ["researcher"], {"researcher": ("scribe",)}, 1) is True
    assert budget_exhausted({"max_tokens": 0}) == "max_tokens"
    planned = plan_child(
        {
            "run_id": "parent",
            "depth": 3,
            "max_depth": 3,
            "remaining_budget": {"max_tokens": 10},
            "allowed": ["researcher"],
            "agent": "researcher",
            "task": "Look",
            "index": 0,
        }
    )
    assert planned["error"] == "depth_exceeded"
    refused = plan_child(
        {
            "run_id": "parent",
            "depth": 0,
            "max_depth": 3,
            "remaining_budget": {"max_tokens": 0},
            "allowed": ["researcher"],
            "agent": "researcher",
            "task": "Look",
            "index": 0,
        }
    )
    assert refused["error"] == "budget_exceeded"


def test_publish_pins_version_and_rejects_cycles() -> None:
    store = ChatService()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    actor = _actor(store)
    life = AgentLifecycle(store)
    writer = next(row for row in store.agents.values() if row["slug"] == "writer")
    version = store.versions[writer["published_version_id"]]
    pinned = version["definition"]["resolved"]["skills"]
    assert pinned[0]["slug"] == "brand-guidelines"
    assert pinned[0]["skill_version_id"]
    lead = next(row for row in store.agents.values() if row["slug"] == "research-lead")
    definition = dict(store.versions[lead["published_version_id"]]["definition"])
    definition.pop("resolved", None)
    subagents = dict(definition["subagents"])
    subagents["allowed"] = ["research-lead"]
    definition["subagents"] = subagents
    life.save_draft(actor, lead["id"], definition, change_note="cycle")
    with pytest.raises(Exception, match="itself") as caught:
        life.publish(actor, lead["id"], change_note="cycle")
    assert "itself" in str(caught.value)


def test_skill_archive_is_blocked_and_versions_increment() -> None:
    store = ChatService()
    actor = _actor(store)
    book = SkillBook(store)
    created = book.create(
        actor,
        {
            "slug": "checklist",
            "name": "Checklist",
            "description": "A reusable checklist.",
            "instructions_md": "Tick each item.",
        },
    )
    skill_id = uuid.UUID(str(created["id"]))
    published = book.publish(actor, skill_id, change_note="first")
    assert published["published_version"] == 1
    book.patch(actor, skill_id, {"instructions_md": "Tick each item twice."})
    again = book.publish(actor, skill_id, change_note="second")
    assert again["published_version"] == 2
    assert len(book.versions(actor, skill_id)) == 2
    outsider = Actor(uuid.uuid4(), uuid.uuid4(), _ACTOR_PERMS)
    with pytest.raises(NotFoundError):
        book.detail(outsider, skill_id)
    archived = book.archive(actor, skill_id)
    assert archived["status"] == "archived"


def test_archive_conflict_lists_the_writer() -> None:
    store = ChatService()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    actor = _actor(store)
    book = SkillBook(store)
    skill = next(row for row in store.skills.values() if row["slug"] == "brand-guidelines")
    with pytest.raises(ConflictError, match="writer"):
        book.archive(actor, skill["id"])
    used = book.where_used(actor, skill["id"])
    assert any(item["slug"] == "writer" for item in used["agents"])


def test_research_lead_merges_two_children_and_cancel_stops_them() -> None:
    store = ChatService()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    lead = next(row for row in store.agents.values() if row["slug"] == "research-lead")
    parent_id = uuid.uuid4()
    parent = {
        "id": parent_id,
        "tenant_id": demo_id("tenant"),
        "conversation_id": uuid.uuid4(),
        "agent_id": lead["id"],
        "agent_version_id": lead["published_version_id"],
        "user_id": demo_id("admin"),
        "depth": 0,
        "root_run_id": parent_id,
        "status": "running",
        "usage": {"tokens_in": 0, "tokens_out": 0},
    }
    store.runs[parent_id] = parent
    store.events[parent_id] = []
    result = delegate(
        store,
        parent,
        [
            {"agent": "researcher", "task": "Research the launch notes."},
            {"agent": "researcher", "task": "Research the rollout plan."},
        ],
    )
    assert result["is_error"] is False
    assert "Launch notes" in str(result["final_text"])
    assert "Rollout plan" in str(result["final_text"])
    assert "untrusted_content" in str(result["wrapped"])
    children = [row for row in store.runs.values() if row.get("parent_run_id") == parent_id]
    assert len(children) == 2
    assert all(row["trigger"] == "subagent" for row in children)
    for child in children:
        child["status"] = "running"
    cancel_children(store, parent_id)
    assert all(row["status"] == "cancelled" for row in children)


def test_loaded_skill_is_trusted_in_the_next_prompt() -> None:
    store = ChatService()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    writer = next(row for row in store.agents.values() if row["slug"] == "writer")
    conversation_id = uuid.uuid4()
    run_id = uuid.uuid4()
    store.conversations[conversation_id] = {
        "id": conversation_id,
        "tenant_id": demo_id("tenant"),
        "agent_id": writer["id"],
        "loaded_skills": [],
    }
    run = {
        "id": run_id,
        "tenant_id": demo_id("tenant"),
        "user_id": demo_id("admin"),
        "conversation_id": conversation_id,
        "agent_id": writer["id"],
        "agent_version_id": writer["published_version_id"],
        "depth": 0,
        "input_message_id": uuid.uuid4(),
    }
    loaded = load_skill(store, run, "brand-guidelines")
    assert loaded["is_error"] is False
    assert "sentence case" in str(loaded["text"])
    digest = prepare_prompt(
        store,
        run,
        store.conversations[conversation_id],
        store.versions[writer["published_version_id"]]["definition"],
        "Write a brief",
        names=[],
    )
    system = str(run["prompt_messages"][0]["content"])
    assert "sentence case" in system
    assert "brand-guidelines" in str(run["capabilities"])
    assert digest


def test_child_memory_save_is_denied_and_subagent_policy_matches() -> None:
    store = ChatService()
    actor = _actor(store)
    with pytest.raises(ForbiddenError):
        MemoryBook(store).save_from_tool(
            actor,
            {"content": "A child should not write this.", "scope": "user"},
            run={"parent_run_id": uuid.uuid4(), "depth": 1},
        )
    allowed = {"run": {"trigger": "subagent"}, "tool": {"qualified_name": "skills.load"}}
    denied = {"run": {"trigger": "chat"}, "tool": {"qualified_name": "skills.load"}}
    rule = {"match": {"triggers": ["subagent"]}}
    assert rule_matches(rule, allowed) is True
    assert rule_matches(rule, denied) is False


def test_skill_edits_republish_and_runtime_wrappers() -> None:
    import ar_domain.skills.tables  # noqa: F401
    from ar_mcp_gateway.builtins.skills import forward
    from ar_runtime.context.sections import capabilities_block
    from ar_runtime.control.delegate import delegate as runtime_delegate
    from ar_runtime.control.delegate import plan as runtime_plan

    store = ChatService()
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    actor = _actor(store)
    book = SkillBook(store)
    brand = book.published_by_slug(demo_id("tenant"), "brand-guidelines")
    assert brand is not None
    skill_id = uuid.UUID(str(brand["id"]))
    patched = book.patch(
        actor,
        skill_id,
        {"name": "Brand guidelines", "description": "House style for one-page briefs."},
    )
    assert patched["description"] == "House style for one-page briefs."
    assert book.version(actor, skill_id, 1)["version"] == 1
    with pytest.raises(NotFoundError):
        book.version(actor, skill_id, 9)
    assert book.list_skills(actor, query="house", status="published", owner="me")
    with pytest.raises(ValidationFailedError):
        book.create(
            actor,
            {"slug": "Bad", "name": "Bad", "description": "x", "instructions_md": "y"},
        )
    with pytest.raises(ValidationFailedError):
        book.patch(
            actor,
            skill_id,
            {"assets": [{"path": "../secret", "file_id": str(uuid.uuid4())}]},
        )
    draft = book.create(
        actor,
        {
            "slug": "launch-notes",
            "name": "Launch notes",
            "description": "A short note.",
            "instructions_md": "Keep it short.",
            "required_tools": ["not.a.real.tool"],
        },
    )
    with pytest.raises(ValidationFailedError):
        book.publish(actor, uuid.UUID(str(draft["id"])))
    reader = Actor(demo_id("tenant"), demo_id("member"), frozenset({"skills:read"}))
    with pytest.raises(ArError):
        book.patch(reader, skill_id, {"description": "no"})
    republished = book.republish_dependants(actor, skill_id)
    assert any(item.get("status") == "published" for item in republished["results"])
    missing = load_skill(store, {"tenant_id": demo_id("tenant")}, "missing-skill")
    assert missing["is_error"] is True
    writer = next(row for row in store.agents.values() if row["slug"] == "writer")
    definition = store.versions[writer["published_version_id"]]["definition"]
    assert "brand-guidelines" in capabilities_block(store, definition, tenant_id=demo_id("tenant"))
    refused = runtime_plan(
        {
            "run_id": "parent",
            "depth": 0,
            "max_depth": 3,
            "remaining_budget": {"max_tokens": 10},
            "allowed": [],
            "agent": "researcher",
            "task": "Look",
            "index": 0,
        }
    )
    assert refused["error"] == "not_allowed"
    lead = next(row for row in store.agents.values() if row["slug"] == "research-lead")
    parent_id = uuid.uuid4()
    parent = {
        "id": parent_id,
        "tenant_id": demo_id("tenant"),
        "conversation_id": uuid.uuid4(),
        "agent_id": lead["id"],
        "agent_version_id": lead["published_version_id"],
        "user_id": demo_id("admin"),
        "depth": 0,
        "root_run_id": parent_id,
        "status": "running",
        "usage": {"tokens_in": 0, "tokens_out": 0},
    }
    store.runs[parent_id] = parent
    store.events[parent_id] = []
    merged = runtime_delegate(
        store, parent, [{"agent": "researcher", "task": "Research the launch notes."}]
    )
    assert merged["is_error"] is False
    forwarded = forward(store, "skills.other", {})
    assert forwarded["is_error"] is True


@pytest.mark.asyncio
async def test_compose_and_child_activity_cover_the_edges() -> None:
    from ar_domain.skills.load import write_docx
    from ar_domain.skills.turn import maybe_compose
    from ar_runtime.activities.create_child_run import create_child_run
    from ar_runtime.activities.expire_approval import bind_store

    store = ChatService()
    assert await maybe_compose(store, {}, {}, "hello") is False
    seed_composition(store, demo_id("tenant"), demo_id("admin"))
    actor = _actor(store)
    created = SkillBook(store).create(
        actor,
        {
            "slug": "scratch-notes",
            "name": "Scratch notes",
            "description": "A disposable note.",
            "instructions_md": "Keep it short.",
        },
    )
    archived = SkillBook(store).archive(actor, uuid.UUID(str(created["id"])))
    assert archived["status"] == "archived"
    denied = load_skill(
        store,
        {"tenant_id": demo_id("tenant"), "agent_version_id": uuid.uuid4()},
        "brand-guidelines",
    )
    assert denied["is_error"] is True
    assert write_docx(store, {}, title="Brand brief", body="Hello")["is_error"] is True
    bind_store(store)
    store.runs[uuid.uuid4()] = {"id": "edge-child-0"}
    planned = await create_child_run(
        {
            "run_id": "edge",
            "depth": 0,
            "max_depth": 3,
            "remaining_budget": {"max_tokens": 10},
            "allowed": ["researcher"],
            "agent": "researcher",
            "task": "Look",
            "index": 0,
        }
    )
    bind_store(None)
    assert planned["child_run_id"] == "edge-child-0"
