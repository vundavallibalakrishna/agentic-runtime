# Spec 07: Agent runtime (`runtime-worker`)

Deployable `runtime-worker` (`services/runtime`, package `ar_runtime`), Temporal task queue `ar-runtime`. Executes every run (chat, API, channel, routine, subagent, eval) as `AgentRunWorkflow`. Writes `runs`, `run_steps`, `run_events`, `messages`, `tool_calls` (control tools), `conversations.plan/rolling_summary` through `ar_domain` services. Decisions: [ADR-0003](../02-architecture/adr/ADR-0003-temporal-durable-runs.md), [ADR-0004](../02-architecture/adr/ADR-0004-custom-agent-loop.md). Stream contract: [stream-events.md](../05-contracts/stream-events.md). Flow diagrams: [request-flows.md](../02-architecture/request-flows.md).

## 1. Responsibilities

1. Durable agent loop: plan → model call → tool calls (parallel, policy-checked, approval-gated) → observe → repeat until final answer, budget, cancel or failure.
2. Context assembly and management: prompt layout, history window, rolling summary compaction, tool-result offloading, memory recall, optional auto-retrieval, tool search.
3. Streaming of every observable step to Valkey (live) and `run_events` (durable).
4. Subagent delegation via child workflows with budget inheritance and depth/parallelism limits.
5. Human-in-the-loop waits: approvals (`waiting_approval`) and MCP elicitation (`waiting_input`).
6. Budgets, kill switches, cancellation, and failure classification.
7. Finalisation: final message, title, usage, outbox events (memory extraction, routine delivery, webhooks).

The runtime never calls tools directly except control tools; all other tools go through `mcp-gateway` `POST /internal/v1/tool-calls:execute`. It never calls model engines directly; only `model-gateway`.

## 2. Workflow: `AgentRunWorkflow`

- Id `run-{run_id}`, queue `ar-runtime`, `id_reuse_policy=REJECT_DUPLICATE`, execution timeout = `budget.max_wall_clock_s + max approval wait + 1 h` (computed at start).
- Input `RunWorkflowInput {run_id, tenant_id}` (everything else is loaded by activities; workflow history never contains prompts, arguments or results; only ids, counters, and small enums).
- Data converter: `temporalio.contrib.pydantic.pydantic_data_converter`.
- Signals: `cancel(CancelSignal{reason, by_user_id?})`, `approval_decided(ApprovalSignal{approval_id, decision})`, `user_input(UserInputSignal{request_id, action, content?})`.
- Queries: `state() -> RunWorkflowState {status, step, usage, pending_approval_ids, pending_input_request_id, active_children}`.
- Child workflows: subagents (same workflow type) with `parent_close_policy=REQUEST_CANCEL`.

### 2.1 Loop (normative pseudocode)

```python
@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    @workflow.run
    async def run(self, inp: RunWorkflowInput) -> RunResult:
        ctx = await act(start_run, inp.run_id)            # status running, emits run.started; returns RunStartInfo (budget, flags, depth)
        self.usage = RunUsage.zero(); self.deadline = workflow.now() + ctx.budget.max_wall_clock_s
        if ctx.memory_enabled:  await act(recall_memory, inp.run_id)          # emits memory.recalled
        if ctx.auto_retrieve:   await act(auto_retrieve_knowledge, inp.run_id)
        model_failures = 0
        while True:
            self.check_budget_and_cancel()                # raises BudgetExceeded / Cancelled
            if await act(needs_compaction, inp.run_id):   # cheap estimate
                await act(compact_context, inp.run_id)    # emits context.compacted
            try:
                step = await act(model_step, ModelStepInput(run_id=inp.run_id, step_seq=self.next_seq(),
                                  use_fast_alias=model_failures >= 2 and ctx.degrade_to_fast))
                model_failures = 0
            except ActivityError as e:
                model_failures += 1
                if model_failures > 3 or non_retryable(e): raise
                continue
            self.usage.add(step.usage)
            if not step.tool_calls:                       # final answer
                break
            self.check_budget_and_cancel(pending_tool_calls=len(step.tool_calls))
            await self.run_tool_batch(inp.run_id, step.tool_calls, ctx)
        if ctx.trigger == "routine":                   # deterministic delivery phase (spec 15 §4)
            calls = await act(build_delivery_calls, inp.run_id)   # tool_calls rows for delivery.* tools
            await self.run_tool_batch(inp.run_id, calls, ctx)
        return await act(finalize_run, FinalizeInput(run_id=inp.run_id, outcome="completed", usage=self.usage))
```

