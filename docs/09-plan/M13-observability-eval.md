# M13 — Observability & evaluation

Goal: operate and improve with evidence. Every request and run is traced without content; dashboards and alerts with runbooks ship with the chart; builders inspect runs step by step; evaluation suites (functional, retrieval, safety, red-team) gate publishing and catch regressions when models, prompts or tools change.

Exit criteria: Grafana dashboards show live data in the compose `obs` profile; each alert rule fires in a synthetic test and links to its runbook; a publish with a failing gated suite is blocked and the builder sees which cases regressed; the platform red-team suite passes on the default agent.

M13-T07 depends on M14-T08, so it is not part of this exit. It is part of 1.0 (see M15-T07).

---

### M13-T01 · Telemetry completeness, dashboards, alerts
- **Depends on:** M11-T07
- **Areas:** all deployables (span attributes), `deploy/helm/agentic-runtime/dashboards/*.json`, `deploy/helm/agentic-runtime/templates/prometheusrules.yaml`, `deploy/compose/otel/collector.yaml`, `ar_runtime/langfuse.py`
- **Spec:** [spec 18 §1–2](../03-specs/18-observability-eval.md#1-telemetry-architecture), [runbooks](../07-ops/runbooks.md), [performance-budgets](../08-quality/performance-budgets.md)
- **Do:** GenAI semantic-convention spans for model and tool calls; metrics listed in each spec's Metrics section implemented and named exactly; tail sampling config; Langfuse run traces (content only when `observability.capture_content`); dashboards `ar-overview`, `ar-runs`, `ar-models`, `ar-tools`, `ar-ingest`, `ar-sandboxes`, `ar-temporal`, `ar-tenants`; PrometheusRule alerts of spec 18 §2 with `runbook_url` annotations pointing to `docs/07-ops/runbooks.md#rb-…`.
- **Done when:** a lint test checks every metric name referenced in specs exists in code (registry dump) and every alert has a runbook anchor that resolves.
- **Tests:** metric-name lint test; `promtool test rules` unit tests for each alert; no-content test (spans/logs from an e2e run contain no message text — grep for a canary string).

### M13-T02 · Observability overview API, platform health, run inspector data
- **Depends on:** M13-T01
- **Areas:** `ar_api/routers/{observability.py,platform_health.py}`, `ar_domain/runs/service.py`
- **Spec:** [spec 18 §3](../03-specs/18-observability-eval.md#3-in-product-observability-api)
- **Do:** `GET /api/v1/observability/overview` (aggregations over runs, tool_calls, approvals, message_feedback, usage_daily with indexes verified by EXPLAIN), `GET /api/v1/platform/health` (parallel readiness probes with 2 s timeout), `trace_url`/`langfuse_url` on run detail (`AR_TRACE_UI_URL`).
- **Done when:** overview for 30 days over 1 M runs returns in < 1 s (perf test dataset).
- **Tests:** integration; perf test (marked `slow`).

### M13-T03 · Revision 0019 `evals` and eval suites API
- **Depends on:** M13-T01
- **Areas:** `ar_domain/evals/**`, migration 0019, `ar_api/routers/{eval_suites.py,eval_runs.py,feedback.py}`
- **Spec:** [spec 18 §4.1, §4.3](../03-specs/18-observability-eval.md#43-api), [schema §16](../04-data/schema.md#16-evaluation-ar_domainevals)
- **Do:** Tables of schema §16; `GET/POST /api/v1/eval-suites`, `GET/PATCH/DELETE /api/v1/eval-suites/{suite_id}`, cases `GET/POST /api/v1/eval-suites/{suite_id}/cases`, `PATCH/DELETE /api/v1/eval-suites/{suite_id}/cases/{case_id}`, `POST /api/v1/eval-suites/{suite_id}/cases:import`, `POST /api/v1/eval-suites/{suite_id}/cases:from-conversation`, `GET /api/v1/eval-runs`, `GET /api/v1/eval-runs/{eval_run_id}`, `GET /api/v1/eval-runs/{eval_run_id}/results`, `GET /api/v1/feedback`; assertion and ToolMock models in `ar_contracts.evals`.
- **Done when:** JSONL/YAML import reports per-line errors.
- **Tests:** integration per endpoint; assertion model validation tests.

### M13-T04 · `EvalRunWorkflow`, graders and publish gates
- **Depends on:** M13-T03, M9-T01
- **Areas:** `ar_system/workflows/eval_run.py`, `ar_system/evals/{graders.py,judge.py}`, `ar_system/prompts/judge.md`, `ar_mcp_gateway/evals.py`, `ar_domain/agents/service.py`, `ar_api/routers/eval_runs.py`
- **Spec:** [spec 18 §4.2, §4.4–4.5](../03-specs/18-observability-eval.md#42-evalrunworkfloweval_run_id-queue-ar-eval-id-eval-eval_run_id), [eval-strategy](../08-quality/eval-strategy.md)
- **Do:** `POST /api/v1/eval-suites/{suite_id}:run`, `POST /api/v1/eval-runs/{eval_run_id}:cancel`; workflow per spec 18 §4.2 (`AR_EVAL_CONCURRENCY`, `channel='eval'` conversations, `runs.eval_context` with mocks and simulated principal, W2/W3 never executed, judge purpose `judge`); every assertion type; baseline comparison and regressions; publish gate (`agents:publish` with gated suites → version state stays draft until `complete_gated_publish`); platform suites from `evals/redteam/` and `evals/golden/` loaded at seed.
- **Done when:** the M13 exit gate scenario passes; eval runs never call real W2/W3 tools (asserted by gateway counters).
- **Tests:** Temporal tests with fake-llm; grader unit tests per type; gate integration test.

### M13-T05 · Web: observability, run inspector, evals
- **Depends on:** M13-T02, M13-T04
- **Areas:** `apps/web/src/app/(app)/runs/[runId]/**`, `apps/web/src/app/(app)/agents/[agentId]/evals/**`, `apps/web/src/app/(admin)/admin/evals/**`, `apps/web/src/app/(platform)/platform/health/**`, observability overview cards on `/admin/usage`
- **Spec:** [spec 19](../03-specs/19-web-app.md)
- **Do:** RunInspector (header, budget bars, step timeline, tool calls with arguments for authorised viewers, events, trace links, trace graph from M9-T04), agent evals tab (suites, cases editor, run, results with diffs vs baseline), admin evals (reusable suites, feedback inbox with "add to suite"), platform health page.
- **Done when:** a builder can go from a thumbs-down to a new eval case and a passing re-run in the UI.
- **Tests:** Vitest; Playwright feedback → case → run; axe.

### M13-T06 · Feedback loop and quality reports
- **Depends on:** M13-T04
- **Areas:** `ar_system/subscribers/notifications.py`, `ar_domain/evals/reports.py`
- **Spec:** [spec 18 §4](../03-specs/18-observability-eval.md#4-evaluation), [spec 20 §2.3](../03-specs/20-notifications-events.md#23-kind-mapping)
- **Do:** `feedback.created` → notify agent owners (digest daily, not per event); scheduled nightly re-run of gated suites for each published agent when its model alias target changed (`model_alias.updated`), with `eval_completed` notifications on regression.
- **Done when:** changing an alias target triggers re-runs for affected agents only.
- **Tests:** Temporal test for alias-change re-run; digest batching test.

### M13-T07 · Run records, replay and the groundedness gate
- **Depends on:** M13-T04, M14-T08
- **Priority:** not part of the M13 exit criteria; required before M15-T07. Do not start it before M14-T08.
- **Areas:** `ar_domain/runs/{records.py,replay.py}`, `ar_system/workflows/run_record_seal.py`, `ar_runtime/graders/groundedness.py`, `evals/golden/groundedness/`, migration `0023_run_records`
- **Spec:** [spec 18 §4.6](../03-specs/18-observability-eval.md#46-groundedness-grader), [spec 18 §7](../03-specs/18-observability-eval.md#7-run-records-and-re-performance), [schema §22](../04-data/schema.md#22-run-records-ar_domainruns), [ADR-0022](../02-architecture/adr/ADR-0022-run-records.md)
- **Do:** `spec.assurance.recordMode` (Python attribute `record_mode`; `off` default, `on` for GRC templates, [OQ-29](../open-questions.md)). `RunRecordSealWorkflow` id `run-record-{run_id}` on `ar-system`. Seal failure audits `run_record.seal_failed` and does not fail the user run. Tool I/O is AES-256-GCM, DEK wrapped by `AR_EVIDENCE_SIGNING_KEY`, size cap `AR_RUN_RECORD_MAX_BLOB_BYTES`. The evidence foreign key is added in revision 0024, not 0023. Replay uses recorded tool results and does not call live tools. Divergence emits `run_record.replay_diverged` and does not mark the original record failed. Endpoints `GET /api/v1/run-records`, `GET /api/v1/run-records/{run_record_id}`, `POST /api/v1/run-records/{run_record_id}:replay`, `GET /api/v1/run-records/{run_record_id}/replays/{replay_id}`. Assertion type `groundedness`. Suite `evals/golden/groundedness/` gates only agents with `grounding=strict`.
- **Done when:** a recorded run can be replayed without live tools; a divergent replay is a separate row; an agent with `grounding=strict` cannot publish when the groundedness suite fails; an agent with grounding off is not gated by that suite.
- **Tests:** Temporal seal and replay; divergence; publish-gate matrix.
