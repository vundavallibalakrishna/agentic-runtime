"""Sample company library for the dev tenant. Spec: M7 exit scenario."""

import uuid
from typing import TYPE_CHECKING

from ar_domain.agents.access import Actor
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook

if TYPE_CHECKING:
    from typing import Any

_GUIDE = """# Visitor guide

The visitor desk opens at 08:30.
Ask reception for a badge.
The visitor badge token is ZX-4471.
"""

_PAYROLL = """# Payroll calendar

Payroll is released on the 28th.
Questions about pay go to the payroll desk.
"""

_ROSTER = """# On-call roster

The member on call this week is Dev Member.
Escalate after two missed calls.
"""


def seed_library(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    """Idempotent SharePoint-shaped library and the librarian agent."""
    store.user_emails.setdefault(demo_id("admin"), "admin@dev.local")
    store.user_emails.setdefault(demo_id("member"), "member@dev.local")
    store.company_domains = {"dev.local"}
    if any(row.get("slug") == "company-library" for row in store.knowledge_collections.values()):
        _librarian(store, tenant_id, user_id)
        return
    actor = Actor(
        tenant_id,
        user_id,
        PERMISSION_KEYS,
        display_name="Dev Admin",
        roles=frozenset({"tenant_admin"}),
    )
    book = KnowledgeBook(store)
    created = book.create_collection(
        actor,
        {
            "slug": "company-library",
            "name": "Company library",
            "description": "Handbooks the assistant can cite.",
            "visibility": "tenant",
            "acl_mode": "source",
            "classification": "internal",
        },
    )
    collection_id = uuid.UUID(str(created["id"]))
    book.create_source(
        actor,
        collection_id,
        {
            "name": "Company SharePoint",
            "kind": "sharepoint",
            "config": {
                "items": [
                    {
                        "external_id": "visitor-guide",
                        "title": "Visitor guide",
                        "uri": "sharepoint://visitor-guide",
                        "text": _GUIDE,
                        "acl": [{"type": "anyone"}],
                    },
                    {
                        "external_id": "payroll",
                        "title": "Payroll calendar",
                        "uri": "sharepoint://payroll",
                        "text": _PAYROLL,
                        "acl": [{"type": "user", "email": "admin@dev.local"}],
                    },
                    {
                        "external_id": "roster",
                        "title": "On-call roster",
                        "uri": "sharepoint://roster",
                        "text": _ROSTER,
                        "acl": [{"type": "user", "email": "member@dev.local"}],
                    },
                ]
            },
        },
    )
    _librarian(store, tenant_id, user_id)


def _librarian(store: Any, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    for agent in store.agents.values():
        if agent.get("tenant_id") == tenant_id and agent.get("slug") == "librarian":
            return
    definition = {
        "persona": {
            "display_name": "Librarian",
            "greeting": "Ask about the company library. I cite the page I used.",
        },
        "instructions": (
            "Answer from the company library. Cite the passage you used with [n]. "
            "If the library has nothing relevant, say so."
        ),
        "starter_prompts": [
            "When does the visitor desk open?",
            "When is payroll released?",
            "Who is on call this week?",
        ],
        "model": {"alias": "reasoning"},
        "tools": [{"server": "knowledge", "version": "*", "include": ["*"]}],
        "knowledge": {
            "collections": ["company-library"],
            "auto_retrieve": True,
            "top_k": 4,
            "min_score": 0.2,
        },
        "output": {"citations": "preferred", "grounding": "preferred"},
        "budget": {
            "max_steps": 8,
            "max_tokens": 16000,
            "max_cost_micros": 1_000_000,
            "max_wall_clock_s": 120,
            "max_tool_calls": 4,
            "max_parallel_tool_calls": 1,
        },
    }
    AgentLifecycle(store)._insert(
        tenant_id,
        user_id,
        slug="librarian",
        name="Librarian",
        description="Answers from the company library and cites the page.",
        visibility="tenant",
        definition=definition,  # type: ignore[arg-type]
        published=True,
    )
