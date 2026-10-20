# M12 — Usage, quotas & billing

Goal: cost control and attribution. Admins set quotas per tenant, team, user or agent; plan limits are enforced everywhere; everyone sees usage and cost by day, agent, user and model.

Exit criteria: a user quota of 10,000 tokens/day blocks the next run with `quota_exceeded` and a clear message; the warn threshold sends a `quota.warning` notification; usage CSV export matches `usage_daily`; creating the 201st agent on a plan with `max_agents=200` fails with 409 `plan_limit_reached`.

---

### M12-T01 · Quotas API and enforcement
- **Depends on:** M2-T03, M6-T06, M4-T03
- **Areas:** `ar_domain/usage/{quotas.py,service.py}`, `ar_api/routers/quotas.py`, enforcement hooks in `ar_model_gateway`, `ar_runtime/activities/start_run.py`, `ar_mcp_gateway/pipeline.py`, `ar_sandbox_manager/service.py`
- **Spec:** [spec 17 §2.2, §2.4](../03-specs/17-audit-usage-metering.md#22-quota-enforcement-usageservicecheck_quota)
- **Do:** `GET/POST /api/v1/quotas`, `PATCH/DELETE /api/v1/quotas/{quota_id}`; `check_quota` with Valkey counters (period windows in tenant timezone, reconciled from `usage_daily`), implicit tenant quota from plan `monthly_cost_micros`; enforcement at run start, model calls, tool calls and sandbox start; `quota.warning` events once per threshold per period; `quota_exceeded` problem and run failure reason.
- **Done when:** counters converge with `usage_daily` after rollup; enforcement adds < 2 ms p95.
- **Tests:** integration per endpoint; concurrency test for counters; enforcement at each point.

### M12-T02 · Plan limit enforcement
- **Depends on:** M12-T01, M11-T01
- **Areas:** `ar_domain/identity/plan_limits.py`, creation paths in agents, tools, knowledge, routines, users, files, sandboxes
- **Spec:** [spec 02 §3.10, §6](../03-specs/02-identity-tenancy.md#6-limits)
- **Do:** One `plan_limits.check(ctx, limit_key, delta)` used by every creation path listed in PlanLimits (`max_users`, `max_agents`, `max_tool_servers`, `max_collections`, `max_knowledge_documents`, `max_knowledge_bytes`, `max_storage_gb`, `max_routines`, `max_concurrent_runs`, `max_concurrent_sandboxes`, `max_sandbox_cpu_millis`, `max_sandbox_memory_mb`, `api_rpm`, `max_retention`) and feature checks (`features.*`), raising 409 `plan_limit_reached` / 403 `forbidden` (`feature_not_in_plan:<feature>`) per api-conventions §5; single-tenant `self_hosted` plan defaults.
- **Done when:** a table-driven test covers every PlanLimits key.
- **Tests:** table-driven integration tests.

### M12-T03 · Usage reports
- **Depends on:** M12-T01
- **Areas:** `ar_api/routers/{usage.py,platform_usage.py}`, `ar_domain/usage/reports.py`
- **Spec:** [spec 17 §2.4](../03-specs/17-audit-usage-metering.md#24-api)
- **Do:** `GET /api/v1/usage/summary` (group by day/agent/user/team/model, filters), `GET /api/v1/usage/export` (CSV streaming), `GET /api/v1/me/usage`, `GET /api/v1/platform/usage`, `GET /api/v1/platform/usage/export`; cost in tenant `billing_currency` micros.
- **Done when:** totals equal the sum of `usage_events` for closed days.
- **Tests:** integration with seeded usage; CSV format snapshot.

### M12-T04 · Web: usage and quotas
- **Depends on:** M12-T03
- **Areas:** `apps/web/src/app/(admin)/admin/{usage,quotas}/**`, `apps/web/src/app/(app)/settings/profile/**` (my usage card)
- **Spec:** [spec 19 `/admin/usage`, `/admin/quotas`](../03-specs/19-web-app.md)
- **Do:** Usage charts (recharts) with grouping and date range, CSV export, quotas CRUD with live consumption bars, "my usage" card, quota-exceeded UI states in chat.
- **Done when:** M12 exit scenario visible in the UI.
- **Tests:** Vitest; Playwright quota block message; axe.
