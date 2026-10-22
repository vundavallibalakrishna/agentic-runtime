"""Auto-retrieve activity. Spec: docs/03-specs/10-knowledge.md §6.4."""

from typing import TYPE_CHECKING

from temporalio import activity

from ar_domain.knowledge.answer import compose

if TYPE_CHECKING:
    from typing import Any

_STORE: Any = None


def bind_store(store: Any) -> None:
    """Tests and the dev worker install the process store."""
    global _STORE  # noqa: PLW0603
    _STORE = store


@activity.defn(name="auto_retrieve_knowledge")
async def auto_retrieve_knowledge(payload: dict[str, object]) -> dict[str, object]:
    """Retrieve and cite when the agent asks for it. Otherwise return the question."""
    store = _STORE
    if store is None or not isinstance(payload.get("run"), dict):
        return {"text": str(payload.get("question") or ""), "citations": []}
    composed = compose(store, payload["run"], str(payload.get("question") or ""))  # type: ignore[arg-type]
    if composed is None:
        return {"text": str(payload.get("question") or ""), "citations": []}
    return composed
