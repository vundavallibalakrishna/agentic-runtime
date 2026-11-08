"""The model chooses a skill: a hint, skills.load bound by default. Task: M39-T05."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.demo_ids import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.skills.book import SkillBook
from ar_domain.skills.match import match_skill
from ar_domain.tools.pipeline import ToolPipeline
from ar_testing.demo import demo_store


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS, display_name="Dev Admin")


def _skill(store: Any) -> None:
    book = SkillBook(store)
    created = book.create(
        _actor(),
        {
            "slug": "weekly-status",
            "name": "Weekly status",
            "description": "Use when the user asks for a weekly status note.",
            "visibility": "tenant",
            "instructions_md": "Begin with STATUS-OK.",
            "required_tools": [],
        },
    )
    book.publish(_actor(), uuid.UUID(str(created["id"])), change_note="x")


def _agent_with_skill(store: Any) -> tuple[uuid.UUID, uuid.UUID]:
    life = AgentLifecycle(store)
    created = life.create(_actor(), slug="helper", name="Helper", template="blank")
    agent_id = uuid.UUID(str(created["id"]))
    life.save_draft(
        _actor(),
        agent_id,
        {"instructions": "help", "skills": ["weekly-status"], "tools": []},
    )
    published = life.publish(_actor(), agent_id, change_note="skilled")
    return agent_id, uuid.UUID(str(published["published_version_id"]))


def test_match_hints_at_a_skill_without_loading_its_body() -> None:
    store = demo_store()
    _skill(store)
    run = {"tenant_id": demo_id("tenant"), "agent_id": demo_id("admin")}
    hint = match_skill(store, run, {"skills": ["weekly-status"]}, "Write the weekly status note")
    assert hint is not None
    assert hint["slug"] == "weekly-status"
    assert "instructions" not in hint  # the body is not loaded
    assert match_skill(store, run, {"skills": ["weekly-status"]}, "What is the weather?") is None


def test_skills_load_is_entitled_by_default() -> None:
    store = demo_store()
    _skill(store)
    _agent, version_id = _agent_with_skill(store)
    load = next(
        row for row in store.tool_versions.values() if row.get("qualified_name") == "skills.load"
    )
    assert ToolPipeline(store)._entitled({"agent_version_id": version_id}, load) is True


def test_a_skilled_agent_is_offered_skills_load() -> None:
    store = demo_store()
    store._completion_call = lambda _t, alias="reasoning": ("Qwen/Qwen3-32B", {}, 5.0, True)
    _skill(store)
    agent_id, _version = _agent_with_skill(store)
    tenant, user = demo_id("tenant"), demo_id("admin")

    captured: list[list[str]] = []

    async def complete(
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        *,
        tenant_id: uuid.UUID,
        model_alias: str,
    ) -> dict[str, object]:
        del messages, tenant_id, model_alias
        captured.append([str(tool["function"]["name"]) for tool in tools])  # type: ignore[index]
        return {
            "text": "ok",
            "tool_calls": [],
            "usage": {"tokens_in": 1, "tokens_out": 1},
            "real": True,
        }

    store.complete_turn = complete  # type: ignore[method-assign]
    conversation = store.create_conversation(tenant, user, agent_id, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), "write the weekly status", schedule=False
    )
    asyncio.run(store.generate(uuid.UUID(str(posted["run"]["id"])), "write the weekly status", []))
    assert captured, "the model was called"
    assert "skills__load" in captured[0]
