# M38 — Tool framework hardening

Goal: fix the tool-calling framework so that a strong model is not held back by it. Source:
[the tool review](../testing/tools-review-2026-11-05/tools-review.md), findings A1 to A12 and A14.

Depends on: M37. One pull request for each task. Paths are under `libs/ar_domain/src/ar_domain/` unless they
start with another top-level folder. Tests are under `libs/ar_domain/tests/unit/` unless stated.

Order: T01, T02 and T03 do not depend on each other. [M38a](M38a-one-model-path.md) follows T03 and is finished before T04. T04 follows T02. T05 to T08 follow T04. T02, T09, T10,
T12 and T13 are in strict order because they change the same call site (`tools/agent_loop.py`, the
`ToolPipeline.execute` call). T11 goes beside T10. T14 follows T06 and T08. T15 follows T10.

Out of scope: loading tools on demand, rewriting tool descriptions, new tools (M39). A container sandbox and a
real browser (M40). Token streaming to the client (M42). Moving state off the in-process store. Routing calls
through `mcp-gateway` (decision D4 of the November review).

## M38-T00 Review record and roadmap

**Do:** commit the review, this file, and the outline files for M39 to M42. Add the milestone rows and the
decisions.

**Done when:** `scripts/check_docs_links.py` passes and the plan README lists M38 to M42.

## M38-T01 Built-in reads stay inside the caller's tenant

