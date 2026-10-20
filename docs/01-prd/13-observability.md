# PRD 13 — Observability

Operators and builders understand what the platform and each agent are doing through traces, metrics, logs, dashboards, alerts and an in-product run inspector — without exposing content in telemetry. Spec: [spec 18 §1–3](../03-specs/18-observability-eval.md#1-telemetry-architecture), [runbooks](../07-ops/runbooks.md). Plan: [M13](../09-plan/M13-observability-eval.md).

### US-OBS-01 · End-to-end traces (P0)
As a **platform operator**, I want one trace per request/run spanning api, workers, gateways, tool servers and sandboxes.
- OpenTelemetry in every deployable (`ar_common.telemetry.setup`), context propagated over HTTP, Temporal and MCP; GenAI semantic conventions on model and tool spans; error traces always kept (tail sampling), others at `AR_TRACE_SAMPLE_RATIO`.
- No prompts, messages, tool arguments or results on spans, metrics or logs (tested by canary scanning).
- Spec: spec 18 §1. Plan: M0-T04, M13-T01.

### US-OBS-02 · Dashboards (P0)
As a **platform operator**, I want ready-made dashboards for API, runs, models, tools, ingestion, sandboxes, Temporal, Postgres and tenants.
- Grafana dashboards shipped with the chart (`ar-overview`, `ar-runs`, `ar-models`, `ar-tenants`, …); each panel backed by documented metrics.
- Spec: spec 18 §2, §5. Plan: M13-T01.

### US-OBS-03 · Actionable alerts (P0)
As an **on-call engineer**, I want alerts that link to runbooks.
- PrometheusRules for the alerts in spec 18 §2, each with a runbook anchor in [runbooks](../07-ops/runbooks.md); SLOs per [performance-budgets §1](../08-quality/performance-budgets.md#1-service-level-objectives-production).
- Spec: spec 18 §2. Plan: M13-T01.

### US-OBS-04 · Agent quality overview (P0)
As a **builder** or **tenant admin**, I want an overview of runs, latency, tool errors, approvals, feedback and cost per agent.
- `GET /api/v1/observability/overview` (permission `usage:read`) with time range and agent filter, shown on the observability page.
- Spec: spec 18 §3. Plan: M13-T02, M13-T05.

### US-OBS-05 · Run inspector (P0)
As a **builder**, I want to drill into one run: timeline of steps, model calls (tokens, latency, cost), tool calls (decision, approval, duration), subagents, events, and a link to the trace.
- Built on spec 06 run endpoints plus `trace_url`/`langfuse_url`; content visible only with conversation access.
- Spec: spec 18 §3, spec 06 §3. Plan: M13-T02, M13-T05.

### US-OBS-06 · Platform health (P0, SaaS and single-tenant operators)
As a **platform operator**, I want one page showing the health of every component and model provider.
- `GET /api/v1/platform/health` aggregates readiness of deployables and dependencies with status `up|degraded|down`.
- Spec: spec 18 §3. Plan: M13-T02.
