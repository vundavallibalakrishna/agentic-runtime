"""Run budget shared by definitions and stream events."""

from pydantic import ConfigDict, Field

from ar_contracts.api_model import ApiModel


class RunBudget(ApiModel):
    """Limits for one top-level run. Subagents draw from the same budget."""

    model_config = ConfigDict(frozen=True)

    max_steps: int = Field(ge=1)
    max_tokens: int = Field(ge=1)
    max_cost_micros: int = Field(ge=0)
    max_wall_clock_s: int = Field(ge=1)
    max_tool_calls: int = Field(ge=0)
    max_parallel_tool_calls: int = Field(ge=1)


class RunUsage(ApiModel):
    """Cumulative usage reported on run events."""

    model_config = ConfigDict(frozen=True)

    tokens_in: int = 0
    tokens_out: int = 0
    cached_tokens: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    cost_micros: int = 0
    sandbox_cpu_seconds: float = 0
    elapsed_ms: int = 0
