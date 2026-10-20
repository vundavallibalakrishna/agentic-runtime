# Run stream event schema

Every run (chat turn, API run, routine run, subagent) emits an ordered stream of events. Producers: `runtime-worker` (most events), `mcp-gateway` (none directly; it returns results to the runtime), `api` (`run.queued`). Transport: Valkey Stream `ar:run:{run_id}:events` (live) + table `run_events` (durable, excluding deltas) → SSE endpoint `GET /api/v1/runs/{run_id}/events` ([spec 06](../03-specs/06-conversations-runs.md)). Pydantic source of truth: `ar_contracts.stream` (`RunEvent` discriminated union on `type`); JSON Schema exported to `packages/api-client/src/stream-events.ts` by `make gen`.

## 1. Envelope

```json
{
  "id": "0192f0c4-...:17",
  "seq": 17,
  "type": "tool_call.completed",
  "run_id": "0192f0c4-...",
  "root_run_id": "0192f0c4-...",
  "conversation_id": "0192f0b9-...",
  "ts": "2026-10-20T04:12:33.120Z",
  "data": { }
}
```

| Field | Type | Notes |
|---|---|---|
| `id` | string | `{run_id}:{seq}`; used as SSE `id:` |
| `seq` | int | Strictly increasing per run, starting at 1, gapless. Assigned by the producer with `INCR ar:run:{run_id}:seq` (Valkey). |
| `type` | string | One of §3 (open enum; clients must ignore unknown types) |
| `run_id` | uuid | The run that emitted the event. Subagent events are emitted on the **subagent's** run stream and summarised on the parent stream via `subagent.*` events. |
| `root_run_id` | uuid | Top-level run |
| `conversation_id` | uuid \| null | |
| `ts` | RFC 3339 | Producer clock |
| `data` | object | Type-specific payload (§3) |

## 2. SSE framing and resume

```
id: 0192f0c4-...:17
event: tool_call.completed
data: {"id":"0192f0c4-...:17","seq":17,"type":"tool_call.completed",...}

```

- The server sends `: ping` comments every 15 s.
- Resume: client reconnects with `Last-Event-ID: {run_id}:{seq}` header or `?after_seq=17`. Server replays events with `seq > 17`: first from Valkey stream (retained 24 h, `MAXLEN ~ 20000`), falling back to `run_events` when Valkey has expired (deltas are then unavailable; the `message.completed` events carry full text so the UI converges).
- The stream ends (server closes) after a terminal event (`run.completed`, `run.failed`, `run.cancelled`, `run.budget_exceeded`) has been sent. If the run is already terminal on connect, the server replays and closes.
- Conversation-level stream `GET /api/v1/conversations/{conversation_id}/events` multiplexes all runs of a conversation (used by the chat page so that a run started from another tab/channel appears live); envelope identical, `Last-Event-ID` is `conv:{conversation_id}:{stream_id}` using the Valkey stream id of `ar:conv:{conversation_id}:events`.

## 3. Event types

### Run lifecycle

| type | data | Persisted |
|---|---|---|
| `run.queued` | `{agent_id, agent_version_id, trigger, input_message_id}` | yes |
| `run.started` | `{model_alias, budget: RunBudget, sandbox_id?}` | yes |
| `run.status` | `{status: "running"\|"waiting_approval"\|"waiting_input", reason?}` | yes |
| `run.usage` | `RunUsage` (cumulative: `tokens_in, tokens_out, cached_tokens, model_calls, tool_calls, cost_micros, sandbox_cpu_seconds, elapsed_ms`) | yes (throttled: at most 1 per 2 s) |
| `run.completed` | `{final_message_id, usage: RunUsage}` | yes |
| `run.failed` | `{error: {code, message, retriable}, usage}` | yes |
| `run.cancelled` | `{by: "user"\|"system", usage}` | yes |
| `run.budget_exceeded` | `{limit: "max_steps"\|"max_tokens"\|"max_cost_micros"\|"max_wall_clock_s"\|"max_tool_calls", usage}` | yes |

### Assistant output

| type | data | Persisted |
|---|---|---|
| `message.started` | `{message_id, role: "assistant", model_alias, reset?: bool}` (`reset: true` when a retried model step restarts the same message: the client clears the text accumulated so far) | yes |
| `message.delta` | `{message_id, text}` (append) | **no** |
| `reasoning.delta` | `{message_id, text}` (only when the agent definition sets `show_reasoning: true`) | **no** |
| `message.completed` | `{message_id, content: ContentPart[], tokens_in, tokens_out, finish_reason}` | yes |
| `citation.added` | `{message_id, citation: Citation}` | yes |

`Citation`: `{index, document_id, chunk_id, collection_id, title, uri, snippet, page_from?, page_to?, source_modified_at?}`.

### Tools

