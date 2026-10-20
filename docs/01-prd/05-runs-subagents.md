# PRD 05 — Runs & subagents

Every agent execution is a durable run (`AgentRunWorkflow`) with budgets, planning, cancellation, inspection and optional delegation to subagents. Spec: [spec 07](../03-specs/07-agent-runtime.md), [spec 06 §3–4](../03-specs/06-conversations-runs.md), [ADR index](../02-architecture/adr/README.md). Plan: [M2](../09-plan/M02-first-chat.md), [M9](../09-plan/M09-subagents-skills.md).

### US-RUN-01 · Durable runs survive failures (P0)
As a **member**, I want my long task to finish even if a worker restarts or a model call fails transiently.
- Runs execute as Temporal workflows (`run-{run_id}`); activities retry per spec 07 §2.2; a worker crash mid-run resumes from the last completed activity without duplicate tool side effects (idempotency keys on tool calls).
- If Temporal is briefly unavailable the message is accepted (`202`, run `queued`) and the run starts when it recovers.
- Spec: spec 07 §2, [spec 01 failure modes](../03-specs/01-api-bff.md). Plan: M2-T09, M1-T06.

### US-RUN-02 · Budgets stop runaway runs (P0)
As a **tenant admin**, I want limits on steps, tokens, cost, wall-clock and tool calls per run.
- `RunBudget` from the agent definition (defaults in [definition-schema §2](../05-contracts/definition-schema.md#2-agentdefinition-kind-agent)), capped by tenant settings; exceeding any limit ends the run with `run.budget_exceeded` (which limit, usage) and a final message explaining it.
- Subagents draw from the parent's remaining budget.
- Spec: spec 07 §2.1, §7. Plan: M2-T09, M9-T01.

### US-RUN-03 · Planning visible to the user (P1)
As a **member**, I want to see the agent's plan for multi-step tasks.
- The agent maintains a checklist via `plan.update`; the UI shows it live (`plan.updated`) and on the conversation (`Conversation.plan`).
- Spec: spec 07 §6. Plan: M4-T05, M2-T11.

### US-RUN-04 · Inspect a run (P0)
As a **builder**, I want to inspect steps, model calls, tool calls, timings, tokens and cost of a run.
- Run inspector built on `GET /api/v1/runs/{run_id}`, `/steps`, `/tool-calls`, `/children`, `/events`; link to the trace (`trace_url`) for operators.
- Content visibility follows conversation access; admins with `conversations:read_all` see content with audit `conversation.read_privileged`.
- Spec: spec 06 §3, [spec 18 §3](../03-specs/18-observability-eval.md#3-in-product-observability-api). Plan: M2-T10, M13-T02, M13-T05.

### US-RUN-05 · Delegate to subagents (P1)
As a **builder**, I want my agent to delegate focused tasks to specialised agents or a focused copy of itself.
- `agents.delegate` allowed only to agents listed in `subagents.allowed` (resolved at publish) or `self` when `allow_self_clone`; depth ≤ `min(subagents.max_depth, 3)`; at most `max_parallel` children at once.
- Child runs share the conversation and user; approvals inside children appear in the same chat; children cannot write memory.
- The UI shows subagent cards (`subagent.started`/`subagent.completed`) and a run tree graph.
- Spec: spec 07 §7. Plan: M9-T01, M9-T04.

### US-RUN-06 · Start runs from the API (P0)
As an **integrator**, I want to start an agent run from my system and get the result.
- `POST /api/v1/runs` with an API key of a service account holding `chat:use`; modes: default `202`, `stream=true` (SSE), `wait=true` (up to 120 s).
- Optional `callback_url` receives a signed POST on completion (tenant run-callback secret, rotatable with step-up).
- Service accounts with `on_behalf_of` enabled may run as a named user (audited `run.started_on_behalf_of`).
- Spec: spec 06 §3 `POST /api/v1/runs`, [spec 20 §3.1](../03-specs/20-notifications-events.md#31-run-callback-secret). Plan: M2-T10.

### US-RUN-07 · Answer questions from the agent mid-run (P1)
As a **member**, I want to provide input when a tool needs it (MCP elicitation).
- `input.required` pauses the run (`waiting_input`); I answer through a generated form (`POST /api/v1/runs/{run_id}:input`); unanswered requests expire after `AR_INPUT_WAIT_TIMEOUT_S` and the tool call fails cleanly.
- Spec: stream-events, spec 07. Plan: M5-T05.

### US-RUN-08 · Large toolsets stay usable (P1)
As a **builder**, I want agents with many tools to pick the right ones without overloading the context.
- Above the tool threshold the model sees `tools.search` plus pinned tools and loads others on demand; tool selection accuracy is measured in evals.
- Spec: spec 07 §8. Plan: M4-T05.