- `run_tool_batch`: runs up to `budget.max_parallel_tool_calls` concurrently (`asyncio.gather` over activities / child workflows). Each item:
  1. Control tools → handled in-workflow (§6, §7) after `act(evaluate_control_tool)` (policy + `tool_calls` row).
  2. Other tools → `act(execute_tool_call, {run_id, tool_call_id})`. Outcome statuses:
     - `succeeded|failed|denied` → done.
     - `requires_approval` → set status `waiting_approval` (`act(set_run_status)`), `await workflow.wait_condition(lambda: approval_id in self.decisions, timeout=expires_at - now)`; timeout → `act(expire_approval)`. Approved → call `execute_tool_call` again (gateway consumes approval). Rejected/expired → tool result to model: `"The user rejected this action."` / `"Approval expired; the action was not performed."` (status `rejected`/`expired`). After all waits resolve → status back to `running`.
     - `input_required` → if `ctx.interactive` (trigger chat/api/channel with a user): emit `input.required`, status `waiting_input`, wait for `user_input` signal (timeout `AR_INPUT_WAIT_TIMEOUT_S`, default 1800 s), then re-execute with `input_responses`. Non-interactive (routine, eval) → auto-respond `decline`.
     - `credential_required` → result to model: `"The user has not connected <provider>. Ask them to connect it via the Connect button."`; emitted `tool_call.failed` carries `connect_url`. Routine runs notify the routine owner (notification `credential_required`).
- Wall-clock budget excludes time spent in `waiting_approval`/`waiting_input` (tracked by `self.paused_seconds`).
- `check_budget_and_cancel` is evaluated before every model step and every tool batch; on exceed → `finalize_run(outcome="budget_exceeded", limit=...)`; the partial assistant text so far is preserved and a final note `"(Stopped: <limit> budget reached.)"` is appended.
- Cancellation: `cancel` signal sets a flag and cancels the current cancellation scope (in-flight activities receive `CancelledError` through heartbeats; children get cancel requests); pending approvals → `cancelled`; `finalize_run(outcome="cancelled")`.
- History guard: if `workflow.info().get_current_history_length() > 20000`, `continue_as_new` with `RunWorkflowInput{run_id, tenant_id, resume: ResumeState{usage, seq, paused_seconds, model_failures}}`.
- Determinism: only workflow APIs for time/randomness; all I/O in activities; changes guarded by `workflow.patched("<id>")`; replay tests (§12).

### 2.2 Activities (all on `ar-runtime`)

