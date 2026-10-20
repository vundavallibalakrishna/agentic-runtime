# M2 — Model gateway & first chat

Goal: the first vertical slice. A user chats with the default `assistant` agent; tokens stream from a company model (fake-llm in dev/CI) through `model-gateway`, the run is a durable `AgentRunWorkflow`, events stream over SSE, files can be attached, and usage is metered.

Exit criteria: Playwright: log in → new chat → message → streamed answer → stop button cancels a long answer → regenerate → upload a PDF and reference it. Killing `runtime-worker` mid-answer and restarting it completes the run.

---

### M2-T01 · Revision 0006 `models` and model registry API
- **Depends on:** M1-T15
- **Areas:** `ar_domain/models/**`, migration 0006, `ar_api/routers/{models.py,platform_models.py}`, seed of platform aliases
- **Spec:** [spec 04 §4](../03-specs/04-model-gateway.md#4-registry-api-served-by-api), [schema §3](../04-data/schema.md#3-models-ar_domainmodels)
- **Do:** Tables of schema §3 (platform rows `tenant_id NULL`, platform-or-own RLS); registry service with alias resolution order (tenant alias → platform alias), capability checks, provider credentials via secrets; tenant endpoints `GET/POST /api/v1/model-providers`, `PATCH/DELETE /api/v1/model-providers/{provider_id}`, `POST /api/v1/model-providers/{provider_id}:test`, `GET/POST /api/v1/models`, `PATCH/DELETE /api/v1/models/{model_id}`, `GET/POST /api/v1/model-aliases`, `PATCH/DELETE /api/v1/model-aliases/{alias_id}`, `POST /api/v1/model-aliases/{alias_id}:test`; platform endpoints under `/api/v1/platform/model-providers`, `/api/v1/platform/models`, `/api/v1/platform/model-aliases` (GET/POST/PATCH/DELETE). Seed (dev) a `fake-llm` provider and aliases `reasoning`, `fast`, `vision`, `embed`, `rerank`.
- **Done when:** a tenant alias overrides the platform alias; provider URLs inside `AR_MODEL_PROVIDER_DENY_CIDRS` are rejected.
- **Tests:** integration per endpoint; resolution-order unit tests; `:test` against fake-llm.

### M2-T02 · Revision 0007 `usage` and usage recording
- **Depends on:** M2-T01
- **Areas:** `ar_domain/usage/{models.py,repository.py,service.py}`, migration 0007, `ar_system/workflows/usage_rollup.py`
- **Spec:** [spec 17 §2.1, §2.3](../03-specs/17-audit-usage-metering.md#2-usage-metering), [schema §15](../04-data/schema.md#15-audit-and-usage-ar_domainaudit-ar_domainusage)
- **Do:** `usage_events`, `usage_daily`, `quotas` tables; `usage.service.record(...)` (idempotent by `dedupe_key`, cost from plan `unit_prices`); `UsageRollupWorkflow` (Temporal Schedule every `AR_USAGE_ROLLUP_INTERVAL`, upsert into `usage_daily` by tenant timezone). Quota enforcement and reports land in M12.
- **Done when:** duplicate records are ignored; rollup is idempotent over the same window.
- **Tests:** integration: dedupe, rollup correctness across midnight in `Asia/Kolkata` tenant timezone (time-machine).

### M2-T03 · `model-gateway` service
- **Depends on:** M2-T02, M0-T07
- **Areas:** `services/model_gateway/src/ar_model_gateway/{routes.py,router.py,breaker.py,semaphores.py,upstream.py,metering.py,tokenize.py}`
- **Spec:** [spec 04](../03-specs/04-model-gateway.md), [internal-apis §2](../05-contracts/internal-apis.md#2-model-gateway-openai-compatible-base-httpmodel-gateway8001), [ADR-0005](../02-architecture/adr/ADR-0005-thin-model-gateway.md)
- **Do:** Internal JWT auth; `POST /v1/chat/completions` (stream + non-stream), `POST /v1/embeddings`, `POST /v1/rerank`, `GET /v1/models`, `POST /v1/tokenize`; request handling steps of spec 04 §2 (alias resolution cache, param merge/strip, fallbacks ≤ `AR_MG_MAX_FALLBACKS`, per-model concurrency semaphores in Valkey, circuit breaker, health probes), `X-AR-Purpose` validation and span attributes, usage events per response (`mg:{request_id}:in|out|cached`).
- **Done when:** streaming passes through with < 5 ms added per chunk p95 against fake-llm; primary failure falls back to the configured fallback model; open breaker short-circuits.
- **Tests:** unit (param merge, breaker state machine), integration with fake-llm (stream, tools, fallback, 429 semaphore timeout), usage events recorded once per request.

### M2-T04 · `ar_contracts`: definitions, stream events, domain event payloads
- **Depends on:** M0-T09
- **Areas:** `libs/ar_contracts/src/ar_contracts/{definitions/*.py,stream.py,events.py,internal/*.py}`
- **Spec:** [definition-schema](../05-contracts/definition-schema.md), [stream-events](../05-contracts/stream-events.md), [domain-events](../05-contracts/domain-events.md), [internal-apis](../05-contracts/internal-apis.md)
- **Do:** Pydantic models for `AgentDefinition`, `ToolServerDefinition`, `PolicyDefinition`, `SkillDefinition`, `RoutineDefinition`, `KnowledgeSourceDefinition`, `ChannelConfig`, `Bundle`; every stream event type and `ContentPart` union; every domain event payload; internal request/response models. JSON Schema export wired into `make gen`.
- **Done when:** the example documents in definition-schema and stream-events validate; JSON Schemas generated into `packages/api-client`.
- **Tests:** snapshot tests (inline-snapshot) of JSON Schemas; examples from the contract docs parsed as fixtures.

### M2-T05 · Revision 0008 `agents` (minimal registry) and default agent
- **Depends on:** M2-T04, M2-T01
- **Areas:** `ar_domain/agents/{models.py,repository.py,service.py,templates/*.yaml}`, migration 0008, `ar_api/routers/agents.py` (read + create + draft + publish only)
- **Spec:** [spec 05 §2–3, §5](../03-specs/05-agent-registry.md), [schema §4](../04-data/schema.md#4-agents-ar_domainagents)
- **Do:** Agents tables with the published-version immutability trigger; service: create (from template), get, list (visibility rules), `PUT /api/v1/agents/{agent_id}/versions/draft`, `POST /api/v1/agents/{agent_id}:publish` (validation limited to model alias for now), `get_runtime_config(agent_version_id)`; endpoints `GET/POST /api/v1/agents`, `GET /api/v1/agents/{agent_id}`, `GET /api/v1/agents/{agent_id}/versions`, `GET /api/v1/agents/{agent_id}/versions/{version_ref}`. Register `seed_tenant_defaults` step creating agent `assistant` (published v1) and team `everyone`.
- **Done when:** new tenants get `assistant`; published versions cannot be updated (DB trigger).
- **Tests:** integration per endpoint; trigger test; visibility rules unit tests.

### M2-T06 · Revision 0009 `conversations_runs` and conversation API
- **Depends on:** M2-T05, M1-T06
- **Areas:** `ar_domain/{conversations,runs}/**`, migration 0009, `ar_api/routers/{conversations.py,messages.py}`
- **Spec:** [spec 06 §2–3](../03-specs/06-conversations-runs.md#3-message-posting-and-run-start), [schema §5](../04-data/schema.md#5-conversations-messages-runs-ar_domainconversations-ar_domainruns)
- **Do:** Tables of schema §5; `GET/POST /api/v1/conversations`, `GET/PATCH/DELETE /api/v1/conversations/{conversation_id}` (soft delete), `GET/POST /api/v1/conversations/{conversation_id}/messages`; `post_message` transaction (message + run `queued` + outbox `run.start_requested`, `run_in_progress` guard, limits from spec 06 §6) and fast-path workflow start; `start_run` outbox subscriber.
- **Done when:** posting while a run is active returns 409 `run_in_progress`; Temporal unavailable still returns 202 with a queued run (spec 01 §9).
- **Tests:** integration per endpoint; outbox fallback start (Temporal stopped then started); cross-tenant cases.

### M2-T07 · Revision 0010 `files`, files API and `FileProcessWorkflow`
- **Depends on:** M2-T06
- **Areas:** `ar_domain/files/**`, migration 0010, `ar_api/routers/files.py`, `services/ingest/src/ar_ingest/{worker.py,workflows/file_process.py}`
- **Spec:** [spec 13 §2–5](../03-specs/13-files-artifacts.md#2-storage-layout), [schema §11](../04-data/schema.md#11-files-ar_domainfiles)
- **Do:** `files` table; storage keys `t/{tenant_id}/…`; `can_read`; `POST /api/v1/files` (presigned PUT), `POST /api/v1/files/{file_id}:complete`, `POST /api/v1/files:upload` (multipart), `GET /api/v1/files`, `GET /api/v1/files/{file_id}`, `GET /api/v1/files/{file_id}/content`, `GET /api/v1/files/{file_id}/thumbnail`, `DELETE /api/v1/files/{file_id}`; `ingest-worker` process; `FileProcessWorkflow` (magic-byte sniff with filetype, ClamAV scan when `AR_FILES_SCANNER=clamav`, thumbnail with pillow, PDF page count, `file.ready` event, quarantine on detection).
- **Done when:** an uploaded EICAR test file is quarantined; image upload gets a thumbnail; disallowed MIME → 415.
- **Tests:** integration with SeaweedFS and ClamAV containers (ClamAV marked `slow`); access-rule unit tests.

### M2-T08 · Run event streams and SSE
- **Depends on:** M2-T06
- **Areas:** `ar_domain/runs/events.py`, `ar_runtime/events.py`, `ar_api/sse.py`, `ar_api/routers/{run_events.py,conversation_events.py}`
- **Spec:** [stream-events](../05-contracts/stream-events.md), [spec 01 §7](../03-specs/01-api-bff.md#7-sse-plumbing-ar_apisse), [spec 07 §3](../03-specs/07-agent-runtime.md#3-event-emission-ar_runtimeeventsruneventemitter), [ADR-0019](../02-architecture/adr/ADR-0019-sse-streaming.md)
- **Do:** `RunEventEmitter` (XADD to `ar:run:{id}:events` and `ar:conv:{id}:events`, delta coalescing `AR_DELTA_COALESCE_MS`, persist non-delta events to `run_events`, stream TTL `AR_RUN_STREAM_TTL_S`); SSE endpoints `GET /api/v1/runs/{run_id}/events` and `GET /api/v1/conversations/{conversation_id}/events` with `Last-Event-ID` resume (Valkey first, `run_events` fallback), keep-alive pings, per-user connection cap `AR_SSE_MAX_PER_USER`, API-side stripping of `tool_use.arguments`.
- **Done when:** a client reconnecting with `Last-Event-ID` receives every missed non-delta event and the final message exactly once.
- **Tests:** integration: resume after disconnect, resume after Valkey stream expiry (DB fallback), cap enforcement.

### M2-T09 · `AgentRunWorkflow` v1 (no tools)
- **Depends on:** M2-T03, M2-T08
- **Areas:** `services/runtime/src/ar_runtime/{worker.py,workflows/agent_run.py,activities/{start_run.py,model_step.py,set_run_status.py,finalize_run.py},context/assembler.py,prompts/*.md}`
- **Spec:** [spec 07 §2, §4, §9–10](../03-specs/07-agent-runtime.md#2-workflow-agentrunworkflow), [spec 06 §4](../03-specs/06-conversations-runs.md#4-run-status-transitions-owned-by-the-runtime-read-here), [ADR-0003](../02-architecture/adr/ADR-0003-temporal-durable-runs.md), [ADR-0004](../02-architecture/adr/ADR-0004-custom-agent-loop.md)
- **Do:** Workflow id `run-{run_id}` on `ar-runtime`; loop per spec 07 §2.1 restricted to model steps (tool branches raise `NotImplemented` guarded by definition having no tools); activities `start_run`, `model_step` (streams via emitter, heartbeats), `set_run_status`, `finalize_run` (persist assistant message, usage summary, title generation with purpose `title`); `cancel` signal; budgets (steps, tokens, wall time); context assembly v1 (system prompt from agent instructions + platform preamble + conversation history).
- **Done when:** worker kill mid-stream → on restart the run completes (the in-flight model step is retried and the UI receives `message.started` with `reset=true`); cancel stops within 2 s.
- **Tests:** Temporal test env with fake-llm: happy path, cancel, budget exceeded (`run.budget_exceeded`), activity retry with reset event; replay test for determinism (`Replayer` over recorded histories committed under `services/runtime/tests/histories/`).

### M2-T10 · Runs API and run callbacks
- **Depends on:** M2-T09, M1-T14
- **Areas:** `ar_api/routers/runs.py`, `ar_domain/runs/service.py`, `ar_system/subscribers/api_callbacks.py`
- **Spec:** [spec 06 §3](../03-specs/06-conversations-runs.md#3-message-posting-and-run-start), [spec 20 §3.1](../03-specs/20-notifications-events.md#31-run-callback-secret)
- **Do:** `POST /api/v1/runs` (agent by id/slug, input, `wait`, `stream`, `callback_url`, `notify`, `on_behalf_of_user_id` for service accounts with `allow_on_behalf_of`), `GET /api/v1/runs`, `GET /api/v1/runs/{run_id}`, `GET /api/v1/runs/{run_id}/steps`, `POST /api/v1/runs/{run_id}:cancel`; callbacks via `webhook_deliveries` with `target_url`, signed with `__run_callback_secret__`. `GET /api/v1/runs/{run_id}/tool-calls`, `GET /api/v1/runs/{run_id}/children` and `POST /api/v1/runs/{run_id}:input` return empty lists / `invalid_state` until M4-T04, M9-T01 and M5-T05.
- **Done when:** `wait=true` returns the final result within the timeout or 202 with the run; callback received and signature verifies with the documented algorithm.
- **Tests:** integration per endpoint; callback signature; service account on-behalf-of denied without flag.

### M2-T11 · Web chat v1
- **Depends on:** M2-T10, M2-T07
- **Areas:** `apps/web/src/app/(app)/chat/**`, `apps/web/src/components/chat/{ChatView,MessageList,Message,Composer,AgentPicker,StreamingMarkdown,FileChip}/**`, `apps/web/src/lib/stream/**`
- **Spec:** [spec 19 chat sections](../03-specs/19-web-app.md), [stream-events](../05-contracts/stream-events.md)
- **Do:** Conversation sidebar (list, rename, delete, search), new chat with agent picker, message list (virtualised), streaming render (react-markdown + remark-gfm + rehype-sanitize + shiki + katex on demand + mermaid blocks), composer (attachments via files API, Enter/Shift+Enter, stop), run status indicator, reconnect with `Last-Event-ID`, error toasts with retry.
- **Done when:** the M2 exit-criteria Playwright scenario passes; Lighthouse accessibility ≥ 95 on `/chat`.
- **Tests:** Vitest (stream reducer, Markdown sanitisation of `<script>`), Playwright scenario, axe.

### M2-T12 · Message operations: regenerate, edit, branches, feedback, sharing, export
- **Depends on:** M2-T11
- **Areas:** `ar_api/routers/{messages.py,shares.py,feedback.py}`, `ar_domain/conversations/service.py`, `apps/web/src/components/chat/{MessageActions,BranchSwitcher,ShareDialog}/**`
- **Spec:** [spec 06](../03-specs/06-conversations-runs.md)
- **Do:** `POST /api/v1/conversations/{conversation_id}/messages/{message_id}:regenerate`, `:edit`, `:activate`; `PUT/DELETE /api/v1/messages/{message_id}/feedback`; `GET/POST /api/v1/conversations/{conversation_id}/shares`, `DELETE /api/v1/conversations/{conversation_id}/shares/{principal_type}/{principal_id}` (tenant setting `chat.allow_sharing`); `GET /api/v1/conversations/{conversation_id}/export` (Markdown and JSON); UI for all of them.
- **Done when:** branches render correctly after edit+regenerate; shared viewers are read-only.
- **Tests:** integration per endpoint; Playwright edit → branch switch; share read-only test.

### M2-T13 · Web: models admin
- **Depends on:** M2-T01, M1-T15
- **Areas:** `apps/web/src/app/(admin)/admin/models/**`, `apps/web/src/app/(platform)/platform/{models,health}/**`
- **Spec:** [spec 19 `/admin/models`, §3.12](../03-specs/19-web-app.md)
- **Do:** Providers/models/aliases tables and forms (platform rows read-only for tenants), `:test` buttons with latency and sample output, platform models page; `/platform/health` placeholder until M13-T02.
- **Done when:** an admin can register an OpenAI-compatible provider, add a model, point alias `reasoning` at it and test it from the UI.
- **Tests:** Vitest forms; Playwright register-and-test flow against fake-llm.
