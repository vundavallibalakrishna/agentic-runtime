"""Choose how a turn reads the documents it names.

The choice uses the model's registered ``context_window``. A missing window is
not replaced with a constant: a document over the retrieval budget is not read
in one prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from ar_common.errors import ArError, ErrorCode
from ar_common.settings import get_settings
from ar_domain.documents.chunk import RETRIEVAL_BUDGET
from ar_domain.knowledge.chunker import token_count

TASKS = frozenset(
    {"question", "summarise", "extract", "review", "compare", "gaps", "compose", "auto"}
)
STRATEGIES = frozenset({"auto", "full", "retrieve", "map_reduce"})
_QUESTION_WORDS = ("what", "which", "who", "when", "where", "why", "how", "?")


@dataclass(frozen=True, slots=True)
class NamedText:
    """One named document, measured the way the strategy spends the window."""

    file_id: str
    document_id: str
    tokens: int
    characters: int
    headings: int


@dataclass(frozen=True, slots=True)
class ReadingPlan:
    """The reading the turn will use. ``strategy`` is ``full``, ``retrieve`` or ``map_reduce``."""

    task: str
    strategy: str
    reason: str
    usable_tokens: int | None
    fits: bool


def normalise_task(value: object) -> str:
    """A task hint. Anything outside the set is rejected."""
    text = str(value or "auto").strip()
    if text not in TASKS:
        raise ArError(ErrorCode.VALIDATION_FAILED, "task is not one this runtime knows")
    return text


def normalise_strategy(value: object) -> str:
    """``mapReduce`` on the wire is ``map_reduce`` in Python."""
    text = str(value or "auto").strip()
    if text == "mapReduce":
        text = "map_reduce"
    if text not in STRATEGIES:
        raise ArError(ErrorCode.VALIDATION_FAILED, "strategy is not one this runtime knows")
    return text


def estimate_tokens(text: str) -> int:
    """Tokens the ingest counter would charge, times the install's margin."""
    if not text.strip():
        return 0
    factor = float(get_settings().document_token_factor)
    return max(1, int(token_count(text) * factor))


def usable_tokens(context_window: int | None) -> int | None:
    """Tokens left for document text. ``None`` when the model has no registered window."""
    if (
        not isinstance(context_window, int)
        or isinstance(context_window, bool)
        or context_window <= 0
    ):  # noqa: E501
        return None
    settings = get_settings()
    margin = int(context_window * float(settings.document_margin_ratio))
    left = (
        context_window
        - int(settings.document_output_reserve)
        - int(settings.document_instruction_reserve)
        - int(settings.document_tool_reserve)
        - int(settings.document_history_reserve)
        - margin
    )
    return max(0, left)


def infer_task(text: str, *, items: bool, documents: int) -> str:  # noqa: PLR0911
    """A hint from the words of the request. Core has no checklist of its own."""
    lowered = " ".join(text.lower().split())
    if items or any(word in lowered for word in ("gap", "missing", "checklist", "not covered")):
        return "gaps"
    if documents >= 2 and any(
        word in lowered for word in ("compare", "difference", "changed", "versus", "vs ")
    ):
        return "compare"
    if any(word in lowered for word in ("summarise", "summarize", "summary", "bullet")):
        return "summarise"
    if lowered.startswith("extract") or " extract " in f" {lowered} ":
        return "extract"
    if any(word in lowered for word in ("review", "finding", "rubric")):
        return "review"
    if any(word in lowered for word in ("draft", "compose", "write a")):
        return "compose"
    if any(word in lowered for word in _QUESTION_WORDS):
        return "question"
    return "question"


def choose(
    task: str,
    strategy: str,
    documents: list[NamedText],
    context_window: int | None,
) -> ReadingPlan:
    """Pick ``full``, ``retrieve`` or ``map_reduce``. Forced ``full`` that does not fit is a 409."""
    kind = task if task != "auto" else infer_task("", items=False, documents=len(documents))
    usable = usable_tokens(context_window)
    total_tokens = sum(item.tokens for item in documents)
    total_chars = sum(item.characters for item in documents)
    many = len(documents) > 3
    if usable is None:
        fits = total_chars <= RETRIEVAL_BUDGET and not many and bool(documents or total_chars == 0)
    else:
        fits = total_tokens <= usable and not many
    half = usable is not None and any(item.tokens > usable / 2 for item in documents)
    heading_cap = int(get_settings().document_heading_cap)
    many_headings = any(item.headings > heading_cap for item in documents)
    chosen, reason = _auto(kind, fits=fits, many=many, half=half, many_headings=many_headings)
    if strategy == "full" and chosen != "full":
        raise ArError(
            ErrorCode.INVALID_STATE,
            "The documents do not fit one reading. Send strategy auto.",
        )
    if strategy == "retrieve":
        chosen, reason = "retrieve", "the request asked to retrieve"
    elif strategy == "map_reduce":
        chosen, reason = "map_reduce", "the request asked to read section by section"
    return ReadingPlan(task=kind, strategy=chosen, reason=reason, usable_tokens=usable, fits=fits)


def _auto(  # noqa: PLR0911
    task: str, *, fits: bool, many: bool, half: bool, many_headings: bool
) -> tuple[str, str]:
    if task == "gaps":
        return "retrieve", "a gap check searches once per item"
    if task == "compare" and (not fits or half or many_headings or many):
        return "map_reduce", "the documents are aligned section by section"
    if task == "compare":
        return "full", "both documents fit one reading"
    if not fits or many:
        if task in {"summarise", "review"}:
            return "map_reduce", "the text does not fit one reading"
        if task == "compose":
            return "retrieve", "the draft reads the references it needs"
        return "retrieve", "the question is answered from the named documents"
    return "full", "the named text fits the model's window"