| Activity | Purpose | start_to_close | Heartbeat | Retry |
|---|---|---|---|---|
| `start_run` | Load run + `AgentRuntimeConfig`, verify agent not disabled and user still active, set `running`, `started_at`, emit `run.started` | 30 s | – | 5×, 1 s→10 s |
| `recall_memory` | [spec 11](11-memory.md) `memory.service.recall`; store recalled ids on run context cache | 20 s | – | 3× ; failure → warning, continue |
| `auto_retrieve_knowledge` | `knowledge.service.search` with the user message; stores hits for context | 30 s | – | 3× ; failure → warning |
| `needs_compaction` | Token estimate of next prompt vs threshold | 10 s | – | 3× |
| `compact_context` | §5 | 120 s | 10 s | 3× |
| `model_step` | §4 + §3: assemble, call gateway (streaming), persist | `model.params` timeout (default 300 s) | 10 s | 3×, 2 s→30 s, non-retryable: `context_length_exceeded`, `model_capability_missing`, `quota_exceeded`, `agent_disabled`, `content_filtered` |
| `evaluate_control_tool` | Policy + `tool_calls` row for control tools | 10 s | – | 3× |
| `execute_tool_call` | Call `mcp-gateway` `tool-calls:execute`; persist; emit events | tool `timeout_s` + 30 s | 10 s (relays `tool_call.progress`/`heartbeat`) | 3× only if the tool is `idempotent` or the error is a transport error before the request was accepted; else 1 attempt |
| `set_run_status` | Update status + emit `run.status` | 10 s | – | 5× |
| `expire_approval` | Mark approval expired, tool call `expired`, emit `tool_call.approval_resolved` | 10 s | – | 5× |
| `create_child_run` | §7 | 20 s | – | 5× |
| `apply_plan_update` | §6 | 10 s | – | 5× |
| `search_tools` | §8 | 20 s | – | 3× |
| `build_delivery_calls` | Routine runs: one `delivery.*` tool call per routine delivery target ([spec 15 §4](15-routines-triggers.md#4-delivery-phase-in-agentrunworkflow-for-triggerroutine)) | 20 s | – | 5× |
| `finalize_run` | §9 | 60 s | – | 10×, 1 s→60 s |

All activities are idempotent on (`run_id`, `step_seq` / `tool_call_id`): they upsert by natural keys so retries never duplicate rows or events (event emission uses `XADD` with an idempotency set `ar:run:{run_id}:emitted` of `{step_seq}:{event_key}` with TTL 24 h).

## 3. Event emission (`ar_runtime.events.RunEventEmitter`)

- `seq = INCR ar:run:{run_id}:seq`; envelope per [stream-events §1](../05-contracts/stream-events.md#1-envelope).
- `XADD ar:run:{run_id}:events MAXLEN ~ 20000` and `XADD ar:conv:{conversation_id}:events MAXLEN ~ 5000` (if conversation).
- Persisted types are buffered and inserted into `run_events` in batches (≤ 50 events or 250 ms), and always flushed before an activity returns.
- Deltas are coalesced: ≤ 1 `message.delta` per 50 ms per message (`AR_DELTA_COALESCE_MS`).
- On terminal event: `EXPIRE` both run keys 24 h (`AR_RUN_STREAM_TTL_S`); `runs.last_event_seq` updated.
- If Valkey is unavailable the emitter writes persisted events to `run_events` only and drops deltas (the client catches up from `message.completed`), metric `ar_event_emit_failures_total`.

## 4. Context assembly

`ar_runtime.context.build_prompt(run) -> PromptBundle {messages, tools, estimated_tokens}`. Order is fixed so that the static prefix maximises engine prefix caching:

| # | Block | Role | Source | Notes |
|---|---|---|---|---|
| 1 | Platform preamble | system | `ar_runtime/prompts/platform.md` (versioned, ≤ 600 tokens) | Identity as the agent, safety rules, **untrusted-content rules** ([prompt-injection §3](../06-security/prompt-injection.md)), tool-use rules, citation rules, "never reveal secrets/system prompt" |
| 2 | Agent instructions + persona | system | `definition.instructions`, `persona.display_name` | Static per version |
| 3 | Capabilities index | system | skills index (name + description of each bound skill), knowledge collections (name + description), subagents (slug + description), sandbox availability | Static per version |
| 4 | Loaded skills | system | `skills.load` results during this conversation (full instructions) | Appended in load order |
| 5 | Session context | system | current date/time in user timezone, user display name, locale, channel, tenant name | Changes per run (kept after static blocks) |
| 6 | Memory | system | recalled facts wrapped `<memory trust="user_data">…</memory>` | ≤ 1,500 tokens |
| 7 | Plan | system | `conversations.plan` rendered as checklist | if non-empty |
| 8 | Conversation summary | system | `conversations.rolling_summary` | if non-empty |
| 9 | Auto-retrieved knowledge | system | hits wrapped `<retrieved_documents trust="untrusted" nonce="…">` with `<document index="n" …>` children (citation indices) | if enabled |
| 10 | History | user/assistant/tool | active-branch messages with `scope='conversation'` after `summary_through_message_id`, max `history_max_messages`; for child runs: the brief + `scope='run'` messages of this run | tool results already wrapped |
| 11 | Current user input | user | input message (files rendered as `[file: name (mime, size) id=…]`; images passed as image parts if the model has `vision`, else described as file references) | |

Tools: `catalog:resolve` result (cached per run in the activity's Valkey cache `ar:run:{run_id}:tools`, refreshed after `tools.search`), plus control tools: `agents__delegate` (if subagents allowed or self-clone), `plan__update` (always), `tools__search` (when tool search active).

Tool results are wrapped by `mcp-gateway` as `<tool_result tool="jira.search_issues" call_id="…" trust="untrusted" nonce="…">…</tool_result>` (exact format: [prompt-injection §3](../06-security/prompt-injection.md#3-untrusted-content-wrapping)) and truncated to `context.tool_result_max_tokens` with a trailer `[truncated: full result in file <id>; use files__read to page]`.

Citations: knowledge hits are numbered per run (`[1]`, `[2]`…) and the model is instructed to cite with `[n]`. `model_step` parses `[n]` markers in the final text, emits `citation.added` for each valid index, and stores `citation_ref` parts. With `output.citations=required` and no citations while knowledge was retrieved, one corrective re-prompt is made ("Cite sources or state that none were found").

## 5. Context management

- **Threshold**: `estimated_tokens > compaction_threshold * context_window(model)` → compaction.
- **Compaction** (`compact_context`): (a) fold the oldest history messages (all but the last 6 turns) into `rolling_summary` using `fast_alias` with prompt `ar_runtime/prompts/compaction.md` (keeps decisions, facts, open tasks, file ids, citations); update `summary_through_message_id`; (b) within the current run, replace tool results older than the last 4 steps with stubs `[earlier result of <tool>: <preview ≤ 300 chars>; file <id>]`. Emits `context.compacted`, writes `run_steps(kind='compaction')`.
- **Offloading**: any tool result beyond `tool_result_max_tokens` is stored as `files(kind='tool_result')` by `mcp-gateway`; the model can page it with `files__read {file_id, offset, limit}`.
- If after compaction the prompt still exceeds the window → fail the step with `context_length_exceeded` (non-retryable) and finalize `failed` with a user-facing message suggesting a new conversation.

## 6. Planning (`plan.update`)

Schema: `{items: [{id?: string, title: string (≤ 200), status: "pending"|"in_progress"|"done"|"cancelled"}] (≤ 30)}` replaces the plan. Stored in `conversations.plan` (or run-local for child runs, in `run_steps.detail`), emits `plan.updated`, returns `"Plan updated."`. The platform preamble instructs: for tasks needing ≥ 3 steps, create a plan first and keep it current.

## 7. Subagents (`agents.delegate`)

Model-facing schema:

```json
{"type":"object","required":["agent","task"],"properties":{
  "agent":{"type":"string","description":"Slug of an allowed subagent, or \"self\" for a focused copy of yourself"},
  "task":{"type":"string","maxLength":8000,"description":"Self-contained brief: goal, inputs, constraints, expected output"},
  "tools":{"type":"array","items":{"type":"string"},"description":"(self only) subset of your tools the copy may use"},
  "expected_output":{"type":"string","maxLength":1000},
  "files":{"type":"array","items":{"type":"string"},"maxItems":20,"description":"file ids to share"}}}
```

Rules:
1. `agent` must be in `subagents.allowed` (resolved at publish) or `self` with `allow_self_clone`; `depth + 1 ≤ min(subagents.max_depth, 3)`; concurrently running children ≤ `max_parallel` (extra calls wait in the batch).
2. `create_child_run` inserts `runs` (trigger `subagent`, `parent_run_id`, `root_run_id`, `depth+1`, same `user_id`, same `conversation_id`), an input message (`scope='run'`) with the brief, and returns `child_run_id`; emits `subagent.started` on the parent.
3. Child budget = element-wise `min(child definition budget, parent remaining)`; self-clone uses the parent definition with `tools` narrowed (must be a subset; control tool `agents__delegate` removed when depth limit reached).
4. Parent starts child workflow `AgentRunWorkflow(run-{child_run_id})` and awaits the result `RunResult {status, final_text (≤ 8,000 chars), file_ids, usage}`; adds child usage to its own; emits `subagent.completed`; tool result to the model = final text + file references. A failed child returns `is_error` with the error message.
5. Approvals/elicitations inside a child appear on the conversation stream (child runs share `conversation_id`) and are decided the same way.
6. Memory writes from children are disabled (`memory.save` denied in child runs) to avoid duplicate facts; recall allowed.

## 8. Tool search

Active when `tool_search.mode = on`, or `auto` and the agent has > 30 tools. Initial set = control tools + tools marked `pinned: true` in the agent definition override + top `tool_search.top_k` by semantic similarity of the user message (`catalog:resolve` with `query`). `tools__search {query}` returns up to 10 `{name, description}` and adds them to the run's tool set (max 40 loaded tools; oldest unused evicted).

## 9. Finalisation (`finalize_run`)

1. Determine the final assistant message (last `model_step` without tool calls) → `runs.result_summary` (≤ 8,000 chars), status, `ended_at`, `usage`.
2. Title: if the conversation title is empty → `fast_alias` (purpose `title`, ≤ 60 chars, language of the conversation).
3. `conversations.active_run_id = NULL`, `last_message_at`.
4. `usage_events(metric='runs', quantity=1)` (+ sandbox seconds reported by tool results).
5. Outbox: `run.completed|run.failed|run.cancelled|run.budget_exceeded` (subscribers: `MemoryExtractionWorkflow` start when memory extraction is enabled and trigger ≠ `eval`; `RoutineRunWorkflow` delivery; channel reply; webhooks; API `callback_url`).
6. Emit terminal event; expire stream keys.

Error classification for `runs.error.code`: `model_unavailable`, `context_length_exceeded`, `tool_error_limit` (more than 8 consecutive failed tool calls), `agent_disabled`, `user_deactivated`, `quota_exceeded`, `delegation_expired`, `internal_error`.

## 10. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AR_TEMPORAL_ADDRESS` | `localhost:7233` | |
| `AR_TEMPORAL_NAMESPACE` | `agentic-runtime` | One namespace per environment; dedicated tenants may get their own (`AR_TENANT_TEMPORAL_NAMESPACES`) |
| `AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES` | `200` | Per worker process |
| `AR_RUNTIME_MAX_CONCURRENT_WORKFLOW_TASKS` | `100` | |
| `AR_MODEL_GATEWAY_URL` | `http://localhost:8001` | |
| `AR_MCP_GATEWAY_URL` | `http://localhost:8002` | |
| `AR_INPUT_WAIT_TIMEOUT_S` | `1800` | Elicitation wait |
| `AR_DELTA_COALESCE_MS` | `50` | |
| `AR_RUN_STREAM_TTL_S` | `86400` | |
| `AR_MAX_DEPTH` | `3` | Platform cap for subagents |
| `AR_CONSECUTIVE_TOOL_ERROR_LIMIT` | `8` | |

## 11. Metrics

`ar_runtime_steps_total{kind,status}`, `ar_runtime_model_step_seconds`, `ar_runtime_ttft_seconds` (activity start → first delta), `ar_runtime_tool_batch_size`, `ar_runtime_approval_wait_seconds`, `ar_runtime_compactions_total`, `ar_runtime_subagents_total{status}`, `ar_runtime_budget_exceeded_total{limit}`, `ar_event_emit_failures_total`; Temporal SDK metrics exported via Prometheus. Each run is one OTel trace (`trace_id` saved on the run): spans `run`, `model_step`, `tool_call`, `subagent` (child trace linked).

## 12. Test plan

- Unit: prompt layout snapshot tests (inline-snapshot) per block; budget arithmetic incl. paused time; citation parser; compaction stub replacement; tool name mapping `server__tool`.
- Workflow tests (`temporalio.testing.WorkflowEnvironment` time-skipping) with mocked activities: final answer path; parallel tool batch limit; approval approve/reject/timeout; elicitation accept/decline; cancel during model step, during approval, during child; budget exceeded for each limit; continue-as-new resume; degrade to fast alias after 2 failures.
- Replay tests: recorded histories in `services/runtime/tests/replay/*.json` replayed with `Replayer` on every PR (guards determinism).
- Integration (testcontainers + `fake-llm` scripted scenarios in `services/fake_llm/scenarios/*.yaml`): chat turn end-to-end with SSE; tool call through `mcp-gateway` with an in-repo test MCP server (`ar_testing.mcp_echo`); subagent delegation; compaction triggered by small `context_window`.
- Eval smoke (M13): golden suite runs nightly against real models.
