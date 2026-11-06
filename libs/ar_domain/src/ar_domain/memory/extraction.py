"""Ask the tenant's model what to remember from one turn. Spec: docs/03-specs/11-memory.md §4.

After a turn completes, the person's words, the answer and the memories already kept go to
a chat model, and the operations it returns are applied under the rules of
:class:`MemoryBook`. Nothing here decides what to remember by matching words: with no
model, nothing is remembered from the turn, and the log says so.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from ar_common.logging import get_logger
from ar_common.wrapping import neutralise, wrap_untrusted
from ar_domain.memory.book import MemoryBook
from ar_domain.memory.extract import parse_ops
from ar_domain.models.aliases import resolves
from ar_domain.prompts.budget import read_prompt

if TYPE_CHECKING:
    from typing import Any

_log = get_logger("ar_domain.memory")
_TEXT_LIMIT = 6000
_KEPT_LIMIT = 10


async def remember_turn(
    store: Any, run: dict[str, object], user_text: str, answer: str
) -> list[dict[str, object]]:
    """Extract after a completed top-level turn. Returns the facts that were saved."""
    book = MemoryBook(store)
    if not book.extraction_wanted(run):
        return []
    tenant_id = run.get("tenant_id")
    if not isinstance(tenant_id, uuid.UUID):
        return []
    alias = extraction_alias(store, run)
    if alias is None:
        run["memory_extraction"] = {"status": "no_model"}
        _log.warning("memory_extraction_skipped", reason="no_model", run_id=str(run.get("id")))
        return []
    kept = book.kept_for(run, f"{user_text}\n{answer}", limit=_KEPT_LIMIT)
    messages = extraction_messages(store, tenant_id, user_text, answer, kept)
    turn = await store.complete_turn(messages, [], tenant_id=tenant_id, model_alias=alias)
    if not isinstance(turn, dict) or not _answered(turn):
        # The provider did not answer, or answered with an error. Nothing is made up.
        run["memory_extraction"] = {"status": "no_answer", "alias": alias}
        _log.warning("memory_extraction_skipped", reason="no_answer", run_id=str(run.get("id")))
        return []
    _meter(store, run, alias, turn)
    output = str(turn.get("text") or "")
    saved = book.extract_turn(run, user_text, answer, model_output=output)
    run["memory_extraction"] = {
        "status": "done",
        "alias": alias,
        "ops": len(parse_ops(output)),
        "saved": len(saved),
    }
    return saved


def extraction_alias(store: Any, run: dict[str, object]) -> str | None:
    """The agent's alias for short background work, else the alias it answers with.

    None when neither points at a chat model the tenant can use.
    """
    from ar_domain.tools.agent_loop import model_alias_for  # noqa: PLC0415

    tenant_id = run.get("tenant_id")
    version = store.versions.get(run.get("agent_version_id"))
    definition = version.get("definition") if isinstance(version, dict) else None
    model = definition.get("model") if isinstance(definition, dict) else None
    fast = model.get("fast_alias") if isinstance(model, dict) else None
    for name in (fast, model_alias_for(store, run)):
        if isinstance(name, str) and name.strip() and resolves(store, tenant_id, name.strip()):
            return name.strip()
    return None


def extraction_messages(
    store: Any,
    tenant_id: uuid.UUID,
    user_text: str,
    answer: str,
    kept: list[dict[str, object]],
) -> list[dict[str, object]]:
    """The prompt: the instructions, then the exchange and the memories already kept."""
    system = read_prompt("memory_extraction.md")
    extra = _tenant_instructions(store, tenant_id)
    if extra:
        system += f"\n\nThis organisation adds:\n{extra}"
    lines = [f"- {item['id']}: {_inside(str(item['content']))}" for item in kept]
    user = "\n".join(
        [
            "<person_said>",
            _inside(user_text[:_TEXT_LIMIT]),
            "</person_said>",
            # The answer may repeat text that came from a tool or a document.
            wrap_untrusted(source="assistant_answer", content=answer[:_TEXT_LIMIT]),
            "<memories_kept>",
            *(lines or ["(none)"]),
            "</memories_kept>",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _inside(text: str) -> str:
    """Text placed inside a block of this prompt. It cannot open or close a block."""
    safe = neutralise(text)
    for tag in ("person_said", "memories_kept"):
        safe = safe.replace(f"<{tag}", f"&lt;{tag}").replace(f"</{tag}", f"&lt;/{tag}")
    return safe


def _tenant_instructions(store: Any, tenant_id: uuid.UUID) -> str:
    """What the tenant's administrator added to the instructions, on the Memory screen."""
    from ar_domain.identity.tenant_settings import section, settings_for  # noqa: PLC0415

    value = section(settings_for(store, tenant_id), "memory").get("extraction_instructions")
    return value.strip()[:2000] if isinstance(value, str) else ""


def _meter(store: Any, run: dict[str, object], alias: str, turn: dict[str, object]) -> None:
    """The model call is priced and counted like any other call of the run."""
    from ar_domain.tools.agent_loop import note_model_usage, price_step  # noqa: PLC0415

    usage = turn.get("usage")
    if not isinstance(usage, dict):
        return
    tokens_in = _whole(usage.get("tokens_in"))
    tokens_out = _whole(usage.get("tokens_out"))
    if not tokens_in and not tokens_out:
        return
    _cost, model_id = price_step(store, run, alias, tokens_in, tokens_out)
    note_model_usage(
        store, run, alias, model_id, step="memory", tokens_in=tokens_in, tokens_out=tokens_out
    )


def _answered(turn: dict[str, object]) -> bool:
    """True when the model produced output. A failed call reports no tokens at all."""
    usage = turn.get("usage")
    if not isinstance(usage, dict):
        return bool(str(turn.get("text") or "").strip())
    return bool(_whole(usage.get("tokens_in")) or _whole(usage.get("tokens_out")))


def _whole(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0