| type | data | Persisted |
|---|---|---|
| `tool_call.started` | `{tool_call_id, model_call_id, qualified_name, title, risk_class, arguments_preview}` (preview = redacted, truncated 2 KiB) | yes |
| `tool_call.progress` | `{tool_call_id, message, progress?: 0..1}` (from MCP progress notifications) | no |
| `tool_call.approval_required` | `{tool_call_id, approval_id, preview: ApprovalPreview, expires_at, approver_rule}` | yes |
| `tool_call.approval_resolved` | `{tool_call_id, approval_id, decision: "approved"\|"rejected"\|"expired"\|"cancelled", by_user_id?}` | yes |
| `input.required` | `{request_id, tool_call_id, message, requested_schema, expires_at}` (MCP elicitation surfaced to the user; run status becomes `waiting_input`; answered via `POST /api/v1/runs/{run_id}:input`) | yes |
| `input.resolved` | `{request_id, action: "accept"\|"decline"\|"cancel"\|"expired"}` | yes |
| `tool_call.completed` | `{tool_call_id, status: "succeeded", result_preview, result_file_id?, latency_ms}` | yes |
| `tool_call.failed` | `{tool_call_id, status: "failed"\|"denied"\|"rejected"\|"expired"\|"cancelled", error: {code, message}, policy_reasons?, connect_url?}` (`connect_url` present when `error.code = "credential_required"`: the UI shows a "Connect" button) | yes |

### Workspace, files, computer

| type | data | Persisted |
|---|---|---|
| `artifact.created` | `{file_id, name, mime_type, size_bytes, preview?}` | yes |
| `sandbox.status` | `{sandbox_id, status}` | yes |
| `sandbox.output` | `{tool_call_id, stream: "stdout"\|"stderr", text}` (chunked ≤ 4 KiB) | no |
| `browser.screenshot` | `{tool_call_id, file_id, url, title}` (live view of the agent's browser) | yes |
| `plan.updated` | `{items: PlanItem[]}` where `PlanItem = {id, title, status: "pending"\|"in_progress"\|"done"\|"cancelled"}` | yes |

### Subagents and memory

| type | data | Persisted |
|---|---|---|
| `subagent.started` | `{child_run_id, agent_id, agent_name, task_brief}` | yes |
| `subagent.completed` | `{child_run_id, status, result_summary (≤ 2 KiB), usage}` | yes |
| `memory.recalled` | `{fact_ids: uuid[], count}` | yes |
| `memory.saved` | `{fact_id, content, scope}` | yes |
| `context.compacted` | `{tokens_before, tokens_after}` | yes |

### Errors and heartbeats

| type | data | Persisted |
|---|---|---|
| `warning` | `{code, message}` (e.g. `model_fallback_used`, `tool_result_truncated`) | yes |
| `heartbeat` | `{}` (emitted every 10 s while a long tool runs; SSE pings are separate) | no |

## 4. Content parts (`ar_contracts.messages.ContentPart`)

```json
[
  {"type": "text", "text": "Here is the MTTR chart [1]."},
  {"type": "file", "file_id": "0192...", "name": "mttr.png", "mime_type": "image/png"},
  {"type": "image", "file_id": "0192...", "alt": "uploaded screenshot"},
  {"type": "tool_use", "tool_call_id": "0192...", "qualified_name": "jira.search_issues"},
  {"type": "citation_ref", "index": 1, "citation": { }},
  {"type": "tool_result", "tool_call_id": "0192...", "text": "<tool_result ...>...</tool_result>", "is_error": false}
]
```

User messages may contain `text`, `file`, `image`. Assistant messages may contain `text`, `file`, `tool_use`, `citation_ref`. Stored assistant `tool_use` parts also carry `arguments` (raw, needed to replay the conversation to the model); the public API strips `arguments` from `tool_use` parts (redacted arguments are available via `GET /api/v1/runs/{run_id}/tool-calls`). `role="tool"` messages contain only `tool_result` parts and are internal (stored for replay; not returned by default in `GET .../messages` unless `include=tool`).

## 5. Ordering guarantees

- Events within a run are totally ordered by `seq`.
- `tool_call.started` precedes `tool_call.approval_required` precedes `tool_call.approval_resolved` precedes `tool_call.completed|failed` for the same `tool_call_id`.
- `message.started` precedes all `message.delta` for that message; `message.completed` is last for that message.
- Exactly one terminal run event per run.

## 6. Client reducer (normative for the web app)

The web app keeps a `RunViewState` per run (zustand store `useRunStreams`), reduced from events: `messages[message_id].text += delta`; on `message.completed` replace text with `content`; tool calls keyed by `tool_call_id`; approvals keyed by `approval_id`; subagent child runs rendered as nested collapsible timelines (the UI opens the child's stream lazily when expanded).
