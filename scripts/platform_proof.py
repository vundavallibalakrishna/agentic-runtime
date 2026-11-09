#!/usr/bin/env python
"""Prove the platform works end to end with a real model, from a clean store.

Layer 3 of platform verification. Where the tool matrix (Layer 1) proves each tool runs
and the gym (Layer 2) measures tool-choice accuracy, this walks one product story across
the whole platform: a person builds an agent from a sentence, that agent chats and uses a
tool, answers a grounded question from knowledge, and remembers a preference. Each step
asserts a real outcome; the exit code is non-zero if any step fails.

It runs in process on the demo tenant with the reasoning alias pointed at the cert model —
the same path the gym's live mode uses. Run:

  AR_EVAL_GYM_LIVE=1 AR_CERT_LLM_API_KEY=... uv run python scripts/platform_proof.py

The cert key is read from the environment and never printed.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING

from ar_domain.agents.access import Actor
from ar_domain.agents.assist import draft_from_description
from ar_domain.agents.service import AgentLifecycle
from ar_domain.chat.service import demo_id
from ar_domain.evals.gym.live import install_live, live_settings
from ar_domain.identity.permissions import PERMISSION_KEYS
from ar_domain.knowledge.book import KnowledgeBook
from ar_testing.demo import demo_store

if TYPE_CHECKING:
    from ar_domain.chat.service import ChatService

_TOKEN = "VERIFY-PLATFORM-8842"  # noqa: S105 - a proof fixture token, not a credential


def _actor() -> Actor:
    return Actor(demo_id("tenant"), demo_id("admin"), PERMISSION_KEYS)


def _proof_definition() -> dict[str, object]:
    """An agent bound to the tools the proof exercises, told to use them."""
    return {
        "persona": {"display_name": "Proof agent", "greeting": "Ask me anything."},
        "instructions": (
            "Use a tool before you answer, and quote the tool's result. For a calculation "
            "run code. To answer a question about a policy, search knowledge and cite it."
        ),
        "model": {"alias": "reasoning"},
        "tools": [
            {"server": "general", "version": "*", "include": ["code", "shell", "read_file"]},
            {"server": "knowledge", "version": "*", "include": ["search"]},
        ],
        "budget": {
            "max_steps": 6,
            "max_tokens": 8000,
            "max_cost_micros": 1_000_000,
            "max_wall_clock_s": 60,
            "max_tool_calls": 4,
        },
    }


def _proof_agent(store: ChatService) -> uuid.UUID:
    agent = AgentLifecycle(store)._insert(
        demo_id("tenant"),
        demo_id("admin"),
        slug="platform-proof",
        name="Platform proof",
        description="Exercises the platform end to end.",
        visibility="tenant",
        published=True,
        definition=_proof_definition(),
    )
    return uuid.UUID(str(agent["id"]))


async def _chat(store: ChatService, agent_id: uuid.UUID, text: str) -> tuple[list[str], str]:
    """Run one turn through the real agent loop; return the tools used and the answer."""
    tenant, user = demo_id("tenant"), demo_id("admin")
    conversation = store.create_conversation(tenant, user, agent_id, model_alias="reasoning")
    posted = store.post_message(
        tenant, user, uuid.UUID(str(conversation["id"])), text, attachment_ids=[], schedule=False
    )
    run = posted.get("run")
    if not isinstance(run, dict):
        raise TypeError("post_message returned no run")
    run_id = uuid.UUID(str(run["id"]))
    await store.generate(run_id, text, [])
    finished = store.runs[run_id]
    assistant = store.messages.get(uuid.UUID(str(finished.get("assistant_message_id"))))
    answer = str(assistant.get("text") or "") if isinstance(assistant, dict) else ""
    tools = [
        str(row.get("qualified_name") or "")
        for row in store.tool_calls.values()
        if row.get("run_id") == run_id
    ]
    return tools, answer


async def _check_builder(store: ChatService) -> tuple[bool, str]:
    result = await draft_from_description(
        store, _actor(), "Review vendor SOC 2 reports and flag missing controls"
    )
    definition = result.get("definition") if isinstance(result, dict) else None
    persona = definition.get("persona") if isinstance(definition, dict) else None
    instructions = str(definition.get("instructions") or "") if isinstance(definition, dict) else ""
    ok = isinstance(persona, dict) and len(instructions) > 20
    return ok, f"drafted an agent with {len(instructions)} chars of instructions"


async def _check_chat_tool(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    # A product the model cannot reliably do in its head, so it must run the tool.
    tools, answer = await _chat(
        store, agent_id, "Use code to compute 48271 * 93179 and reply with the number."
    )
    used = any("code" in tool or "shell" in tool for tool in tools)
    ok = used and "4497843509" in answer
    return ok, f"tools={tools or 'none'}; product in answer={'4497843509' in answer}"


async def _check_knowledge(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    book = KnowledgeBook(store)
    collection = book.create_collection(
        _actor(),
        {
            "slug": "proof-handbook",
            "name": "Proof handbook",
            "description": "One passage for the platform proof.",
            "embedding_alias": "embed",
        },
    )
    book.create_source(
        _actor(),
        uuid.UUID(str(collection["id"])),
        {
            "name": "Handbook",
            "kind": "sharepoint",
            "config": {
                "items": [
                    {
                        "external_id": "policy",
                        "title": "Access policy",
                        "uri": "proof://policy",
                        "text": f"The badge reset code for the north gate is {_TOKEN}.",
                        "acl": [{"type": "anyone"}],
                    }
                ]
            },
        },
    )
    _tools, answer = await _chat(
        store, agent_id, "What is the badge reset code for the north gate? Cite it."
    )
    return _TOKEN in answer, f"answer cites the token={_TOKEN in answer}"


async def _check_memory(store: ChatService, agent_id: uuid.UUID) -> tuple[bool, str]:
    before = len(getattr(store, "memory_facts", {}))
    await _chat(store, agent_id, "Remember that I always want figures in euros, not dollars.")
    after = len(getattr(store, "memory_facts", {}))
    return after > before, f"memory facts {before} -> {after}"


async def run() -> int:
    store = demo_store()
    key, url, model = live_settings()
    install_live(store, demo_id("tenant"), key=key, base_url=url, model=model)
    agent_id = _proof_agent(store)

    checks = [
        ("build an agent from a sentence", _check_builder(store)),
        ("chat and use a tool", _check_chat_tool(store, agent_id)),
        ("answer from knowledge, grounded", _check_knowledge(store, agent_id)),
        ("remember a preference", _check_memory(store, agent_id)),
    ]
    results: list[tuple[str, bool, str]] = []
    for name, coro in checks:
        try:
            ok, note = await coro
        except Exception as exc:  # noqa: BLE001 - a crash is a failed step, recorded
            ok, note = False, f"raised {type(exc).__name__}: {exc}"
        results.append((name, ok, note))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {note}")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nplatform proof: {passed}/{len(results)} steps passed (model {model})")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
