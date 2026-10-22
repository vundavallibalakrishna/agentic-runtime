"""Natural-language entry points for delegation and skill loading.

The dev API still advances runs in process. These phrases call the same
delegation and skill loader the runtime uses.
"""

import re
import uuid
from typing import TYPE_CHECKING

from ar_common.time import utcnow
from ar_domain.skills.delegate import delegate
from ar_domain.skills.load import load_skill, write_docx

if TYPE_CHECKING:
    from typing import Any

_RESEARCH = re.compile(r"(?i)\bresearch\b")
_BRAND = re.compile(r"(?i)brand guidelines|one-page brief|brand-brief|\bdocx\b")


async def maybe_compose(
    store: Any, run: dict[str, object], assistant: dict[str, object], text: str
) -> bool:
    """Run a composed turn when the agent is a research lead or a brand writer."""
    agent = _agent(store, run)
    if agent is None:
        return False
    slug = str(agent.get("slug") or "")
    if slug == "research-lead" and _RESEARCH.search(text):
        return _research(store, run, assistant, text)
    if slug == "writer" and _BRAND.search(text):
        return await _brand(store, run, assistant, text)
    return False


def _research(store: Any, run: dict[str, object], assistant: dict[str, object], text: str) -> bool:
    result = delegate(
        store,
        run,
        [
            {
                "agent": "researcher",
                "task": "Research the launch notes and report whether the release is on track.",
            },
            {
                "agent": "researcher",
                "task": "Research the rollout plan and say which team goes first.",
            },
        ],
    )
    if result.get("is_error"):
        answer = "I could not delegate that research."
    else:
        answer = "Merged findings.\n\n" + str(result.get("final_text") or "")
    _complete(store, run, assistant, answer, text)
    return True


async def _brand(
    store: Any, run: dict[str, object], assistant: dict[str, object], text: str
) -> bool:
    loaded = load_skill(store, run, "brand-guidelines")
    if loaded.get("is_error"):
        _complete(
            store, run, assistant, str(loaded.get("text") or "The skill could not be loaded."), text
        )
        return True
    _record_call(store, run, "skills.load", str(loaded.get("text") or "")[:300])
    from ar_domain.skills.sections import loaded_skills_block  # noqa: PLC0415

    conversation = store.conversations.get(run.get("conversation_id"))
    system = ""
    if isinstance(conversation, dict):
        system = loaded_skills_block(store, conversation, run)
    remote = await store._remote_completion(text, system)
    prose = remote or ""
    if not prose or prose.startswith("fake:"):
        prose = "One-page brief. The name stays in sentence case."
    written = write_docx(store, run, title="Brand brief", body=prose)
    name = "brand-brief.docx"
    structured = written.get("structured")
    if isinstance(structured, dict) and structured.get("name"):
        name = str(structured["name"])
    answer = f"Wrote {name} using the brand-guidelines skill.\n\n{prose}"
    _complete(store, run, assistant, answer, text)
    return True


def _complete(
    store: Any, run: dict[str, object], assistant: dict[str, object], answer: str, user_text: str
) -> None:
    assistant["text"] = answer
    assistant["content"] = [{"type": "text", "text": answer}]
    assistant["status"] = "completed"
    run["status"] = "completed"
    run["ended_at"] = utcnow()
    run["result_summary"] = answer[:8000]
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        conversation["active_run_id"] = None
    usage = run.get("usage")
    if not isinstance(usage, dict):
        usage = {
            "tokens_in": max(1, len(user_text.split())),
            "tokens_out": max(1, len(answer.split())),
        }
        run["usage"] = usage
    store._emit(run, "message.completed", {"message_id": str(assistant.get("id")), "text": answer})
    store._emit_memory(run, user_text, answer)
    store._emit(
        run, "run.completed", {"final_message_id": str(assistant.get("id")), "usage": usage}
    )


def _record_call(store: Any, run: dict[str, object], qualified: str, preview: str) -> None:
    call_id = uuid.uuid4()
    store.tool_calls[call_id] = {
        "id": call_id,
        "tenant_id": run.get("tenant_id"),
        "run_id": run.get("id"),
        "qualified_name": qualified,
        "status": "succeeded",
        "arguments_redacted": {"skill": "brand-guidelines"},
        "result_preview": preview,
    }
    store._emit(
        run,
        "tool_call.completed",
        {"tool_call_id": str(call_id), "qualified_name": qualified, "status": "succeeded"},
    )


def _agent(store: Any, run: dict[str, object]) -> dict[str, object] | None:
    agent_id = run.get("agent_id")
    if isinstance(agent_id, uuid.UUID):
        row = store.agents.get(agent_id)
        if isinstance(row, dict):
            return row
    conversation = store.conversations.get(run.get("conversation_id"))
    if isinstance(conversation, dict):
        found = store.agents.get(conversation.get("agent_id"))
        if isinstance(found, dict):
            return found
    return None
