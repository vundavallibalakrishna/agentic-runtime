# Performance budgets

Budgets are **platform overhead** unless stated: model generation time and upstream tool latency are excluded (measured against `fake-llm` with fixed latency and test MCP servers). Measured in load tests (M15-T04, Locust) and continuously via metrics ([spec 18](../03-specs/18-observability-eval.md)). A budget breach blocks release (see [testing-strategy §8](testing-strategy.md#8-coverage-and-gates)).

## 1. Service-level objectives (production)

| SLO (30-day window) | Target | Metric |
|---|---|---|
| API availability (non-5xx for valid requests) | 99.9 % | `ar_http_requests_total` |
| Run start latency (POST message → `run.started`) | p95 < 2 s | `ar_run_start_latency_seconds` |
| Time to first token overhead (platform part) | p95 < 300 ms | `ar_runtime_ttft_seconds` minus `ar_mg_ttft_seconds` upstream part |
| Tool-call gateway overhead | p95 < 50 ms | `ar_tool_call_seconds{phase="overhead"}` |
| Approval notification delivery (in-app) | p95 < 5 s from request | `ar_notifications_delivered_total` timing |
| Routine schedule lag | p95 < 60 s | `ar_routine_schedule_lag_seconds` |

## 2. Component budgets (p95 unless noted, at target load)

| Path | Budget | Source |
|---|---|---|
| Simple authenticated GET (list ≤ 50 items) | < 100 ms server time | api |
| `POST /api/v1/conversations/{conversation_id}/messages` → 202 | < 150 ms | [spec 06](../03-specs/06-conversations-runs.md) |
| Context assembly (`build_prompt`, excl. retrieval) | < 50 ms | [spec 07](../03-specs/07-agent-runtime.md) |
| Knowledge search (hybrid + rerank, 50 candidates) | < 400 ms (< 150 ms without rerank; store query p95 ≤ 80 ms on the pgvector adapter up to 5 M chunks, [scaling §4](../07-ops/scaling.md#4-retrieval-store-sizing)) | [spec 10](../03-specs/10-knowledge.md) |
| Memory recall | < 80 ms excl. embedding | [spec 11](../03-specs/11-memory.md) |
| Model gateway added TTFT | < 15 ms; per-chunk added < 5 ms | [spec 04](../03-specs/04-model-gateway.md) |
| Policy decision (OPA) | < 10 ms (p99 < 25 ms) | [spec 09](../03-specs/09-policy-approvals.md) |
| Quota/rate-limit check | < 2 ms | [spec 17](../03-specs/17-audit-usage-metering.md) |
| Audit write (in transaction) | < 5 ms | spec 17 |
| SSE event fan-out (Valkey → client) | < 100 ms from emit | [stream-events](../05-contracts/stream-events.md) |
| Sandbox ensure from warm pool | < 2 s; cold < 15 s | [spec 12](../03-specs/12-sandbox-manager.md) |
| Sandbox exec round-trip (`echo`) | < 150 ms | spec 12 |
| File upload processing (10 MB PDF to `ready`) | < 30 s | [spec 13](../03-specs/13-files-artifacts.md) |
| Document ingestion throughput | ≥ 20 text pages/s per ingest-worker pod | [spec 10](../03-specs/10-knowledge.md) |
| Outbox relay lag | < 5 s | [spec 20](../03-specs/20-notifications-events.md) |
| Channel reply first update (Slack/Teams) | < 3 s from inbound event (excl. model) | [spec 16](../03-specs/16-channels.md) |
| Web: LCP `/chat` | < 2.0 s; INP < 200 ms; shell JS ≤ 250 KB gzip | [spec 19 §7](../03-specs/19-web-app.md#7-performance-budgets-web) |

## 3. Target load

The release load test runs `values-loadtest.yaml` (based on `values-large.yaml`) and must meet all budgets at:

| Dimension | Target |
|---|---|
| Provisioned users | 10,000 (single tenant) and 200 tenants × 50 users (SaaS run) |
| Concurrently active users | 1,000 |
| Chat turns | 10 run starts/s sustained, 50/s burst for 60 s |
| Concurrent active runs | 300 (each with 1–5 model steps, 0–3 tool calls; fake-llm 40 ms/chunk, 30 chunks) |
| Open SSE streams | 2,000 |
| Tool calls | 30/s (mix: 60 % R0, 30 % W1, 10 % requiring approval auto-approved by a bot user) |
| Knowledge searches | 20/s over 5 M chunks |
| Concurrent sandboxes | 100 (warm pool 20) |
| Routine bursts | 500 routines firing at the same minute |
| Uploads | 2/s, 1–10 MB |

Soak: 24 h at 50 % of target load with no error-rate increase, no memory growth > 10 % per pod, no Postgres bloat beyond autovacuum capacity.

## 4. Resource budgets

| Deployable | Request / limit (default values-large) | Idle RSS budget |
|---|---|---|
| api | 1 CPU / 2 CPU, 1 GiB / 2 GiB | < 300 MB |
| runtime-worker | 1 / 2 CPU, 1 / 2 GiB | < 400 MB |
| model-gateway, mcp-gateway | 0.5 / 2 CPU, 512 MiB / 1 GiB | < 200 MB |
| ingest-worker | 1 / 2 CPU, 2 / 4 GiB | < 800 MB (models loaded) |
| web | 0.5 / 1 CPU, 512 MiB / 1 GiB | < 250 MB |
| Container image size | ≤ 400 MB (ingest and sandbox images excepted) | |

## 5. How to measure

- Locust scenarios in `tests/load/scenarios/` (one per row in §3) with custom SSE client measuring TTFT and event latency.
- Server-side truth from Prometheus histograms (§1 metrics); Locust numbers are cross-checks.
- Results: `docs/08-quality/reports/load-<date>.md` with p50/p95/p99 per budget, resource usage and tuning changes (recorded into [scaling §6](../07-ops/scaling.md#6-tuned-values)).
