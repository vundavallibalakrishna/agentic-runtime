"""Choose how a turn reads the documents it names.

A model plan says whether the reading is whole or targeted, and whether it
stays inside one document or crosses them. The registered context window
decides whether that plan is a full read, a scoped search, or a section
map-reduce. Strategies are a registry: a new one is a registration, not a
new branch on the instruction text.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from jsonschema import Draft202012Validator

from ar_common.errors import ArError, ErrorCode
from ar_common.settings import get_settings
from ar_domain.documents.chunk import RETRIEVAL_BUDGET
from ar_domain.knowledge.chunker import token_count

# The planner's answer. Coverage and scope are the schema, not words taken
# from the caller's instruction.
PLAN_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["coverage", "scope", "outputShape", "steps"],
    "properties": {
        "coverage": {"type": "string", "enum": ["whole", "targeted"]},
        "scope": {"type": "string", "enum": ["perDocument", "acrossDocuments"]},
        "outputShape": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass(frozen=True, slots=True)
class Fit:
    """The plan's coverage and whether the measured text fits the window."""

    coverage: str
    fits: bool


When = Callable[[Fit], bool]


@dataclass(frozen=True, slots=True)
class NamedText:
    """One named document, measured the way the strategy spends the window."""

    file_id: str
    document_id: str
    tokens: int
    characters: int
    headings: int
    title: str = ""
    page_count: int = 0
    outline: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReadingPlan:
    """The reading the turn will use, and the plan that chose it."""

    strategy: str
    reason: str
    usable_tokens: int | None
    fits: bool
    coverage: str
    scope: str
    output_shape: str
    steps: tuple[str, ...]
    source: str
    template_id: str = ""


@dataclass(frozen=True, slots=True)
class _Strategy:
    name: str
    when: When


_REGISTRY: dict[str, _Strategy] = {}
_ORDER: list[str] = []


def register_strategy(name: str, when: When) -> None:
    """Add or replace a strategy. Later registrations of the same name keep their place."""
    if name not in _REGISTRY:
        _ORDER.append(name)
    _REGISTRY[name] = _Strategy(name, when)


def registered_strategies() -> tuple[str, ...]:
    """Names in the order they are considered when the caller does not override."""
    return tuple(_ORDER)


def canonical_strategy(value: object) -> str:
    """The registry name for a wire value. Empty means the caller did not override."""
    text = str(value or "").strip()
    if text == "mapReduce":
        return "map_reduce"
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
    ):
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


def parse_plan(raw: object) -> dict[str, object] | None:
    """A plan object that matches ``PLAN_SCHEMA``, or None when it does not."""
    if isinstance(raw, str):
        import orjson  # noqa: PLC0415

        try:
            raw = orjson.loads(raw)
        except orjson.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None
    errors = list(Draft202012Validator(PLAN_SCHEMA).iter_errors(raw))
    if errors:
        return None
    steps = raw.get("steps")
    return {
        "coverage": str(raw.get("coverage") or ""),
        "scope": str(raw.get("scope") or ""),
        "outputShape": str(raw.get("outputShape") or ""),
        "steps": tuple(str(item) for item in steps) if isinstance(steps, list) else (),
    }


def documents_fit(
    documents: list[NamedText], context_window: int | None
) -> tuple[bool, int | None]:
    """Whether the measured text fits the usable budget."""
    usable = usable_tokens(context_window)
    total_tokens = sum(item.tokens for item in documents)
    total_chars = sum(item.characters for item in documents)
    if usable is None:
        return total_chars <= RETRIEVAL_BUDGET, None
    return total_tokens <= usable, usable


def choose(
    plan: dict[str, object] | None,
    documents: list[NamedText],
    context_window: int | None,
    override: str = "",
) -> ReadingPlan:
    """Pick a registered strategy from the plan and the measured window.

    An invalid or missing plan is whole-document coverage: full when the text
    fits, otherwise map-reduce. ``override`` must name a registered strategy.
    ``full`` on text that does not fit is a 409.
    """
    fits, usable = documents_fit(documents, context_window)
    parsed = plan if isinstance(plan, dict) and plan.get("coverage") else None
    coverage = str(parsed.get("coverage")) if parsed else "whole"
    scope = str(parsed.get("scope") or "perDocument") if parsed else "perDocument"
    shape = str(parsed.get("outputShape") or "") if parsed else ""
    steps = parsed.get("steps") if parsed else ()
    step_list = tuple(steps) if isinstance(steps, tuple) else ()
    source = "model" if parsed else "fallback"
    name, reason = _select(Fit(coverage, fits), override)
    return ReadingPlan(
        strategy=name,
        reason=reason,
        usable_tokens=usable,
        fits=fits,
        coverage=coverage,
        scope=scope,
        output_shape=shape,
        steps=step_list,
        source=source,
    )


def _select(fit: Fit, override: str) -> tuple[str, str]:
    named = canonical_strategy(override)
    if named:
        if named not in _REGISTRY:
            raise ArError(ErrorCode.VALIDATION_FAILED, "strategy is not registered")
        if named == "full" and not fit.fits:
            raise ArError(
                ErrorCode.INVALID_STATE,
                "The documents do not fit one reading. Omit strategy to let the plan choose.",
            )
        return named, "the caller named this strategy"
    for name in _ORDER:
        spec = _REGISTRY[name]
        if spec.when(fit):
            return name, _reason(name, fits=fit.fits)
    raise ArError(ErrorCode.INVALID_STATE, "no reading strategy is registered")


def _reason(name: str, *, fits: bool) -> str:
    if name == "retrieve":
        return "the plan asks for targeted passages"
    if name == "full":
        return "the named text fits the model's window"
    if fits:
        return "the plan fits one reading"
    return "the text does not fit one reading"


def _targeted(fit: Fit) -> bool:
    return fit.coverage == "targeted"


def _full(fit: Fit) -> bool:
    return fit.fits and fit.coverage != "targeted"


def _map_reduce(fit: Fit) -> bool:
    return not fit.fits


def _install_defaults() -> None:
    if _ORDER:
        return
    register_strategy("retrieve", _targeted)
    register_strategy("full", _full)
    register_strategy("map_reduce", _map_reduce)


_install_defaults()


# Kept so a registration made after import can be inspected in tests.
def reset_strategies(specs: list[tuple[str, When]] | None = None) -> None:
    """Replace the registry. Tests use this; the product keeps the defaults."""
    _REGISTRY.clear()
    _ORDER.clear()
    if specs is None:
        _install_defaults()
        return
    for name, when in specs:
        register_strategy(name, when)
