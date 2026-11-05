# Agentic Runtime — end-to-end review and remediation plan

Review complete (read-only). Approval starts "Post-approval execution" and Phase 0.

## Context

The owner wants to start testing the platform (visually and functionally) and asked for a fair end-to-end
review on four axes: agentic depth, scalability, metrics/cost/analytics, and genericity. Repo HEAD is
`c94fee9` (M31 certification merged). Working tree has an uncommitted fresh-pass report from today
(`docs/testing/fresh-pass-report.md`) and GRC test fixtures (`docs/testing/grc-flows/`).

## Headline finding (verified by reading code)

The specs describe a repository / unit-of-work / RLS architecture (M1), but the product paths built in
M21–M31 run on a **single process-local in-memory store** with write-behind to Postgres:

- `libs/ar_domain/src/ar_domain/chat/service.py:110` — `ChatService` dataclass, ~80 dict buckets
  (agents, conversations, messages, runs, tool_calls, approvals, policies, secrets, blobs, usage, …), 2,511 lines.
- `libs/ar_domain/src/ar_domain/durable/bind.py:116` hydrates **only** `tenants WHERE slug = 'dev'` at startup.
- `libs/ar_domain/src/ar_domain/durable/flush.py:51` — `schedule_flush` write-behind task; audit rows are flushed
  only for routine/run actions (`flush.py:77-82`); the other 15 `audit_log.append` sites stay in memory.
- `services/api/src/ar_api/main.py:322-350` — sessions, rate limiter, idempotency, audit, platform, notifications
  are all `Memory*` implementations.
- 62 routers; 0 use the `ar_domain` repositories; all go through the store.
- Leftover fixtures in the production state class (`pets: [{"id": 1, "name": "doggie"}]`, `service.py:172`).

Consequences: one API replica only; one tenant only in durable mode; restart loses anything not yet flushed
(M31 §10 confirms running runs become `interrupted`); memory grows without eviction (OQ-68); audit chain and
RLS never-skip rules are not met on the product paths.

## Axis 1 — Agentic depth (spot-checked)

`D/` = `libs/ar_domain/src/ar_domain/`.

**Strong**
- Real tool-calling loop `D/tools/agent_loop.py:82-298`: model → tool calls → results as `role: tool` → repeat; budgets
  (8 steps, 16k tokens, 120 s, 8 tool calls), provider retry, failed tool fed back, one JSON repair, pause/checkpoint
  for approval or human question. M31 proved it live on Qwen3-32B (error → retry → `323`).
- Tools that are real: `general.code/shell` (Linux `unshare` namespaces), `general.read/write/list_files`,
  `general.fetch/http` (SSRF guard, approval for writes), `general.search` (Brave/Tavily once a key exists),
  `data.*` SQL with guard, `documents.*`, charts/analysis.
- MCP client: streamable HTTP, SSE, stdio; OAuth code+PKCE, client credentials, refresh. Policy evaluator + OPA
  optional; approvals, SoD, standing approvals. Agents exposed as MCP server and A2A; REST `/v1` with keys,
  idempotency, rate limit.
- Orchestration: `agents_call / agents_parallel / agents_handoff / agents_ask` as model tools; depth/parallel/
  budget guards; inbox question survives restart.
- Knowledge: heading-aware chunker, real `bge-m3` + reranker via provider, pgvector hybrid (dense + tsvector, RRF),
  Qdrant adapter, ACL filter, citations with anchors.
- 21 declarative HTTP connectors + OpenAPI→MCP and SQL MCP servers; AWS SigV4 / GCP auth implemented.

**Weak**
- Tool calls run **sequentially** and `ToolPipeline.execute` is **synchronous inside async** (`agent_loop.py:229,476`):
  every subprocess/HTTP tool call blocks the whole API event loop (also the fresh-pass note about spaCy download).
- **No token streaming**: one non-streaming POST per step (`D/chat/service.py:1768-1815`); the final answer is emitted
  as one delta.
- "Plan" is cosmetic (`agent_loop.py:395-408`): no plan/reflect/critique step.
- **Cost = output tokens** (`agent_loop.py:194`): `cost += int(tokens_out or 1)`.
- Model text alongside tool calls is dropped (`:228`). No in-loop compaction.
- Skill matching is lexical token overlap (`D/skills/match.py:54-104`), pre-turn, whole body injected (≤50k chars);
  the model does not choose skills.
- Memory: extraction is regex (`D/memory/extract.py`), embeddings always `fake-embed` (`D/memory/book.py:926-929`),
  compaction is a text fold not a summary.
