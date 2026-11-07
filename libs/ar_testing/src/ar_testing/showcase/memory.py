"""Sample memories for the dev tenant. The page reads this process store."""

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import uuid
    from typing import Any

from ar_domain.agents.access import Actor
from ar_domain.chat.service import demo_id
from ar_domain.memory.book import MemoryBook


def seed_memory(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Preferences, a team glossary and one lesson waiting for review."""
    if getattr(store, "memory_seeded", False):
        return
    team_id = demo_id("team-platform")
    store.team_roster[team_id] = {
        "id": team_id,
        "tenant_id": tenant_id,
        "name": "Platform",
        "slug": "platform",
        "members": {
            str(user_id): "lead",
            str(demo_id("member")): "member",
            str(demo_id("builder")): "lead",
        },
    }
    _enable_memory(store, tenant_id)
    admin = Actor(tenant_id, user_id, frozenset({"memory:manage_agent", "chat:use"}))
    book = MemoryBook(store)
    book.create_user(
        admin,
        {
            "content": "Prefers weekly status notes to stay under one page.",
            "scope": "user",
            "category": "preference",
        },
    )
    book.create_team(
        admin,
        team_id,
        {
            "content": "The platform team names files with the date first.",
            "category": "glossary",
        },
    )
    agent = _assistant(store, tenant_id)
    if agent is not None:
        book.create_agent(
            admin,
            agent["id"],  # type: ignore[arg-type]
            {
                "content": "Quote the source when you cite a document.",
                "category": "lesson",
            },
        )
        _pending(store, tenant_id, agent["id"])  # type: ignore[arg-type]
    store.memory_seeded = True


def _enable_memory(store: Any, tenant_id: uuid.UUID) -> None:
    settings = store.tenant_settings.setdefault(tenant_id, {})
    if isinstance(settings, dict):
        settings["memory"] = {"enabled": True, "extraction": True}


def _assistant(store: Any, tenant_id: uuid.UUID) -> dict[str, object] | None:
    for agent in store.agents.values():
        if agent.get("tenant_id") == tenant_id and agent.get("slug") == "assistant":
            version_id = agent.get("published_version_id")
            version = store.versions.get(version_id)
            if isinstance(version, dict) and isinstance(version.get("definition"), dict):
                version["definition"]["memory"] = {
                    "enabled": True,
                    "read_scopes": ["user", "agent", "team", "agent_user"],
                    "user_writes": "auto",
                    "agent_writes": "review",
                    "recall_top_k": 8,
                }
            return cast("dict[str, object]", agent)
    return None


def _pending(store: Any, tenant_id: uuid.UUID, agent_id: uuid.UUID) -> None:
    """A non-editor proposal so the review queue is not empty on first open."""
    member = Actor(tenant_id, demo_id("member"), frozenset({"chat:use"}))
    MemoryBook(store).create_agent(
        member,
        agent_id,
        {
            "content": "Lessons about the visitor desk should mention the 08:30 opening.",
            "category": "lesson",
        },
    )
