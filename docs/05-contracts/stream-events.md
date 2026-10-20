# Run stream event schema

Every run (chat turn, API run, routine run, subagent) emits an ordered stream of events. Producers: `runtime-worker` (most events), `mcp-gateway` (none directly; it returns results to the runtime), `api` (`run.queued`). Transport: Valkey Stream `ar:run:{run_id}:events` (live) + table `run_events` (durable, excluding deltas) → SSE endpoint `GET /api/v1/runs/{run_id}/events` ([spec 06](../03-specs/06-conversations-runs.md)). Pydantic source of truth: `ar_contracts.stream` (`RunEvent` discriminated union on `type`); JSON Schema exported to `packages/api-client/src/stream-events.ts` by `make gen`.

## 1. Envelope

```json
{
  "id": "0192f0c4-...:17",
  "seq": 17,
  "type": "tool_call.completed",
  "runId": "0192f0c4-...",
  "rootRunId": "0192f0c4-...",
  "conversationId": "0192f0b9-...",
  "ts": "2026-10-20T04:12:33.120Z",
  "data": { }
}
```

Property names are camelCase. The `type` value stays the identifier in §3 (`tool_call.completed`), which is not a property name ([ADR-0026](../02-architecture/adr/ADR-0026-public-json-camel-case.md)).

| Field | Type | Notes |
|---|---|---|
| `id` | string | `{run_id}:{seq}`; used as SSE `id:` |
| `seq` | int | Strictly increasing per run, starting at 1, gapless. Assigned by the producer with `INCR ar:run:{run_id}:seq` (Valkey). |
| `type` | string | One of §3 (open enum; clients must ignore unknown types) |
| `runId` | uuid | The run that emitted the event. Subagent events are emitted on the **subagent's** run stream and summarised on the parent stream via `subagent.*` events. |
| `rootRunId` | uuid | Top-level run |
| `conversationId` | uuid \| null | |
| `ts` | RFC 3339 | Producer clock |
| `data` | object | Type-specific payload (§3) |

## 2. SSE framing and resume

```
id: 0192f0c4-...:17
event: tool_call.completed
data: {"id":"0192f0c4-...:17","seq":17,"type":"tool_call.completed",...}

```

- The server sends `: ping` comments every 15 s.
- Resume: client reconnects with `Last-Event-ID: {runId}:{seq}` header or `?after_seq=17`. Server replays events with `seq > 17`: first from Valkey stream (retained 24 h, `MAXLEN ~ 20000`), falling back to `run_events` when Valkey has expired (deltas are then unavailable; the `message.completed` events carry full text so the UI converges).
- The stream ends (server closes) after a terminal event (`run.completed`, `run.failed`, `run.cancelled`, `run.budget_exceeded`) has been sent. If the run is already terminal on connect, the server replays and closes.
- Conversation-level stream `GET /api/v1/conversations/{conversation_id}/events` multiplexes all runs of a conversation (used by the chat page so that a run started from another tab/channel appears live); envelope identical, `Last-Event-ID` is `conv:{conversation_id}:{stream_id}` using the Valkey stream id of `ar:conv:{conversation_id}:events`.

## 3. Event types

### Run lifecycle

| type | data | Persisted |
|---|---|---|
| `run.queued` | `{agentId, agentVersionId, trigger, inputMessageId}` | yes |
| `run.started` | `{modelAlias, budget: RunBudget, sandboxId?}` | yes |
| `run.status` | `{status: "running"\|"waiting_approval"\|"waiting_input", reason?}` | yes |
| `run.usage` | `RunUsage` (cumulative: `tokensIn, tokensOut, cachedTokens, modelCalls, toolCalls, costMicros, sandboxCpuSeconds, elapsedMs`) | yes (throttled: at most 1 per 2 s) |
| `run.completed` | `{finalMessageId, usage: RunUsage}` | yes |
| `run.failed` | `{error: {code, message, retriable}, usage}` | yes |
| `run.cancelled` | `{by: "user"\|"system", usage}` | yes |
| `run.budget_exceeded` | `{limit: "max_steps"\|"max_tokens"\|"max_cost_micros"\|"max_wall_clock_s"\|"max_tool_calls", usage}` | yes |

### Assistant output

| type | data | Persisted |
|---|---|---|
| `message.started` | `{messageId, role: "assistant", modelAlias, reset?: bool}` (`reset: true` when a retried model step restarts the same message: the client clears the text accumulated so far) | yes |
| `message.delta` | `{messageId, text}` (append) | **no** |
| `reasoning.delta` | `{messageId, text}` (only when the agent definition sets `showReasoning: true`) | **no** |
| `message.completed` | `{messageId, content: ContentPart[], tokensIn, tokensOut, finishReason}` | yes |
| `citation.added` | `{messageId, citation: Citation}` | yes |

`Citation`: `{index, documentId, chunkId, collectionId, title, uri, snippet, pageFrom?, pageTo?, sourceModifiedAt?}`.

### Tools