- Model gateway: `openai_compatible / vllm / tei / fake` only; no Anthropic/Bedrock/Azure/Vertex adapters, no
  tool-format conversion, `fallback_model_ids` stored but unused, `breaker.py` has no callers, no prompt caching,
  no provider-side `response_format`. Hardcoded `max_tokens` 1500/800/700 and a Qwen3 `enable_thinking` special
  case (`service.py:1787-1790`, `upstream.py:31-32`). Chat service **bypasses the gateway** when the key is in
  memory (`service.py:1340-1353`) — OQ-53 admits breaker/semaphore/quota are off that path.
- `services/mcp_gateway` is **not on the hot path**: tool calls go through in-process `ToolPipeline`; nothing reads
  `AR_MCP_GATEWAY_URL`. Never-skip rule 4 ("all tool calls through mcp-gateway") is not met.
- MCP client re-initialises per call, no pagination/resources/prompts; stdio servers run with network off and only
  python/node/npx/uv allowed.
- Ingest connectors (S3, SharePoint, Confluence, Drive) are stubs: inline rows or one unauthenticated GET
  (`D/knowledge/fetchers.py:169-236`).

**Fake / scripted in the production path**
- **Builder agent never calls an LLM.** `draft_from_description` → `_complete` → `scripted_definition`
  (`D/agents/assist.py:124-164`); `builder_responder` is set only in tests. Principle 2 ("primary create-agent path
  is a natural-language instruction handled by the builder agent") is not implemented.
- `maybe_compose` and `maybe_tools` run **before / after the real loop** (`service.py:1628-1641`): slug
  `research-lead` + "research" → scripted subagent results; regexes "file a ticket", "how many orders", "create pet",
  "chart", "ask me" → hardcoded tool calls (`D/tools/chat_loop.py:121-156, 272-279`).
- `sandbox.exec` runs `/bin/bash -lc` on the host via `Popen` with no namespace (`D/sandboxes/runtime.py:358-417`);
  egress control is a regex over `curl` args. The k8s driver only builds a pod spec nobody submits; docker driver only
  checks the socket exists. `general.*` falls back to an unisolated subprocess with **no prod guard** (OQ-57).
- `browser.*` is httpx + HTML parse; `screenshot` returns `png_chart([1,2,3])` (`runtime.py:420-545`).
  `web.fetch` (`builtin://web`) returns canned text for example.com (`D/tools/handlers.py:247-262`).
- Tool search `hash_embedding` is a SHA-seeded random vector (`D/tools/logic.py:148-154`); gateway `/v1/embeddings`
  always hash vectors, `/v1/rerank` lexical.
- Temporal: `TurnWorkflow` is one activity wrapping the whole in-process `generate()` (5 min, 3 retries); `model_step`
  activity is a placeholder; `ToolTurnWorkflow` is a simulator with `fail_code`; `ChildRunWorkflow` echoes
  `final_text`. M31 ran with `AR_TEMPORAL_ADDRESS=127.0.0.1:1` (unreachable). Crash → run `interrupted`, not resumed.
- Evals: runner echoes input (`D/evals/runner.py:30-41`), latency hardcoded 12 ms, cost 0, `llm_judge` is token
  cosine (`D/evals/scoring.py:186-193`). Eval-gated publish is therefore meaningless.
- Demo fixtures in seed: tickets, petstore, warehouse, echo, `control.checkpoint` (fails first call on purpose).
- Model gateway echoes `fake: {text}` when fake-llm is down (`main.py:100-108`); fresh pass saw `fake:` replies
  with zero tool calls on a real alias.

**Live-tested connectors**: GitHub, Email (local SMTP). Other 18 labelled Not live-tested.

## Axis 4 — Genericity and hard-coding (spot-checked)

**Strong**
- No customer names in code (NGX, Cura, Talentfino, Wisestep, ledgerline: zero hits). M30 pack removal is real
  (`/grc/*` pages, `components/grc/*`, ~125 i18n keys deleted; revision 0031 drops schema `grc`; import-linter
  contract `packs-not-in-core`).
- Pack hooks exist: entry-point loader (`services/api/src/ar_api/plugins.py:24-28`), pack permissions/audit actions
  registry, alembic env, install/upgrade/uninstall routes, shell nav built from `/api/v1/tenant/packs`.
- Tenants can add tools without forking: remote MCP servers, OpenAPI imports, connections; connector SDK exists.
- Typed `TenantSettings` with defaults (`libs/ar_contracts/src/ar_contracts/tenants.py:104-119`), plan-limit merge,
  `GET/PATCH /api/v1/tenant`. Most runtime prompts live in `.md` files.

**Weak — GRC concepts still in core with no off switch**
- Assurance API (`routers/assurance.py`, 533 lines): evidence, legal holds, retention schedules, guests, binders,
  agent-cards ("AI register"), run-records. Tables from revisions 0021–0023; permissions `evidence:*`, `holds:manage`,
  `ai_governance:*`, `binders:export`; built-in `auditor` role (`identity/permissions.py:113-124,169-181`).
- `/admin/assurance` nav gated only by `evidence:read` which every tenant_admin has; strings "AI register", "Binders",
  "Seal evidence", "Open a hold", "Matter" in `en.json:959-993`.
- Seed adds a "Compliance officer" user and seals a "Quarterly controls note" for every dev/CI tenant
  (`D/chat/service.py:432-465`). Builder starter prompt "reviews vendor SOC 2 reports" (`agents/templates.py:67`).
- Helm default `AR_EVIDENCE_LOCK_MODE: compliance`; `/grc` tombstone route and 4 e2e specs that only prove absence.
- These are defensible as "generic assurance" (spec 21) but they should be an installable pack or at least a
  tenant feature flag, per principle 3.

**Weak — hard-coded values**
- Qwen3 `enable_thinking` substring special case in 5 places (`chat/service.py:840,1749,1789`, `documents/model.py:39`,
  `model_gateway/upstream.py:31`).
- Default models `BAAI/bge-m3` (1024 dims) and `bge-reranker-v2-m3` in code (`knowledge/live_embed.py:27-29`); UI preset
  auto-fills DeepInfra URL and `Qwen/Qwen3-32B` (`models-admin.tsx:67-77`).
- ~60 `max_tokens` / `timeout=` literals; India defaults (`Asia/Kolkata`, `en-IN`, `INR`) in contracts, migration 0002,
  usage service, quotas, and a special case returning "IST" (`routines/schedule.py:74`); single locale file.
- Inline prompts in Python duplicating `.md` files (`runs/logic.py:8-11`, `documents/model.py:12-18`,
  `tools/searching.py:13`, `agents/templates.py:19-71`).
- `admin@dev.local` and `dev.local` in bootstrap/seed/fetchers; login page hard-codes the four dev users and shows
  dev-login buttons unless `AR_ENV=prod` (staging gets one-click admin).
- Demo fixtures constructed on every `ChatService` (`seed_demo`, `pets`, `tickets`, `memory://echo`).

**Bugs found (real, verified)**
- `D/security/guardrails.py:67-72`: PII redaction toggle iterates **all tenants'** settings and reads a key
  (`pii_redaction`) that the schema places under `features`, so (a) one tenant can disable redaction for all and
  (b) there is no working off switch. Your GRC flow report shows the damage: "90 days" → `[DATE_TIME]`, `P6.3` →
  `[US_DRIVER_LICENSE].3`, countries → `[LOCATION]`, and the model then judged controls on corrupted text.
- `D/tools/handlers.py:471-476` `_settings()` and `records/vault.py:296-300` return the **first tenant's** settings for
  everyone.
- From your GRC report: `:check` is a lexical gate (`_MIN_SCORE 0.34`) that drops 11/12 paraphrased controls before
  the model sees them; rewrite cannot redline to a template; `documents.read` with a bad anchor returns empty silently.

**Missing**
- Packs cannot ship UI (`/ext/*` has no route or loader); no pack settings screen; no tenant settings screen
  (Simple/Advanced is a `localStorage` flag copied into ~10 components); connector catalogue is code-only
  (1,957 lines of Python dataclasses); many backend routers have no UI (roles, groups, teams, secrets, webhooks,
  api keys, SCIM, IdPs, audit, SoD, domains).

## Quality gates and test state

**Strong**: `make check/test/gen`; CI jobs pr-title, python-lint, python-unit (cov ≥ 85 % branch), python-integration,
web (biome/typecheck/test/knip/build), web-e2e, codegen-drift, opa-test, migrations up/down, compose-smoke, docs.
Hosted CI green on `c94fee9`. 602 Python tests, 46 web unit tests, 54 Playwright tests, no xfail.

**Weak**
- Nightly "supply-chain scanners" and "24 h soak" steps are `echo` only (`.github/workflows/nightly.yml:13-24,36-38`).
- Unit tests of the loop replace `complete_turn` with scripts; no CI test runs a real model; real-model proofs are
  manual scripts (`scripts/m21b_proof.py` … `m31_proof.py`) with DeepInfra/Qwen hard-coded.
- Playwright runs single-worker against the in-memory API ("Parallel files race on that store").
- 93k lines Python vs 602 tests; 18k lines web vs 46 unit tests; 916 `# noqa`, 169 `type: ignore`.
- Modules named after milestones (`routers/m2.py` 906 lines, `durable/m23.py … m29.py`); files > 1,000 lines ×8.
- `progress.md`: M2.5-T01a/b still `in_progress` (stale); M16–M19 rows still `done` though M30 removed them.

**Uncommitted working tree**: keep `.gitignore` (+`.secrets/`); **revert** `apps/web/next-env.d.ts` (points at
`.next-fresh`); add `apps/web/.next-fresh/` (311 MB) to `.gitignore`; decide whether `docs/testing/fresh-pass*`,
`grc-flows/` and `scripts/fresh_pass_*.py` are committed (they contain no secrets per their own scan). Rotate the
DeepInfra key the fresh-pass report says was pasted in chat.

## Visual test readiness

- Start: `make bootstrap` → `make dev` (or `make dev AUTO_PORTS=1`; `make dev-min` for the light stack) → http://localhost:3000.
  Users `admin@ | builder@ | member@ | approver@dev.local`, password `dev-password`. Real model: Admin → Models →
  Advanced → OpenAI-compatible, then point `reasoning` alias at it (or `AR_DEV_MODEL_BASE_URL/_API_KEY` before seed).
- Gotchas (all documented): `AR_WEB_HOST_PORT` must match browser origin (CSRF); OPA bundle must target current
  `AR_PORT`; first tool call may stall on spaCy download; fresh seed's W2 approvals deadlock (`approvers.mode=requester`
  + SoD) until a users-mode policy is activated with step-up; host 5432/8000 may be taken (fresh pass used 5433/18131/18132).
