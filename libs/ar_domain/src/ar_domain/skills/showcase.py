"""Seed the research lead, the researcher and the brand-guidelines skill."""

import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.agents.access import Actor
from ar_domain.agents.defaults import apply_definition_defaults
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.skills.book import SkillBook
from ar_domain.skills.logic import file_sha256

if TYPE_CHECKING:
    from typing import Any

_LETTERHEAD = (
    "Brand guidelines.\n"
    "Keep the name in sentence case.\n"
    "Use one page. Lead with the decision, then the evidence.\n"
)


def seed_composition(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Idempotent demo: two agents that delegate, and one skill that writes a DOCX."""
    import ar_domain.skills.resolver  # noqa: F401, PLC0415

    if any(row.get("slug") == "brand-guidelines" for row in getattr(store, "skills", {}).values()):
        return
    actor = Actor(tenant_id, user_id, PERMISSION_KEYS, display_name="Admin")
    _skill(store, actor)
    life = AgentLifecycle(store)
    _agent(
        life,
        actor,
        slug="researcher",
        name="Researcher",
        description="Looks up one question and returns a short finding.",
        definition=_definition(
            "Researcher",
            "Answer the brief with one short finding. Do not delegate.",
            "What should I look up?",
        ),
    )
    _agent(
        life,
        actor,
        slug="research-lead",
        name="Research lead",
        description="Splits a question across the researcher and merges the findings.",
        definition=_definition(
            "Research lead",
            "Delegate each research question to the researcher, then merge the findings.",
            "Give me two topics and I will research them together.",
            subagents={
                "allowed": ["researcher"],
                "allow_self_clone": False,
                "max_depth": 2,
                "max_parallel": 3,
            },
        ),
    )
    _agent(
        life,
        actor,
        slug="writer",
        name="Writer",
        description="Writes a one-page brief with the brand guidelines.",
        definition=_definition(
            "Writer",
            "Load the brand-guidelines skill and write a one-page DOCX.",
            "Tell me which brief to write.",
            skills=["brand-guidelines"],
            tools=[{"server": "sandbox", "version": "*", "include": ["*"]}],
            sandbox={"enabled": True, "template": "default", "scope": "conversation"},
        ),
    )


def _skill(store: Any, actor: Actor) -> None:
    file_id = demo_id("skill-brand-asset")
    blob = _LETTERHEAD.encode()
    now = utcnow()
    store.files[file_id] = {
        "id": file_id,
        "tenant_id": actor.tenant_id,
        "owner_user_id": actor.user_id,
        "conversation_id": None,
        "run_id": None,
        "kind": "upload",
        "name": "letterhead.md",
        "mime_type": "text/markdown",
        "size_bytes": len(blob),
        "sha256": file_sha256(blob),
        "object_key": f"skills/{file_id}",
        "classification": "internal",
        "status": "ready",
        "scan_status": "skipped",
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }
    store.blobs[file_id] = blob
    book = SkillBook(store)
    created = book.create(
        actor,
        {
            "slug": "brand-guidelines",
            "name": "Brand guidelines",
            "description": "How to write a one-page brief that follows the house style.",
            "visibility": "tenant",
            "instructions_md": (
                "1. Read /workspace/.skills/brand-guidelines/letterhead.md.\n"
                "2. Keep the name in sentence case.\n"
                "3. Write a one-page DOCX at /workspace/outputs/brand-brief.docx.\n"
            ),
            "required_tools": ["sandbox.exec"],
            "assets": [{"path": "letterhead.md", "file_id": file_id}],
        },
    )
    book.publish(actor, uuid.UUID(str(created["id"])), change_note="House style")


def _agent(
    life: AgentLifecycle,
    actor: Actor,
    *,
    slug: str,
    name: str,
    description: str,
    definition: dict[str, object],
) -> None:
    if any(row.get("slug") == slug for row in life.store.agents.values()):
        return
    created = life.create(
        actor,
        slug=slug,
        name=name,
        description=description,
        visibility="tenant",
        definition=definition,
    )
    life.publish(actor, uuid.UUID(str(created["id"])), change_note="seed")


def _definition(
    display: str,
    instructions: str,
    greeting: str,
    *,
    skills: list[str] | None = None,
    subagents: dict[str, object] | None = None,
    tools: list[dict[str, object]] | None = None,
    sandbox: dict[str, object] | None = None,
) -> dict[str, object]:
    raw: dict[str, object] = {
        "persona": {"display_name": display, "greeting": greeting},
        "instructions": instructions,
        "starter_prompts": ["Research the launch notes and the rollout plan."],
        "model": {"alias": "reasoning", "fast_alias": "fast"},
        "budget": {
            "max_steps": 8,
            "max_tokens": 16000,
            "max_cost_micros": 1_000_000,
            "max_wall_clock_s": 120,
            "max_tool_calls": 4,
            "max_parallel_tool_calls": 2,
        },
    }
    if skills is not None:
        raw["skills"] = skills
    if subagents is not None:
        raw["subagents"] = subagents
    if tools is not None:
        raw["tools"] = tools
    if sandbox is not None:
        raw["sandbox"] = sandbox
    return apply_definition_defaults(raw)
