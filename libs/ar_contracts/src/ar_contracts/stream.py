"""Run stream events. Spec: docs/05-contracts/stream-events.md."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field

from ar_contracts.api_model import ApiModel
from ar_contracts.budget import RunBudget, RunUsage
from ar_contracts.messages import Citation, ContentPart, GroundingReport


class _Event(ApiModel):
    model_config = ConfigDict(frozen=True)

    id: str
    seq: int = Field(ge=1)
    run_id: uuid.UUID
    root_run_id: uuid.UUID
    conversation_id: uuid.UUID | None
    ts: datetime


class _Data(ApiModel):
    model_config = ConfigDict(frozen=True)


class RunQueuedData(_Data):
    agent_id: uuid.UUID
    agent_version_id: uuid.UUID
    trigger: str
    input_message_id: uuid.UUID


class RunQueued(_Event):
    type: Literal["run.queued"]
    data: RunQueuedData


class RunStartedData(_Data):
    model_alias: str
    budget: RunBudget
    sandbox_id: uuid.UUID | None = None


class RunStarted(_Event):
    type: Literal["run.started"]
    data: RunStartedData


class RunStatusData(_Data):
    status: Literal["running", "waiting_approval", "waiting_input"]
    reason: str | None = None


class RunStatus(_Event):
    type: Literal["run.status"]
    data: RunStatusData


class RunUsageEvent(_Event):
    type: Literal["run.usage"]
    data: RunUsage


class RunCompletedData(_Data):
    final_message_id: uuid.UUID
    usage: RunUsage


class RunCompleted(_Event):
    type: Literal["run.completed"]
    data: RunCompletedData


class RunErrorInfo(_Data):
    code: str
    message: str
    retriable: bool


class RunFailedData(_Data):
    error: RunErrorInfo
    usage: RunUsage


class RunFailed(_Event):
    type: Literal["run.failed"]
    data: RunFailedData


class RunCancelledData(_Data):
    by: Literal["user", "system"]
    usage: RunUsage


class RunCancelled(_Event):
    type: Literal["run.cancelled"]
    data: RunCancelledData


class RunBudgetExceededData(_Data):
    limit: Literal[
        "max_steps", "max_tokens", "max_cost_micros", "max_wall_clock_s", "max_tool_calls"
    ]
    usage: RunUsage


class RunBudgetExceeded(_Event):
    type: Literal["run.budget_exceeded"]
    data: RunBudgetExceededData


class MessageStartedData(_Data):
    message_id: uuid.UUID
    role: Literal["assistant"]
    model_alias: str
    reset: bool = False


class MessageStarted(_Event):
    type: Literal["message.started"]
    data: MessageStartedData


class MessageDeltaData(_Data):
    message_id: uuid.UUID
    text: str


class MessageDelta(_Event):
    type: Literal["message.delta"]
    data: MessageDeltaData


class ReasoningDelta(_Event):
    type: Literal["reasoning.delta"]
    data: MessageDeltaData


class MessageCompletedData(_Data):
    message_id: uuid.UUID
    content: list[ContentPart]
    tokens_in: int
    tokens_out: int
    finish_reason: str


class MessageCompleted(_Event):
    type: Literal["message.completed"]
    data: MessageCompletedData


class CitationAddedData(_Data):
    message_id: uuid.UUID
    citation: Citation


class CitationAdded(_Event):
    type: Literal["citation.added"]
    data: CitationAddedData


class GroundingCheckedData(_Data):
    message_id: uuid.UUID
    mode: Literal["off", "preferred", "strict"]
    report: GroundingReport


class GroundingChecked(_Event):
    type: Literal["message.grounding_checked"]
    data: GroundingCheckedData


class ToolCallStartedData(_Data):
    tool_call_id: uuid.UUID
    model_call_id: uuid.UUID
    qualified_name: str
    title: str
    risk_class: str
    arguments_preview: str


class ToolCallStarted(_Event):
    type: Literal["tool_call.started"]
    data: ToolCallStartedData


class ToolCallProgressData(_Data):
    tool_call_id: uuid.UUID
    message: str
    progress: float | None = None


class ToolCallProgress(_Event):
    type: Literal["tool_call.progress"]
    data: ToolCallProgressData


class ToolCallApprovalRequiredData(_Data):
    tool_call_id: uuid.UUID
    approval_id: uuid.UUID
    preview: dict[str, str]
    expires_at: datetime
    approver_rule: str


class ToolCallApprovalRequired(_Event):
    type: Literal["tool_call.approval_required"]
    data: ToolCallApprovalRequiredData


class ToolCallApprovalResolvedData(_Data):
    tool_call_id: uuid.UUID
    approval_id: uuid.UUID
    decision: Literal["approved", "rejected", "expired", "cancelled"]
    by_user_id: uuid.UUID | None = None


class ToolCallApprovalResolved(_Event):
    type: Literal["tool_call.approval_resolved"]
    data: ToolCallApprovalResolvedData


class InputRequiredData(_Data):
    request_id: uuid.UUID
    tool_call_id: uuid.UUID
    message: str
    requested_schema: dict[str, str]
    expires_at: datetime


class InputRequired(_Event):
    type: Literal["input.required"]
    data: InputRequiredData


class InputResolvedData(_Data):
    request_id: uuid.UUID
    action: Literal["accept", "decline", "cancel", "expired"]


class InputResolved(_Event):
    type: Literal["input.resolved"]
    data: InputResolvedData


class ToolCallCompletedData(_Data):
    tool_call_id: uuid.UUID
    status: Literal["succeeded"]
    result_preview: str
    result_file_id: uuid.UUID | None = None
    latency_ms: int


class ToolCallCompleted(_Event):
    type: Literal["tool_call.completed"]
    data: ToolCallCompletedData


class ToolCallFailedData(_Data):
    tool_call_id: uuid.UUID
    status: Literal["failed", "denied", "rejected", "expired", "cancelled"]
    error: dict[str, str]
    policy_reasons: list[str] | None = None
    connect_url: str | None = None


class ToolCallFailed(_Event):
    type: Literal["tool_call.failed"]
    data: ToolCallFailedData


class ArtifactCreatedData(_Data):
    file_id: uuid.UUID
    name: str
    mime_type: str
    size_bytes: int
    preview: str | None = None


class ArtifactCreated(_Event):
    type: Literal["artifact.created"]
    data: ArtifactCreatedData


class SandboxStatusData(_Data):
    sandbox_id: uuid.UUID
    status: str


class SandboxStatus(_Event):
    type: Literal["sandbox.status"]
    data: SandboxStatusData


class SandboxOutputData(_Data):
    tool_call_id: uuid.UUID
    stream: Literal["stdout", "stderr"]
    text: str


class SandboxOutput(_Event):
    type: Literal["sandbox.output"]
    data: SandboxOutputData


class BrowserScreenshotData(_Data):
    tool_call_id: uuid.UUID
    file_id: uuid.UUID
    url: str
    title: str


class BrowserScreenshot(_Event):
    type: Literal["browser.screenshot"]
    data: BrowserScreenshotData


class PlanItem(_Data):
    id: str
    title: str
    status: Literal["pending", "in_progress", "done", "cancelled"]


class PlanUpdatedData(_Data):
    items: list[PlanItem]


class PlanUpdated(_Event):
    type: Literal["plan.updated"]
    data: PlanUpdatedData


class SubagentStartedData(_Data):
    child_run_id: uuid.UUID
    agent_id: uuid.UUID
    agent_name: str
    task_brief: str


class SubagentStarted(_Event):
    type: Literal["subagent.started"]
    data: SubagentStartedData


class SubagentCompletedData(_Data):
    child_run_id: uuid.UUID
    status: str
    result_summary: str
    usage: RunUsage


class SubagentCompleted(_Event):
    type: Literal["subagent.completed"]
    data: SubagentCompletedData


class MemoryRecalledData(_Data):
    fact_ids: list[uuid.UUID]
    count: int


class MemoryRecalled(_Event):
    type: Literal["memory.recalled"]
    data: MemoryRecalledData


class MemorySavedData(_Data):
    fact_id: uuid.UUID
    content: str
    scope: str


class MemorySaved(_Event):
    type: Literal["memory.saved"]
    data: MemorySavedData


class ContextCompactedData(_Data):
    tokens_before: int
    tokens_after: int


class ContextCompacted(_Event):
    type: Literal["context.compacted"]
    data: ContextCompactedData


class WarningData(_Data):
    code: str
    message: str


class WarningEvent(_Event):
    type: Literal["warning"]
    data: WarningData


class Heartbeat(_Event):
    type: Literal["heartbeat"]
    data: _Data


RunEvent = Annotated[
    RunQueued
    | RunStarted
    | RunStatus
    | RunUsageEvent
    | RunCompleted
    | RunFailed
    | RunCancelled
    | RunBudgetExceeded
    | MessageStarted
    | MessageDelta
    | ReasoningDelta
    | MessageCompleted
    | CitationAdded
    | GroundingChecked
    | ToolCallStarted
    | ToolCallProgress
    | ToolCallApprovalRequired
    | ToolCallApprovalResolved
    | InputRequired
    | InputResolved
    | ToolCallCompleted
    | ToolCallFailed
    | ArtifactCreated
    | SandboxStatus
    | SandboxOutput
    | BrowserScreenshot
    | PlanUpdated
    | SubagentStarted
    | SubagentCompleted
    | MemoryRecalled
    | MemorySaved
    | ContextCompacted
    | WarningEvent
    | Heartbeat,
    Field(discriminator="type"),
]