- ~45 routes; two reachable screens are not in nav (`/reviews`, `/admin/policies`); `/guest*` has no loading/empty state;
  no route-level `loading.tsx`. Reusable: `scripts/m31_ui.cjs`, `docs/testing/m31/*`, `fresh-pass/*`, e2e specs
  `screen-layouts / detail-screens / auxiliary-screens / workspace-polish`.

## Axis 2 — Scalability (spot-checked)

**Strong**
- Schema and indexes are well designed: runs (by conversation, partial active, by routine), messages (conversation +
  GIN), `run_events (run_id, seq)`, `usage_events (tenant_id, occurred_at)` + dedupe key, pgvector halfvec HNSW.
- RLS session helper is PgBouncer-safe (transaction-local settings, `statement_cache_size=0`).
- Helm: rolling updates, topology spread, PDB, CPU HPA, KEDA on Temporal backlog; 7 value presets lint clean.
- Temporal turn workflow has heartbeats, retries, cancel signal and a terminal-state compensation step.
- M31 soak: 20 min, 341 req/min, p95 0.95 s, p99 1.9 s, 8 Postgres connections, no pool exhaustion (single replica).

**Weak / broken**
- **All API state is per-process memory** (see headline): sessions (`MemorySessionStore`), login states, idempotency,
  rate buckets, SSE caps, and the whole `ChatService`. The chart runs 2–30 API replicas with no session affinity.
  Login on pod A is unknown on pod B. `docs/07-ops/scaling.md §1` ("all deployables are stateless") is false.