| type | data | Persisted |
|---|---|---|
| `tool_call.started` | `{toolCallId, modelCallId, qualifiedName, title, riskClass, argumentsPreview}` (preview = redacted, truncated 2 KiB) | yes |
| `tool_call.progress` | `{toolCallId, message, progress?: 0..1}` (from MCP progress notifications) | no |
| `tool_call.approval_required` | `{toolCallId, approvalId, preview: ApprovalPreview, expiresAt, approverRule}` | yes |
| `tool_call.approval_resolved` | `{toolCallId, approvalId, decision: "approved"\|"rejected"\|"expired"\|"cancelled", byUserId?}` | yes |
| `input.required` | `{requestId, toolCallId, message, requestedSchema, expiresAt}` (MCP elicitation surfaced to the user; run status becomes `waiting_input`; answered via `POST /api/v1/runs/{run_id}:input`) | yes |
| `input.resolved` | `{requestId, action: "accept"\|"decline"\|"cancel"\|"expired"}` | yes |
| `tool_call.completed` | `{toolCallId, status: "succeeded", resultPreview, resultFileId?, latencyMs}` | yes |
| `tool_call.failed` | `{toolCallId, status: "failed"\|"denied"\|"rejected"\|"expired"\|"cancelled", error: {code, message}, policyReasons?, connectUrl?}` (`connectUrl` present when `error.code = "credential_required"`: the UI shows a "Connect" button) | yes |

### Workspace, files, computer

| type | data | Persisted |
|---|---|---|
| `artifact.created` | `{fileId, name, mimeType, sizeBytes, preview?}` | yes |
| `sandbox.status` | `{sandboxId, status}` | yes |
| `sandbox.output` | `{toolCallId, stream: "stdout"\|"stderr", text}` (chunked ≤ 4 KiB) | no |
| `browser.screenshot` | `{toolCallId, fileId, url, title}` (live view of the agent's browser) | yes |
| `plan.updated` | `{items: PlanItem[]}` where `PlanItem = {id, title, status: "pending"\|"in_progress"\|"done"\|"cancelled"}` | yes |

### Subagents and memory

| type | data | Persisted |
|---|---|---|
| `subagent.started` | `{childRunId, agentId, agentName, taskBrief}` | yes |
| `subagent.completed` | `{childRunId, status, resultSummary (≤ 2 KiB), usage}` | yes |
| `memory.recalled` | `{factIds: uuid[], count}` | yes |
| `memory.saved` | `{factId, content, scope}` | yes |
| `context.compacted` | `{tokensBefore, tokensAfter}` | yes |

### Errors and heartbeats

| type | data | Persisted |
|---|---|---|
| `warning` | `{code, message}` (e.g. `model_fallback_used`, `tool_result_truncated`) | yes |
| `heartbeat` | `{}` (emitted every 10 s while a long tool runs; SSE pings are separate) | no |

## 4. Content parts (`ar_contracts.messages.ContentPart`)

```json
[
  {"type": "text", "text": "Here is the MTTR chart [1]."},
  {"type": "file", "fileId": "0192...", "name": "mttr.png", "mimeType": "image/png"},
  {"type": "image", "fileId": "0192...", "alt": "uploaded screenshot"},
  {"type": "tool_use", "toolCallId": "0192...", "qualifiedName": "jira.search_issues"},
  {"type": "citation_ref", "index": 1, "citation": { }},
  {"type": "tool_result", "toolCallId": "0192...", "text": "<tool_result ...>...</tool_result>", "isError": false}
]
```

User messages may contain `text`, `file`, `image`. Assistant messages may contain `text`, `file`, `tool_use`, `citation_ref`. Stored assistant `tool_use` parts also carry `arguments` (raw, needed to replay the conversation to the model); the public API strips `arguments` from `tool_use` parts (redacted arguments are available via `GET /api/v1/runs/{run_id}/tool-calls`). `role="tool"` messages contain only `tool_result` parts and are internal (stored for replay; not returned by default in `GET .../messages` unless `include=tool`).

## 5. Ordering guarantees

- Events within a run are totally ordered by `seq`.
- `tool_call.started` precedes `tool_call.approval_required` precedes `tool_call.approval_resolved` precedes `tool_call.completed|failed` for the same `toolCallId`.
- `message.started` precedes all `message.delta` for that message; `message.completed` is last for that message.
- Exactly one terminal run event per run.

## 6. Client reducer (normative for the web app)

The web app keeps a `RunViewState` per run (zustand store `useRunStreams`), reduced from events: `messages[messageId].text += delta`; on `message.completed` replace text with `content`; tool calls keyed by `toolCallId`; approvals keyed by `approvalId`; subagent child runs rendered as nested collapsible timelines (the UI opens the child's stream lazily when expanded).

## 7. Grounding and evidence citations (M7-T11)

`Citation` in §3 gains optional fields. When they are absent, `sourceKind` defaults to `knowledge` and `documentId`, `chunkId`, `collectionId` stay required. When `sourceKind` is `tool_result`, `toolCallId` is required and the document fields are omitted. When `sourceKind` is `evidence_item`, `evidenceItemId` is required and the document fields are omitted.

```json
{"index": 2, "sourceKind": "tool_result", "toolCallId": "0192...", "title": "jira.search_issues", "snippet": "..."}
```

| type | data | Persisted |
|---|---|---|
| `message.grounding_checked` | `{messageId, mode, grounded, removed}` | yes |

Content parts gain `{"type":"grounding","report": GroundingReport}` on assistant messages. The report shape is [spec 07 §13](../03-specs/07-agent-runtime.md#13-strict-grounding). Clients that do not know the part type ignore it, the same rule as unknown stream events.
