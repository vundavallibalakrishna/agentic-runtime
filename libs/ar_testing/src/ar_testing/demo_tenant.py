"""Build the dev tenant in a store that has no database: the scripted provider, the
assistant and example agents, and the built-in tools.

Moved out of ``ChatService`` so the product packages hold no demo-tenant building (strict
rules 1 & 3, M38b-T04f). Only test setup calls these (``ar_testing.demo``, the browser-test
harness, the eval tooling); a product process never does, since its tenant, people and
agents are rows in its database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ar_domain.agents.service import AgentLifecycle
from ar_domain.demo_ids import demo_id

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService


def seed_demo(store: ChatService) -> None:
    """The demo tenant and its scripted provider. Safe to call twice."""
    seed_demo_tenant(store)


def _seed_scripted_provider(store: ChatService) -> None:
    """The demo's chat provider: a scripted model server and the chat aliases.

    An embedding model is not part of it. A test registers one the way a person
    does, as a model of kind embedding on a provider that answers.
    """
    if demo_id("provider") in store.providers:
        return
    provider_id = demo_id("provider")
    chat_model = demo_id("model-chat")
    store.providers[provider_id] = store._provider(
        provider_id, None, "fake-llm", "fake", store.fake_llm_url
    )
    store.models[chat_model] = store._model(chat_model, None, provider_id, "fake-chat", "chat")
    for alias in ("reasoning", "fast", "vision"):
        alias_id = demo_id(f"alias-{alias}")
        store.aliases[alias_id] = store._alias(alias_id, None, alias, "chat", chat_model)


def seed_demo_tenant(store: ChatService) -> None:
    """A demo tenant with fixed ids, for a store that has no database behind it.

    Only test setup calls this (``ar_testing.demo``, the browser-test harness and the
    eval gym). A product process never does: its tenant, people and agents are rows
    in its database.
    """
    if store.demo_tenant_seeded:
        return
    store.demo_tenant_seeded = True
    _seed_scripted_provider(store)
    # The dev tenant shows every screen, including the assurance desk that a
    # fresh customer tenant keeps off until it turns the feature on.
    # Kept sparse on purpose: a full settings dump here changes defaults that other
    # code reads as "unset" (tool review, self-review), see test_m22_api.
    store.tenant_settings.setdefault(demo_id("tenant"), {"features": {"assurance": True}})
    store.ensure_assistant(demo_id("tenant"), demo_id("admin"))
    AgentLifecycle(store).ensure_example(demo_id("tenant"), demo_id("admin"))
    AgentLifecycle(store).ensure_builtins(demo_id("tenant"), demo_id("admin"))
    from ar_domain.tools.registry import ToolRegistry  # noqa: PLC0415

    ToolRegistry(store).ensure_seed()
    from ar_domain.agents.access import Actor  # noqa: PLC0415
    from ar_domain.evals.book import EvalBook  # noqa: PLC0415
    from ar_domain.identity.permissions import PERMISSION_KEYS  # noqa: PLC0415

    EvalBook(store).ensure_platform(
        Actor(
            tenant_id=demo_id("tenant"),
            user_id=demo_id("admin"),
            permissions=PERMISSION_KEYS,
        )
    )