- **Only one tenant is hydrated** (`bind.py:116`, `slug = 'dev'`). The product is single-tenant in durable mode.
- **Cross-process SSE is Postgres polling**: each open stream runs `_watch` → `reload_run` every 250 ms
  (`service.py:1482-1500`), and `reload_run` reloads the tenant's conversations/agents/versions/skills/facts/tools
  (`hydrate.py:152-189`). Gives up after 240 polls (~60 s); stream ends after 15 s silence with no keep-alive;
  `seq` is `len(events)+1` per process so API and worker emissions collide and `ON CONFLICT DO NOTHING` drops them;
  every delta calls `flush_soon()` and each flush re-inserts the whole event list (O(n²)). Spec says Valkey Streams.
- **Durability is one 5-minute activity** wrapping the whole turn (`turn.py:32`, `execute_chat_turn.py:64-66`). Runs
  over 5 min fail. Falls back to in-process silently if `start_workflow` throws or Temporal was down at first bind
  (never re-attached). `ChildRunWorkflow` echoes. Worker concurrency env vars (`AR_RUNTIME_MAX_CONCURRENT_*`) are
  set in values.yaml but read nowhere. KEDA max for runtime-worker is 4.
- **Valkey deployed, unused**: `ValkeyTokenBucket` never instantiated; if enabled it fails open permanently and
  `INCR`/`EXPIRE` is non-atomic. `store.valkey_client` is read in 4 places and assigned nowhere.
