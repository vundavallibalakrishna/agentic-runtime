"""The dev tenant's example data: threads, a chart, a library, memory, routines, usage.

Moved out of ``ChatService`` so the product packages hold no demo-data building
(strict rules 1 & 3, M38b-T04f). ``seed_showcase(store)`` fills a seeded demo tenant with
the example content the dev screens show. Test setup calls it; the product never does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.demo_ids import demo_id

if TYPE_CHECKING:
    import uuid

    from ar_domain.chat.service import ChatService


def seed_showcase(store: ChatService) -> None:
    """Example threads for the dev admin so the first screen is not empty.

    Stable ids make the insert idempotent. The durable catalogue still comes
    from ``make seed``; this store is the one the dev API serves (OQ-31).
    """
    tenant_id = demo_id("tenant")
    user_id = demo_id("admin")
    marker = demo_id("showcase-status")
    if marker in store.conversations:
        _seed_chart(store, tenant_id, user_id)
        _seed_library(store, tenant_id, user_id)
        _seed_memory(store, tenant_id, user_id)
        _seed_composition(store, tenant_id, user_id)
        _seed_routines(store, tenant_id, user_id)
        _seed_channels(store, tenant_id, user_id)
        _seed_usage(store, tenant_id, user_id)
        _seed_assurance(store, tenant_id, user_id)
        return
    agent = store.ensure_assistant(tenant_id, user_id)
    samples = (
        (
            "showcase-status",
            "Weekly status for the platform",
            "Draft a short status update for the platform team.",
            "\n".join(
                (
                    "Here is a status you can send.",
                    "",
                    "## This week",
                    "",
                    "- Chat answers stream in place, with a stop control.",
                    "- The workspace directory lists the four seeded roles.",
                    "- Model aliases `reasoning`, `fast` and `vision` point at fake-llm.",
                    "",
                    "Nothing is blocked for the Friday review.",
                )
            ),
        ),
        (
            "showcase-session",
            "How the session cookie works",
            "Explain the sign-in session in simpler terms, and show a short example.",
            "\n".join(
                (
                    "The browser keeps a cookie named `ar_session`. The API stores the",
                    "real session on the server, so the cookie is only a lookup key.",
                    "",
                    "```python",
                    "def signed_in(cookie: str, sessions: dict[str, str]) -> bool:",
                    "    return cookie in sessions",
                    "```",
                    "",
                    "A second cookie, `ar_csrf`, travels with any change you make.",
                    "That stops another site from submitting a form as you.",
                )
            ),
        ),
        (
            "showcase-tone",
            "What the assistant should feel like",
            "Summarise what a calm enterprise assistant should feel like.",
            "\n".join(
                (
                    "It should feel like a well-run desk.",
                    "",
                    "1. One clear next step, not a wall of settings.",
                    "2. Answers that stay in a readable column.",
                    "3. Light and dark that are both finished.",
                    "",
                    "People open it when they have work to do, and they can see",
                    "where that work stands.",
                )
            ),
        ),
    )
    now = utcnow()
    for name, title, question, answer in samples:
        conversation_id = demo_id(name)
        question_id = demo_id(f"{name}-q")
        answer_id = demo_id(f"{name}-a")
        created = now
        store.conversations[conversation_id] = {
            "id": conversation_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "title": title,
            "status": "active",
            "pinned": False,
            "active_run_id": None,
            "created_at": created,
            "updated_at": created,
            "deleted_at": None,
            "showcase": True,
        }
        store.messages[question_id] = {
            "id": question_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "run_id": None,
            "parent_message_id": None,
            "role": "user",
            "content": [{"type": "text", "text": question}],
            "text": question,
            "status": "completed",
            "is_active_branch": True,
            "attachments": [],
            "created_at": created,
            "author_user_id": user_id,
        }
        store.messages[answer_id] = {
            "id": answer_id,
            "tenant_id": tenant_id,
            "conversation_id": conversation_id,
            "run_id": None,
            "parent_message_id": question_id,
            "role": "assistant",
            "content": [{"type": "text", "text": answer}],
            "text": answer,
            "status": "completed",
            "is_active_branch": True,
            "created_at": created,
        }
    _seed_chart(store, tenant_id, user_id)
    _seed_library(store, tenant_id, user_id)
    _seed_memory(store, tenant_id, user_id)
    _seed_composition(store, tenant_id, user_id)
    _seed_routines(store, tenant_id, user_id)
    _seed_channels(store, tenant_id, user_id)
    _seed_usage(store, tenant_id, user_id)
    _seed_assurance(store, tenant_id, user_id)


def _seed_assurance(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415
    from ar_domain.identity.tenant_settings import feature_enabled  # noqa: PLC0415
    from ar_domain.records.vault import EvidenceBook  # noqa: PLC0415

    if not feature_enabled(store, tenant_id, "assurance", default=False):
        return
    officer = demo_id("officer")
    store.user_roles.setdefault(officer, {"tenant_admin"})
    store.display_names.setdefault(officer, "Compliance officer")
    actor = Actor(
        tenant_id=tenant_id,
        user_id=user_id,
        permissions=PERMISSION_KEYS,
        step_up_at=utcnow(),
    )
    existing = [
        row
        for row in store.records.get("evidence", {}).values()
        if isinstance(row, dict) and row.get("idempotency_key") == "seed-evidence"
    ]
    if existing:
        return
    EvidenceBook(store).capture(
        actor,
        {
            "text": "Quarterly controls note",
            "media_type": "text/plain",
            "source_system": "desk",
            "collection_method": "upload",
            "provenance": {"note": "Seeded for the assurance desk"},
        },
        b"Quarterly controls note",
        idempotency_key="seed-evidence",
    )


def _seed_usage(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.usage import seed_usage  # noqa: PLC0415

    seed_usage(store, tenant_id, user_id)


def _seed_channels(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.channels import seed_channels  # noqa: PLC0415

    seed_channels(store, tenant_id, user_id)


def _seed_routines(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.routines import seed_routines  # noqa: PLC0415

    seed_routines(store, tenant_id, user_id)


def _seed_composition(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.skills import seed_composition  # noqa: PLC0415

    seed_composition(store, tenant_id, user_id)


def _seed_memory(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.memory import seed_memory  # noqa: PLC0415

    seed_memory(store, tenant_id, user_id)


def _seed_library(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_testing.showcase.knowledge import seed_library  # noqa: PLC0415

    seed_library(store, tenant_id, user_id)


def _seed_chart(store: ChatService, tenant_id: uuid.UUID, user_id: uuid.UUID) -> None:
    from ar_domain.sandboxes.service import SandboxBook  # noqa: PLC0415

    SandboxBook(store).seed_chart(tenant_id, user_id)
