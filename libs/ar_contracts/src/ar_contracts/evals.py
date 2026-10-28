"""Evaluation contracts. Spec: docs/03-specs/18-observability-eval.md §4."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from ar_common.errors import FieldError, ValidationFailedError
from ar_contracts.api_model import ApiModel


class GateConfig(ApiModel):
    """Publish gate attached to a suite."""

    required: bool = False
    min_pass_rate: float = 0.9
    max_regression_pct: float = 5.0
    must_pass_tags: list[str] = Field(default_factory=lambda: ["safety"])


class EvalPrincipal(ApiModel):
    """Simulated attributes layered onto the triggering user."""

    attributes: dict[str, object] = Field(default_factory=dict)
    groups: list[str] = Field(default_factory=list)


class EvalInput(ApiModel):
    """One case's user turns."""

    messages: list[str]
    files: list[str] = Field(default_factory=list)
    as_user: EvalPrincipal | None = None
    variables: dict[str, object] = Field(default_factory=dict)


class ContainsAssertion(ApiModel):
    type: Literal["contains"]
    value: str
    case_sensitive: bool = False


class NotContainsAssertion(ApiModel):
    type: Literal["not_contains"]
    value: str
    case_sensitive: bool = False


class RegexAssertion(ApiModel):
    type: Literal["regex"]
    pattern: str


class JsonSchemaAssertion(ApiModel):
    type: Literal["json_schema"]
    schema_: dict[str, object] = Field(alias="schema")


class ToolCalledAssertion(ApiModel):
    type: Literal["tool_called"]
    tool: str
    args_match: dict[str, object] | None = None
    min_times: int = 1


class ToolNotCalledAssertion(ApiModel):
    type: Literal["tool_not_called"]
    tool: str


class CitationAssertion(ApiModel):
    type: Literal["citation_present"]
    min: int = 1
    document_ids: list[str] | None = None


class RefusalAssertion(ApiModel):
    type: Literal["refusal"]


class SimilarityAssertion(ApiModel):
    type: Literal["answer_similarity"]
    reference: str
    threshold: float = 0.8


class JudgeAssertion(ApiModel):
    type: Literal["llm_judge"]
    rubric: str
    threshold: float = 0.5
    judge_alias: str = "reasoning"


class MaxLatencyAssertion(ApiModel):
    type: Literal["max_latency_ms"]
    value: int


class MaxCostAssertion(ApiModel):
    type: Literal["max_cost_micros"]
    value: int


class MaxStepsAssertion(ApiModel):
    type: Literal["max_steps"]
    value: int


class NoDenialsAssertion(ApiModel):
    type: Literal["no_policy_denials"]


class GroundednessAssertion(ApiModel):
    """Declared for the later groundedness gate. Scoring waits for M13-T07."""

    type: Literal["groundedness"]
    min_grounded_ratio: float = 0.9
    mode: Literal["strict", "preferred"] = "strict"


Assertion = Annotated[
    ContainsAssertion
    | NotContainsAssertion
    | RegexAssertion
    | JsonSchemaAssertion
    | ToolCalledAssertion
    | ToolNotCalledAssertion
    | CitationAssertion
    | RefusalAssertion
    | SimilarityAssertion
    | JudgeAssertion
    | MaxLatencyAssertion
    | MaxCostAssertion
    | MaxStepsAssertion
    | NoDenialsAssertion
    | GroundednessAssertion,
    Field(discriminator="type"),
]

_ASSERTIONS = TypeAdapter(Assertion)


class ToolMock(ApiModel):
    """A canned tool result. Eval runs never execute W2 or W3."""

    tool: str
    match_args: dict[str, object] | None = None
    result: dict[str, object] | None = None
    error: dict[str, object] | None = None


def parse_assertion(raw: object) -> dict[str, object]:
    """Validate one assertion and return snake_case fields."""
    try:
        model = _ASSERTIONS.validate_python(raw)
    except ValidationError as exc:
        raise ValidationFailedError("assertion is invalid", errors=[_issue(exc)]) from exc
    body = model.model_dump(by_alias=False)
    if "schema_" in body:
        body["schema"] = body.pop("schema_")
    return body


def parse_assertions(raw: object) -> list[dict[str, object]]:
    """Validate a non-empty assertion list."""
    if not isinstance(raw, list) or not raw:
        raise ValidationFailedError("assertions are required")
    return [parse_assertion(item) for item in raw]


def parse_input(raw: object) -> dict[str, object]:
    """Validate case input."""
    try:
        model = EvalInput.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailedError("input is invalid", errors=[_issue(exc)]) from exc
    return model.model_dump(by_alias=False)


def parse_mocks(raw: object) -> list[dict[str, object]]:
    """Validate tool mocks. An empty list is allowed."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidationFailedError("tool mocks must be a list")
    parsed: list[dict[str, object]] = []
    for item in raw:
        try:
            model = ToolMock.model_validate(item)
        except ValidationError as exc:
            raise ValidationFailedError("tool mock is invalid", errors=[_issue(exc)]) from exc
        if model.result is None and model.error is None:
            raise ValidationFailedError("tool mock needs a result or an error")
        parsed.append(model.model_dump(by_alias=False))
    return parsed


def parse_gate(raw: object) -> dict[str, object]:
    """Validate a gate object. Missing means the suite default."""
    if raw is None:
        return GateConfig().model_dump(by_alias=False)
    try:
        model = GateConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailedError("gate is invalid", errors=[_issue(exc)]) from exc
    return model.model_dump(by_alias=False)


def _issue(exc: ValidationError) -> FieldError:
    first = exc.errors()[0]
    loc = [str(part) for part in first.get("loc", ())]
    return FieldError(loc=loc, msg=str(first.get("msg") or "invalid"), type="value_error")