- **Rate limit is N × 600 rpm across N replicas**, per-user key only, no tenant aggregate.
- **Sandboxes are `subprocess.Popen` in the API/worker process** under a `threading.Lock`, blocking the event loop up
  to 120 s. k8s/gVisor driver and warm pool are unwired. sandbox-manager holds an unbound `ChatService` copy.
- **Blocking sync HTTP on the event loop** everywhere: OPA per tool decision, embeddings, HTTP tools, remote MCP,
  connectors, compaction. No `to_thread` except Vault. Model calls are non-streaming so TTFT = full completion.
- **Per-process global locks**: flush lock serialises every request's write-back; quota counters use `threading.Lock`.
- **Outbox has no relay process**; usage rollup is unregistered (OQ-43). No partitioning (OQ-07).
- **Hot-path DB engine** is the cache engine (`bind.py:95-101`) with default pool 5+10, connecting as `ar_platform`
  which **bypasses RLS**. The documented 20/10 RLS pool serves only the little-used `tenant_session` path.
- **Load test is a stub**: `tests/load/harness.py` serves canned JSON; the "1.6 ms p95" report measures that stub.
  Locust scenarios send no auth and hit routes that may not exist. 24 h soak never run (OQ-48); nightly soak is `echo`.
- **Deployment blocker (verified)**: image entrypoint is `python -m ar_common.serve`, which does
  `os.environ["AR_APP_MODULE"]`; Helm sets no `AR_APP_MODULE`, no `command`, no `args`. Only the ingest image sets it.
  Runtime/system `create_application()` are health-only; the Temporal poller starts only from `main()`
  (`uv run ar-runtime` in Procfile). So the chart as shipped either crashes on start or runs workers that never poll.
  M15 proof was "chart render + kubeconform + kind install" (OQ-48), never a working pod.

## Axis 3 — Metrics, cost, analytics (spot-checked)

**Strong**
- Schema: `usage_events` (tenant, user, team, agent, routine, run, model_id, alias, tool_id, source, dedupe,
  cost_micros), `usage_daily`, `quotas` (scopes × periods × block/warn), `run_steps` (tokens in/out, cached, latency),
  `models.price_*_micros_per_mtok`. Quota logic (tz windows, warn-once, block vs warn) is real code.
- Provider `prompt_tokens/completion_tokens` parsed per call; tool calls record `latency_ms` and a usage event.
- Telemetry hygiene good: no content in spans, tool args redacted, Langfuse content capture tenant-gated.
- ~50 real domain counters/histograms (knowledge, policy, sandbox, routines, channels, evals, memory, quota).
- One usage screen (`/admin/usage`): group by day/agent/user/metric, CSV export, overview tiles.

**Weak / broken**
- **Usage events are never written to Postgres**: `usage`/`usage_daily`/`quotas` absent from the flush buckets; no
  `INSERT INTO usage_events` exists outside migrations. Usage is a per-process dict lost on restart; worker-run usage
  never reaches the API's `/usage/summary`.
- **Cost is invented**: `cost += tokens_out` (`agent_loop.py:194`); `_remember_usage` swaps tokens_in/out
  (`:317-323`); fallback path counts **words** with `cost_micros=0`; `model_alias` hard-coded `"reasoning"`; prices
  (`price_*_micros_per_mtok`, `PlanLimits.unit_prices`) read nowhere. The agent loop writes **no model-token usage
  events** at all; only `runs` is metered at completion. Sandbox CPU cost 0, `duration_ms` hard-coded 0.
- **No per-stage capture**: nothing writes `run_steps`; no per-model-call latency; no TTFT; no queue wait; retrieval
  only a histogram; child-agent usage folded into parent.
- **Placeholder metrics**: `metric_catalogue.py` regex-scans the spec docs and registers a zero-valued instrument for
  every `ar_*` name not implemented. Grafana dashboards (`ar-models`, `ar-runs`, `ar-tenants`, `ar-tools`) and alerts
  (`ar_runs_queued_over_60s`, `ar_model_alias_all_open`, `ar_outbox_lag_seconds`) sit on those → flat and never fire.
- **Model gateway emits no metrics and no usage**; its quota guard reads `app.state.chat` which the gateway never sets,
  so it enforces nothing. HTTP metric has no route label and no latency histogram. OTel is auto-instrumentation only
  at 10 % sampling; no spans for loop steps; no Temporal interceptor.
