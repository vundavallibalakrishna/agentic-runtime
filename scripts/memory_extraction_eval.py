"""Check the memory extraction prompt against a real model.

After a turn the product asks a chat model what to remember from it
(``ar_domain/prompts/text/memory_extraction.md``). This sends that prompt for a set of
exchanges and prints what the model returned next to what a careful reader would keep.
Run it after changing the prompt, and before pointing the ``fast`` alias at a smaller model.

    AR_CERT_LLM_BASE_URL=... AR_CERT_LLM_MODEL=... AR_CERT_LLM_API_KEY=... \\
        uv run python scripts/memory_extraction_eval.py

The key is read from the environment and is never printed. Exit code 1 when a case misses.
"""

import asyncio
import os
import sys
import uuid

from ar_domain.chat.service import ChatService
from ar_domain.memory.extract import parse_ops
from ar_domain.memory.extraction import extraction_messages

_PUNE = "11111111-1111-1111-1111-111111111111"
_NUTS = "22222222-2222-2222-2222-222222222222"

# What to expect, what the person said, what the assistant answered, memories already kept.
CASES: list[tuple[str, str, str, list[dict[str, object]]]] = [
    (
        "keep",
        "My daughter Mira turns six next week. What is a good birthday gift?",
        "A scooter.",
        [],
    ),
    (
        "keep",
        "I'm vegetarian, can you suggest a dinner recipe with aubergines?",
        "Try it baked.",
        [],
    ),
    ("keep", "As a nurse working night shifts, how do I improve my sleep?", "Darken the room.", []),
    ("keep", "My dog Bruno keeps barking at night, any tips?", "More exercise in the evening.", []),
    ("keep", "I prefer answers in bullet points.", "Understood.", []),
    ("keep", "Remember that our fiscal year starts in April.", "Noted.", []),
    ("keep", "Please always reply in British English.", "Of course.", []),
    (
        "keep",
        "I'm the head of procurement here and I report to Dana Whitfield. Draft a note to her.",
        "Here is a draft: Dana, the shipment is delayed by a week.",
        [],
    ),
    (
        "keep",
        "We use Jira for tickets and our team is called Platform Reliability. "
        "How do I write a good incident ticket?",
        "State the impact, the timeline and the next step.",
        [],
    ),
    ("none", "What is the capital of France?", "Paris.", []),
    ("none", "Write a haiku about autumn.", "Leaves fall quietly.", []),
    ("none", "Convert 250 euros to dollars at 1.08.", "270 dollars.", []),
    ("none", "Translate 'good morning' into French.", "Bonjour.", []),
    ("none", "Thanks, that helps!", "You're welcome.", []),
    ("none", "My password is hunter2, can you log me in to the portal?", "I cannot sign in.", []),
    (
        "none",
        "Can you summarise the attached contract?",
        "It runs for 24 months and auto-renews. The supplier is Globex and the fee is 4,000.",
        [],
    ),
    (
        "none",
        "What does our leave policy say about carry-over?",
        "At most 12 unused days carry over into the next year.",
        [],
    ),
    (
        "update",
        "I moved to the Berlin office last month. Where can I park there?",
        "I do not have parking details for the Berlin office.",
        [{"id": _PUNE, "content": "Works from the Pune office"}],
    ),
    (
        "delete",
        "Please forget that I am allergic to peanuts, that was a mistake.",
        "Done.",
        [{"id": _NUTS, "content": "Is allergic to peanuts"}],
    ),
]


def _need(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"Set {name}. This check calls a real model.")
    return value


async def run() -> int:
    """Send every case and return how many missed."""
    store = ChatService()
    tenant = uuid.uuid4()
    provider = store.create_provider(
        tenant,
        "eval",
        "openai_compatible",
        _need("AR_CERT_LLM_BASE_URL"),
        platform=False,
        api_key=_need("AR_CERT_LLM_API_KEY"),
    )
    model = store.create_model(
        tenant,
        uuid.UUID(str(provider["id"])),
        "eval",
        _need("AR_CERT_LLM_MODEL"),
        "chat",
        platform=False,
    )
    store.create_alias(tenant, "reasoning", "chat", uuid.UUID(str(model["id"])), platform=False)
    missed = 0
    for want, said, answer, kept in CASES:
        messages = extraction_messages(store, tenant, said, answer, kept)
        text = ""
        for _attempt in range(4):
            turn = await store.complete_turn(
                messages, [], tenant_id=tenant, model_alias="reasoning"
            )
            text = str((turn or {}).get("text") or "")
            usage = (turn or {}).get("usage")
            if isinstance(usage, dict) and (usage.get("tokens_in") or usage.get("tokens_out")):
                break
            await asyncio.sleep(2)
        ops = parse_ops(text)
        kinds = {str(op["op"]) for op in ops}
        fine = (want == "none" and not ops) or (want == "keep" and "add" in kinds) or want in kinds
        missed += 0 if fine else 1
        shown = "; ".join(f"{op['op']}: {op['content']}" for op in ops) or "nothing"
        sys.stdout.write(f"{'ok  ' if fine else 'MISS'} {want:<6} {said[:60]:<60} -> {shown}\n")
    sys.stdout.write(f"{len(CASES) - missed} of {len(CASES)} as expected\n")
    return missed


if __name__ == "__main__":
    raise SystemExit(1 if asyncio.run(run()) else 0)