**Spec:** [tenancy-isolation §5](../02-architecture/tenancy-isolation.md#5-mandatory-isolation-tests),
[spec 08](../03-specs/08-tool-registry-mcp.md).

**Do:**

- `conversations.search_history` returns only messages from the caller's own conversations in the caller's tenant.
- `control.search` ranks platform tools and the caller's tenant's tools, on approved current versions.
- `files.list` and `files.read` return only the caller's tenant's files. A file id from another tenant is `not_found`.

**Done when:** with two tenants in one store, none of the three tools returns the other tenant's rows.

**Tests:** `test_m38_tool_tenant_scope.py`.

## M38-T02 A handler failure is a tool error

**Spec:** [spec 08](../03-specs/08-tool-registry-mcp.md), [internal-apis](../05-contracts/internal-apis.md).

**Do:**

- Catch an exception raised by an in-process handler or a remote call in `tools/pipeline.py`. Return an
  `internal_error` tool result with a fixed message. Log the exception type and the tool name, and no content.
- Guard `ChatService.generate` and `orchestration/engine.py` `resume_run` so that a run that is still active
  when they exit with an exception is ended with an error.

**Done when:** a handler that raises produces a failed tool call the model can read, and the run reaches a
terminal state.

**Tests:** `test_m38_handler_guard.py`; `services/runtime/tests/unit/test_turn_activity.py`.

## M38-T03 Fixtures stay out of a production catalogue

**Spec:** [spec 08](../03-specs/08-tool-registry-mcp.md), [local-dev](../07-ops/local-dev.md).

**Do:**

- Seed the demo servers (tickets, echo, petstore, warehouse), the `desk` agent, `control.checkpoint`,
  `control.propose_change` and the canned `web.fetch` only where fake models are allowed.
- Move the dev and CI gate from `services/api/src/ar_api/main.py` to a shared helper. Every process that
  builds a store calls it.

**Done when:** a store built for `prod` has none of the fixtures, and the e2e specs that use them still pass in CI.

**Tests:** `test_m38_fixture_gate.py`.

## M38-T03a Browser tests retry in CI

**Spec:** [testing-strategy §6](../08-quality/testing-strategy.md#6-end-to-end-tests), [OQ-95](../open-questions.md).

**Do:** in CI, Playwright retries a failed test up to twice and reports a test that then passes as flaky. The
default wait for an element is ten seconds. There is no retry outside CI.

**Done when:** a single slow page no longer fails `web-e2e`, and a test that fails every try still does.

## M38-T04 Loop state in one place

**Depends on:** T02.

**Do:** move the loop's local variables into a `LoopState` with a checkpoint round trip, reusing
`save_checkpoint` and `restore_checkpoint` in `orchestration/engine.py`. Split the loop into a model step, a
tool batch and a finalise step. No behaviour changes.

**Done when:** `test_m21_loop.py` passes unchanged.

**Tests:** `test_m38_loop_state.py`.

## M38-T05 Tool guidance reaches every agent

**Depends on:** T04. **Spec:** [spec 07 §4](../03-specs/07-agent-runtime.md#4-context-assembly).

**Do:** move the guidance text to `prompts/text/tool_use.md`. `prompts/assembler.py` adds a tool-use block
when the agent has tools and an output-schema block when the definition has one. The fallback in
`workspace/turn.py` `opening_messages` uses the same builder.

**Done when:** the system prompt of a chat turn and of a child run both carry the guidance.

**Tests:** `test_m38_prompt_guidance.py`.

## M38-T06 Honest errors for bad model output

**Depends on:** T04.

**Do:**

- `models/logic.py` returns `finish_reason` and an argument error for each call whose JSON did not parse.
- The loop answers such a call with a `validation_failed` tool result. When `finish_reason` is `length` the
  message says the call was cut off at the output limit.
- `tools/logic.py` returns up to ten schema errors.
- Text beside a tool call is kept in history and emitted as a message delta.
- A call without an id gets `call_{step}_{index}`.

**Done when:** a model that sends broken JSON is told so and can retry.

**Tests:** `test_m38_model_output.py`.

## M38-T07 Limits that fit multi-step work

**Depends on:** T04. **Spec:** [definition-schema §12](../05-contracts/definition-schema.md#12-defaults),
[OQ-92](../open-questions.md).

**Do:**

- One default budget: 30 steps, 60 tool calls, 1,200 seconds, 600,000 tokens, 4 parallel calls, and a cost cap
  of 5,000,000 micros.
- Output tokens come from the model's request options, then the model row, then 8,192.
- Limits are checked before every tool batch. A stop keeps the partial answer and lists the calls that ran.
- The Temporal activity timeout follows the wall clock.
- Stored agent versions that carry the old defaults are raised by a seed step. An agent with its own budget is
  left as it is.

**Done when:** a task that needs twelve tool calls finishes on the default budget.

**Tests:** `test_m38_limits.py`.

## M38-T08 The model reads the whole result

**Depends on:** T04. **Spec:** [spec 07 §4](../03-specs/07-agent-runtime.md#4-context-assembly).

**Do:**

- The pipeline returns the result text after redaction. The loop wraps it once and gives it to the model, up
  to `context.toolResultMaxTokens`.
- A longer result is saved, redacted, to `/workspace/tool-results/<call>.txt` in the run workspace. The
  model gets the first part and a notice with the bytes cut, the path and the offset to read from.
- An agent without a file-reading tool is told to narrow the call.
- The preview stored for the UI stays short.

**Done when:** a 20 KB result is answerable from its last paragraph.

**Tests:** `test_m38_result_budget.py`.

## M38-T09 Tools run off the event loop, with a timeout

**Depends on:** T02, T08. **Spec:** [spec 07 §10](../03-specs/07-agent-runtime.md#10-configuration),
[environments §3](../07-ops/environments.md#3-variable-catalogue).

**Do:**

- New `tools/executor.py`. `ToolPipeline.execute` stays synchronous for its other callers and is split into
  prepare, invoke and record.
- Only invoke runs in a bounded thread pool (`AR_TOOL_WORKER_THREADS`), under the smaller of the tool's
  timeout and the wall clock that is left. Prepare and record stay on the loop thread, so event order, audit
  rows and usage are written from one thread.
- A call that overruns is recorded as `upstream_timeout`. Its late return is discarded. A write says that the
  outcome is unknown.
- Events raised from a worker thread are passed to the loop thread. Workspace writes take a lock for the run.

**Done when:** another coroutine makes progress while a handler sleeps.

**Tests:** `test_m38_executor.py`.

## M38-T10 Read-only calls run together

**Depends on:** T09. **Spec:** [stream-events §5](../05-contracts/stream-events.md).

**Do:** consecutive calls that are read-only and idempotent after policy run together, up to
`maxParallelToolCalls`. A write is a barrier. Started events are emitted in model order. Completions, audit
rows and tool messages are recorded in model order.

**Done when:** three slow reads in one step take about as long as one.

**Tests:** `test_m38_parallel_tools.py`.

## M38-T11 Stop stops the run

**Depends on:** T09.

**Do:** the store tracks the task of each run. `cancel_run` sets the flag and cancels the task. The loop
checks the flag before each step and each call. The run ends `cancelled` and keeps its partial text.

**Done when:** Stop during a long call ends an in-process run on a real model.

**Tests:** `test_m38_cancel.py`.

## M38-T12 An approval continues the turn

**Depends on:** T10. **Spec:** [spec 09](../03-specs/09-policy-approvals.md),
[spec 07](../03-specs/07-agent-runtime.md).

**Do:**

- At a pause, the checkpoint records the held call and the rest of the batch. `run["checkpoint"]` is already
  written to Postgres, so no migration is needed.
- A decision resumes the loop through the path `agents_ask` uses. Approved: the held call runs with the
  approval. Rejected or expired: the model receives that as the tool result. Then the rest of the batch runs
  and the model takes its next step.
- After M38a there is no scripted turn, so every paused run has loop state.

**Done when:** after an approval the model uses the result in a further step, and after a rejection it
answers without the call.

**Tests:** `test_m38_approval_resume.py`; update `test_m32_approvals_and_fake.py`.

## M38-T13 A write runs once

**Depends on:** T12. **Spec:** [spec 08](../03-specs/08-tool-registry-mcp.md).

**Do:** the MCP client retries only when the connection was not made, and does not retry a call that is not
idempotent. A finished write with the same run, call id and argument hash is returned from its record, with
`replayed: true`, and is not run again.

**Done when:** a retried turn does not repeat a completed write.

**Tests:** `test_m38_idempotency.py`.

## M38-T14 The turn fits the model's window

**Depends on:** T06, T08. **Spec:** [spec 07 §5](../03-specs/07-agent-runtime.md#5-context-management).

**Do:** `complete_turn` returns the provider's status. Only 429, 5xx and transport errors are retried. The
window comes from the model row. Above the threshold, tool results older than four steps are replaced with a
stub that names the saved file. On an overflow error the loop shrinks and tries once more. The summary that
replaces older turns is written by the agent's `fast` model; today it is built by rules in
`memory/compaction.py` `summarise` (fresh-tenant run, F44).

**Done when:** a turn whose results exceed the window completes.

**Tests:** `test_m38_context.py`.

## M38-T15 A repeated call is noticed

**Depends on:** T10. **Spec:** [internal-apis](../05-contracts/internal-apis.md).

**Do:** count calls with the same tool and argument hash. The third returns a `repeated_call` result without
running. The fifth ends the run. Read `AR_CONSECUTIVE_TOOL_ERROR_LIMIT` in place of the constant.

**Done when:** a model that loops on one call is stopped with a message that says why.

**Tests:** `test_m38_repeat_calls.py`.

## Exit

`make check` and `make test` pass. A live run recorded in `docs/testing/m38-checklist.md` shows: an answer
taken from past the first 2 KB of a fetched page, three reads in one step, an approved write followed by
further steps, a rejected write followed by another route, Stop during a long command, and a task of more than
eight calls.