- **Overview numbers are wrong**: `run_p50/p95` read a field only evals write (always 0); `ttft_p95` copies run p95;
  tool "p95" is the mean; `median_decision_s` hard-coded 0; `_cost` ignores the date window and returns 0 because it
  sums dicts/ints but `usage_daily` holds dataclasses (`runs/service.py:96-192`). `/usage/summary` rebuilds
  `usage_daily` from all in-memory events on every request.
- **Langfuse is a placeholder**: builds a dict nothing sends; trace link is `http://localhost:{port}/trace/{id}`.
- Owner questions unanswerable today: where is cost going (no), which model spends (no), what is slow (no), cache
  effectiveness (no), most-used flows over time (partial, in-memory only), per-tenant usage in Grafana (no).

## Scorecard

| Axis | Spec | Code | Verdict |
|---|---|---|---|
| 1 Agentic | Rich | Real loop + real general tools + MCP/A2A/REST exposure; builder, evals, memory, browser, Temporal steps, tool search fake or scripted | **Partially agentic; demo scaffolding must come out** |
| 2 Scalable | Stateless, Valkey, Temporal per step | Single-process in-memory store, single tenant hydrated, Postgres polling SSE, blocking sync I/O, Helm cannot start pods | **Not horizontally scalable; single-node only** |
| 3 Metrics/cost | Full catalogue | Schema good; usage never persisted; cost = tokens_out; dashboards on zero metrics | **Not usable for cost or performance questions** |
| 4 Generic | No industry in core | No customer names; GRC pack removed; assurance features (evidence/holds/binders/AI register/auditor) remain in core with no flag; Qwen/DeepInfra/India/dev.local defaults in code; 2 cross-tenant settings bugs | **Mostly generic; residue to flag or pack** |
| Quality | CI green, 85 % cov | Loop tests scripted; nightly scanners/soak are `echo`; load test measures a stub | **Green but not load-bearing** |

What M31 and the fresh pass genuinely prove: on one laptop, one tenant, one process, with Qwen3-32B, the product does
chat → tool calls → repair → approval (SoD) → GitHub write → RAG with citations → documents → child agents → REST/MCP/A2A.
That is a real, demo-able vertical slice. It is not yet a multi-tenant, multi-replica, metered platform.

## Remediation plan

Each phase is one or more PRs following AGENTS.md (task ids added to a new milestone file `M32-hardening.md`,
progress.md rows, docs moved with code, open-questions entries). Effort is engineering-days, rough.

### Phase 0 — Honest baseline and test readiness (1–2 days) ← do first, after approval
0.1 Run `make check` and `make test` locally; record results. Revert `apps/web/next-env.d.ts`; gitignore `.next-fresh/`;
    commit `.gitignore` (+`.secrets/`); commit or discard `fresh-pass*`, `grc-flows/`, `scripts/fresh_pass_*.py`.
0.2 Fix the two cross-tenant settings bugs (`guardrails.py:67-72`, `handlers.py:471-476`, `vault.py:296-300`): read
    the **current tenant's** settings; add `security.piiRedaction` (or `features.piiRedaction` honoured) to
    `TenantSettings`; exempt the tenant's own library documents from redaction; allow-list entity types.
    Cross-tenant test expecting isolation.
0.3 Fix the fresh-seed approval deadlock: seed default W2 policy as `approvers.mode=users` (approver role) or make
    `requester` mode fall back to the approver role when SoD excludes the requester. Test on a fresh seed.
0.4 Remove the `fake:` echo fallback from the gateway for non-fake models (return 502 `no_healthy_upstream`), and
    log/alert when an alias resolves to a fake provider outside dev/ci.
0.5 progress.md: close M2.5-T01a/b, mark M16–M19 rows `retired (M30)`.
0.6 Visual test pass (see "Post-approval execution" below) and publish the report.

### Phase 1 — Make it genuinely agentic (3–4 weeks)
1.1 Delete scripted paths from the production turn: `maybe_compose`, `maybe_tools`, `_scripted_result`, keyword
    triggers, `control.checkpoint` demo, petstore/tickets/warehouse/echo fixtures, `pets`/`tickets` fields.
    Keep fixtures only under `ar_testing` / `AR_ENV=ci`.
1.2 LLM-backed builder: wire `builder_responder` to the tenant `reasoning` alias with a JSON-schema prompt
    (`agents/templates.py` Builder instructions already exist), keep `scripted_definition` only as the final repair.
    Preview + diff UI already exists.
