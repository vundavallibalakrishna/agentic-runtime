# PRD 04 — Chat

Members talk to agents in a streaming chat with files, tool activity, approvals, citations and artifacts. Spec: [spec 06](../03-specs/06-conversations-runs.md), [stream-events](../05-contracts/stream-events.md), UI [spec 19 §4](../03-specs/19-web-app.md#4-chat-components-normative-behaviour). Plan: [M2](../09-plan/M02-first-chat.md) (and UI parts of M4–M9).

### US-CHAT-01 · Start a conversation and see the answer stream (P0)
As a **member**, I want to pick an agent, send a message and see the answer appear token by token.
- `POST /api/v1/conversations` then `POST …/messages` returns `202` with `run_id`; the UI subscribes to `GET /api/v1/runs/{run_id}/events` (SSE) and renders `message.delta` events; first visible token within the TTFT budget ([performance-budgets §1](../08-quality/performance-budgets.md#1-service-level-objectives-production)).
- Markdown, code (highlighted), tables, math and Mermaid render safely (sanitised; no raw HTML).
- Spec: spec 06 §3, spec 07. Plan: M2-T06, M2-T08, M2-T09, M2-T11.

### US-CHAT-02 · Resume after disconnect (P0)
As a **member**, I want a dropped connection or page reload not to lose the answer.
- The SSE stream resumes with `Last-Event-ID`/`after_seq`; runs continue server-side regardless of the browser (durable workflows); on reload the conversation shows persisted messages plus the live tail.
- Spec: [stream-events §2](../05-contracts/stream-events.md#2-sse-framing-and-resume). Plan: M2-T08.

### US-CHAT-03 · Stop a run (P0)
As a **member**, I want to stop a long answer.
- **Stop** calls `POST /api/v1/runs/{run_id}:cancel`; the stream ends with `run.cancelled` within 2 s; partial text is kept and marked as stopped.
- Spec: spec 06 §3. Plan: M2-T10, M2-T11.

### US-CHAT-04 · Attach files (P0)
As a **member**, I want to attach documents and images to my message.
- Upload via presigned URL (`POST /api/v1/files` flow in spec 13) with progress; files are scanned and processed (`file.ready`); images are passed to vision-capable models, documents are readable by the agent through file tools.
- Per-file and per-message limits enforced with clear errors.
- Spec: [spec 13](../03-specs/13-files-artifacts.md). Plan: M2-T07, M2-T11.

### US-CHAT-05 · See tool activity, approvals and inputs inline (P0)
As a **member**, I want to see what the agent is doing.
- Tool calls render as collapsible cards (`tool_call.started` → `tool_call.completed|failed`) with arguments and result summaries; approval requests (`tool_call.approval_required`) show approve/reject buttons for eligible approvers; elicitation requests (`input.required`) render a form; plan updates show a checklist.
- Spec: stream-events, [spec 09](../03-specs/09-policy-approvals.md). Plan: M4-T10, M5-T07.

### US-CHAT-06 · Regenerate, edit and branch (P0)
As a **member**, I want to regenerate an answer or edit my earlier message and compare branches.
- `:regenerate` creates a sibling assistant message; `:edit` creates a sibling user message and a new run; `:activate` switches the active branch; the UI shows `< 2/3 >` navigation.
- Spec: spec 06 §3. Plan: M2-T12.

### US-CHAT-07 · Manage my conversations (P0)
As a **member**, I want to search, rename, pin, archive and delete conversations.
- List with search (title + message full text over my conversations), filters (agent, pinned, archived, shared with me); delete is soft (retention sweep purges later); preview conversations are hidden by default.
- Spec: spec 06 §3. Plan: M2-T06, M2-T11.

### US-CHAT-08 · Share and export (P1)
As a **member**, I want to share a read-only conversation with colleagues and export it.
- Shares to users, groups or teams in my tenant (`POST /api/v1/conversations/{conversation_id}/shares`); recipients see it under "Shared with me" and cannot post; revocation is immediate.
- Export as Markdown or JSON of the active branch (`GET …/export?format=markdown|json`); audited.
- Spec: spec 06 §3. Plan: M2-T12.

### US-CHAT-09 · Give feedback (P0)
As a **member**, I want to rate answers so that builders improve agents.
- Thumbs up/down with optional reasons and comment (`PUT /api/v1/messages/{message_id}/feedback`); builders see feedback in the agent's quality view ([US-EVAL-05](14-evaluation.md#us-eval-05--turn-feedback-into-test-cases-p1)).
- Spec: spec 06 §3, [spec 18](../03-specs/18-observability-eval.md). Plan: M2-T12, M13-T06.