1.3 Async, parallel tool execution: make `ToolPipeline.execute` async (httpx.AsyncClient, `asyncio.to_thread` for
    subprocess), run a step's tool calls with `asyncio.gather` bounded by `max_parallel_tool_calls`. Move OPA,
    embeddings, connectors, remote MCP off sync httpx.
1.4 Token streaming end to end: `stream=true` to the provider, incremental `message.delta`, 50 ms coalescing, keep
    text that arrives alongside tool calls. Keep-alive pings on SSE.
1.5 Real embeddings for memory and tool search (through the tenant embedding alias); LLM memory extraction and
    compaction using the existing `prompts/*.md`; in-loop compaction when context nears the budget.
1.6 Model gateway: put every call through the gateway (remove `_completion_url_for` bypass), implement fallback
    routing from `fallback_model_ids`, wire `breaker.py` and `max_concurrency`, provider-side `response_format`,
    per-model config for `enable_thinking`/`max_tokens` (remove the Qwen3 substring hack), prompt caching passthrough.
    Add a native Anthropic adapter (tool-format conversion) as the second provider; Bedrock/Azure after.
1.7 Evals: runner executes the real agent through the gateway; `llm_judge` calls a judge alias; record real latency and
    cost. Only then re-enable eval-gated publish.
1.8 Skills: expose `skills.load` as the model's choice (progressive disclosure), keep lexical match only as a hint
    in the capabilities block.
1.9 Sandbox and browser: refuse the process fallback when `AR_ENV=prod`; implement the docker/gVisor driver for real
    (`sandbox-manager` submits containers; `sandbox.exec` goes through it); replace `browser.*` with Playwright in the
    sandbox image. `web.fetch` → delegate to `general.fetch`.
1.10 MCP client: session reuse, `nextCursor`, resources/prompts, stdio with egress policy; `.well-known` OAuth
    discovery. Route tool calls through `mcp-gateway` or formally retire that service and update never-skip rule 4.

### Phase 2 — Scalability: retire the in-memory store (6–8 weeks, the big one)
2.1 Decision: replace write-behind `ChatService` with the repository/unit-of-work layer the specs and M1 already built
    (`ar_domain/*/tables.py`, `db/session.py` RLS path). Do it bucket by bucket behind the existing service methods:
    conversations/messages/runs/events first (hot path), then agents/versions, tools, approvals/policies, connectors,
    knowledge/memory/skills. Each bucket: repository + RLS test + removal from `BUCKETS` + hydrate/flush deletion.
2.2 Multi-tenant hydration goes away with 2.1; until then, bind per request tenant (not `slug='dev'`).
2.3 Shared state to Valkey: sessions, login states, idempotency, rate buckets (fix fail-open and use `INCR`+`EXPIRE`
    in a Lua script or `SET NX EX`), SSE per-user caps, quota counters, token cache. Set `store.valkey_client`.
2.4 SSE fan-out via Valkey Streams per spec (`XADD ar:run:{id}:events`, `XREAD BLOCK`), server-assigned `seq`,
    no delta persistence, keep-alive pings, no 60 s cutoff.
2.5 Temporal per step: one activity per model call and per tool call, `continue_as_new` on long runs, resume after
    crash from `run_events`; `ChildRunWorkflow` runs the child; register outbox relay and usage rollup; read the
    `AR_RUNTIME_MAX_CONCURRENT_*` settings; per-tenant fairness semaphore; never silently fall back in prod.
2.6 Deploy: set `AR_APP_MODULE` and worker `command` per deployable in the chart; worker containers must run `main()`;
    uvicorn/granian workers from a setting; RPS-based HPA; raise KEDA max; `kind` smoke that actually serves a chat
    turn. Fix `scaling.md §1`.
2.7 Real load test: Locust scenarios with auth against the compose stack (chat, SSE, tools, retrieval, approvals);
    publish p50/p95/p99 and connection counts; nightly soak that runs; wire the supply-chain scanners.

### Phase 3 — Metrics, cost, analytics (2–3 weeks; can start in parallel with Phase 2 once 2.1 covers usage)
3.1 Persist `usage_events` on every model call, tool call, sandbox exec, embedding, rerank and child run, with
    run_id/conversation_id/model_id/tool_id/latency; `usage_daily` rollup as a registered Temporal schedule.
3.2 Real cost: `tokens × price_*_micros_per_mtok` from the `models` row (plus `cached_tokens` at the cached price);
    plan `unit_prices` for tools/sandbox seconds; fix the tokens_in/out swap; stop word-count metering.
3.3 Per-step capture: write `run_steps` (tokens in/out/cached, latency, TTFT, queue wait); spans per loop step and tool
    call; Temporal interceptor; gateway metrics `ar_mg_*` (requests, tokens, latency by model/alias/tenant).
3.4 Delete `metric_catalogue` spec-scraping; every dashboard panel and alert must point at an instrument that is
    written; add route-labelled HTTP latency histogram.
3.5 Fix overview maths (`runs/service.py`): p50/p95 from `run_steps`, real TTFT, real tool p95, cost by window from
    SQL (`OVERVIEW_SQL`), decision latency. Analytics screens: cost by model/agent/user over time, latency percentiles
    by agent/model, most-used tools/skills/agents over time, per-conversation cost, cache hit rate, budget burn-down.
3.6 Langfuse: send traces (or drop the dependency and the link); per-tenant switch already exists.

### Phase 4 — Genericity residue (1–2 weeks)
4.1 Assurance (evidence, holds, retention schedules, binders, AI register, run records, `auditor` role): add a tenant
    feature flag `features.assurance` default **off** (or move to an installable pack using the hooks that exist).
    Hide nav, routes and permissions when off. Remove "Compliance officer" seed and the SOC 2 starter prompt from core.
4.2 Config over code: per-model capability flags (thinking, max_tokens, timeouts) in the `models` row; default
    embedding/rerank model from tenant settings; UI provider presets as a data file; locale/timezone/currency defaults
    from tenant settings with neutral platform defaults (UTC, en, USD) and the India values in the dev seed only.
4.3 Remove dev identities from code paths outside seed; login page renders dev-login only when the API advertises it.
4.4 Packs: `/ext/[...slug]` route with a registry of pack-provided screens; pack settings screen; connector catalogue
    as YAML definitions loadable at runtime.
4.5 Tenant settings screen (Simple/Advanced) backed by `GET/PATCH /api/v1/tenant`; replace the 10 `localStorage` copies
    with `components/common/settings-mode.tsx`. Admin UI for roles/groups/teams/API keys/webhooks/audit.

### Decisions needed from the owner (defaults applied if silent)
- D1 Assurance features: feature-flag off by default (recommended) vs installable pack vs keep in core.
- D2 Phase 2 approach: incremental repository migration behind existing service methods (recommended) vs rewrite.
- D3 Second provider: native Anthropic adapter first (recommended), then Bedrock/Azure.
- D4 Whether to keep `mcp-gateway` as a service (route calls through it) or retire it and amend never-skip rule 4.

## Post-approval execution (this session, read-write)

1. `make check` and `make test` → record pass/fail counts and coverage.
2. Start the stack on free ports (`make dev AUTO_PORTS=1`, or reuse the fresh-pass layout 5433/18131/18132) with
   the DeepInfra key from `.secrets/deepinfra_api_key` (never echoed). Register Qwen3-32B + bge-m3 via the Models UI.
3. Visual click-through in the built-in browser, desktop 1440×900 and mobile 390×844, light and dark, screenshots to
   `docs/testing/review-2026-11-05/`:
   Chat (empty → first turn → tool progress → trace) · Builder (NL → preview → publish) · Agents list/editor/evals ·
   Tools · Connections · Connectors · Documents (upload PDF → outline → summary → check → compare → rewrite accept) ·
   Knowledge (collection → source → cited answer) · Memory edit · Skills · Routines/Schedules · Inbox question ·
   Runs tree · Approvals (W2 POST → SoD 422 → approver 200) · Reviews (not in nav) · Admin: Models, Channels, Evals,
   Usage, Quotas, Sandboxes, Assurance, Users, Policies (not in nav) · Platform health · Expose tab (REST/MCP/A2A) ·
   Guest portal · Widget. Record loading/empty/error states, dark-mode defects, axe violations.
4. Run the GRC fixture flows from `docs/testing/grc-flows/` as generic document/knowledge/approval scenarios and
   confirm defect 1 (redaction) reproduces before Phase 0.2.
5. Publish the review as an artifact page (scorecard, findings with file refs, remediation Gantt, screenshots) and
   send the screenshots folder.

## Verification for Phase 0 PRs
- `make check`, `make test`, Playwright axe specs pass.
- New tests: cross-tenant PII setting isolation; fresh-seed W2 approval resolves with `approver@dev.local`; gateway
  returns 502 (not `fake:`) for a dead registered model.
- Fresh `make reset-db && make seed` → approval flow and `documents.read` on `acme-information-security-policy-v2.md`
  shows unredacted "90 days" / "P6.3".
