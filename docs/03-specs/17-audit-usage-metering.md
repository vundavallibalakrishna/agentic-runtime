# Spec 17: Audit, usage metering, quotas and retention (`ar_domain.audit`, `ar_domain.usage`)

Endpoints served by `api`; writers in every deployable that imports `ar_domain`; background work on `system-worker` (`UsageRollupWorkflow`, `RetentionSweepWorkflow`, `AuditExportWorkflow`). Owns `audit_events`, `usage_events`, `usage_daily`, `quotas` ([schema §15](../04-data/schema.md#15-audit-and-usage-ar_domainaudit-ar_domainusage)). Action catalogue: [audit.md](../06-security/audit.md). PRD: [12-admin-tenancy-billing](../01-prd/12-admin-tenancy-billing.md).

## 1. Audit

### 1.1 Writing (`audit.service.record`)
`record(ctx, action, target_type, target_id, *, decision=None, outcome="success", detail={}, classification=None)`; called **inside the same DB transaction** as the state change it describes (so no change without audit, no audit without change). Algorithm:
1. `SELECT pg_advisory_xact_lock(hashtextextended('audit:' || tenant_id, 0))`.
2. Read last `(tenant_seq, hash)` for the tenant (index-only via `UNIQUE (tenant_id, tenant_seq)`).
3. `tenant_seq = last + 1`, `prev_hash = last.hash` (64 zeros if none), `hash = sha256(prev_hash || JCS(fields except id, hash))`.
4. `detail` passes through `ar_common.redaction.redact()` (secrets, tokens; message content is never put in `detail`; tool arguments are represented by `args_hash` only).
Actor fields come from the request principal (`ctx.principal`): user / service_account / platform_admin (impersonation: `actor_type='platform_admin'`, `on_behalf_of_user_id` unset; platform admins cannot read tenant content in SaaS mode except via support-access grants, see [authn-authz](../06-security/authn-authz.md)), `agent` for agent-initiated tool calls (actor_id = agent id, on_behalf_of_user_id = run user), `system` for workflows.
Throughput: per-tenant serialisation via the advisory lock; expected peak 200 events/s per tenant is well within budget (lock held < 2 ms).

### 1.2 SIEM streaming
If the tenant configures `settings.audit.siem` (`{enabled, webhook_id}`), every audit insert also writes an outbox event `audit.event` (public topic) delivered through outbound webhooks ([spec 20](20-notifications-events.md)) to the SIEM endpoint (JSON per event, HMAC-signed, retries per webhook policy). Syslog/CEF forwarding is done by customers via their webhook receiver (see open question OQ-09).

### 1.3 API
Permissions: `audit:read`, `audit:export`.

#### GET /api/v1/audit-events
Query `action` (prefix match, e.g. `agent.`), `actor_id`, `actor_type`, `target_type`, `target_id`, `agent_id`, `run_id`, `outcome`, `occurred_after`, `occurred_before`. Cursor pagination descending by `tenant_seq`. Item `AuditEvent {id, tenant_seq, occurred_at, actor: {type, id, display_name?}, on_behalf_of_user_id, action, target_type, target_id, agent_id, run_id, tool_call_id, decision, outcome, data_classification, ip, user_agent, trace_id, detail, hash}`.

#### GET /api/v1/audit-events/{event_id}

#### POST /api/v1/audit-events:verify
`audit:read`. Body `{from_seq?: int, to_seq?: int}` (max range 1,000,000; longer ranges run as `AuditExportWorkflow` in verify mode). Recomputes the hash chain → `{ok, checked, first_seq, last_seq, broken_at_seq?: int}`.

#### POST /api/v1/audit-exports
`audit:export`. Body `{occurred_after, occurred_before, format: "jsonl"|"csv", include_verification: true}`. Starts `AuditExportWorkflow` (id `audit-export-{uuid}`) → `202 {export_id}`.

#### GET /api/v1/audit-exports/{export_id}
`{status: running|completed|failed, file_id?, rows?, verification?: {ok, broken_at_seq?}}` (from the workflow query; completed results also persisted in `files.preview`). Notification `export_ready` to the requester.

### 1.4 `AuditExportWorkflow`
Pages through `audit_events` (10,000 rows per activity, heartbeating the last seq), streams to a gzip object `files(kind='export')`, verifies the chain while exporting. Used also by `TenantDeletionWorkflow` (to the platform audit archive bucket `AR_AUDIT_ARCHIVE_BUCKET`) and for retention before deletion.

## 2. Usage metering

### 2.1 Recording (`usage.service.record`)
`record(ctx, metric, quantity, *, cost_micros=0, dims: UsageDims, dedupe_key, source)`: inserts `usage_events` (`ON CONFLICT (tenant_id, dedupe_key) DO NOTHING`), then increments quota counters for each matching quota (`INCRBY ar:q:{quota_id}:{period_key} quantity` with expiry at period end + 2 days). Writers and dedupe keys:

| Metric | Writer | Dedupe key |
|---|---|---|
| `model_input_tokens`, `model_output_tokens`, `model_cached_tokens` | `model-gateway` | `mg:{request_id}:{in|out|cached}` |
| `embedding_tokens` | `model-gateway` | `mg:{request_id}:emb` |
| `rerank_requests` | `model-gateway` | `mg:{request_id}:rr` |
| `tool_calls` | `mcp-gateway` | `tc:{tool_call_id}` |
| `sandbox_cpu_seconds` | `mcp-gateway` (deltas from sandbox results) and `sandbox-manager` (final at suspend/terminate) | `sbx:{sandbox_id}:{cpu_total_ms}` |
| `sandbox_sessions` | `sandbox-manager` | `sbx:{sandbox_id}:start:{n}` |
| `runs` | `runtime-worker` (`finalize_run`) | `run:{run_id}` |
| `storage_bytes` | `UsageRollupWorkflow` (daily snapshot) | `st:{tenant_id}:{date}` |

`cost_micros` uses the model's prices (tenant currency `tenants.billing_currency`; platform models priced in `AR_BILLING_CURRENCY`, default `INR`; cross-currency conversion is out of scope for v1). Non-model metrics have cost 0 unless `plans.limits.unit_prices` defines a per-unit price (e.g. `sandbox_cpu_seconds`).

Quota metric mapping: `model_tokens` = input + output tokens; `cost_micros` = sum of `cost_micros`; `runs`; `sandbox_cpu_seconds`; `tool_calls`.

### 2.2 Quota enforcement (`usage.service.check_quota`)
Called before: starting a run (`runs`, `cost_micros`, `model_tokens`), each model call (`model-gateway`), tool calls (`tool_calls`), sandbox ensure (`sandbox_cpu_seconds`). For each quota applicable to the context (tenant; user's teams; user (specific or "each user"); agent): if `action='block'` and `counter ≥ limit_value` → raise `QuotaExceeded(quota_id)` → HTTP 429 `quota_exceeded` with `{quota_id, metric, period, limit, used, resets_at}`. When a counter crosses `warn_at_pct` (first time per period: Valkey `SET NX ar:qwarn:{quota_id}:{period_key}`) → notification `quota_warning` to tenant admins (+ the user for user-scoped quotas). Plan limits (`plans.limits.monthly_cost_micros` etc.) are enforced as implicit tenant quotas.
Counters are reconciled hourly from `usage_events` by `UsageRollupWorkflow` (`SET` to the DB total) to correct drift; Valkey loss → counters rebuilt on the next reconciliation (fail-open in between, metric `ar_quota_check_bypass_total`).

### 2.3 `UsageRollupWorkflow`
Temporal Schedule `usage-rollup` every 15 min: for each tenant with new events since the watermark (Valkey `ar:usage:watermark:{tenant}` + DB fallback), upsert `usage_daily` grouped by day (tenant timezone), metric, user, team (user's primary team = first team by join date, or none), agent, model alias. Daily at 00:30 tenant time: `storage_bytes` snapshot (sum of `files.size_bytes` not deleted + knowledge bytes from collection stats). Hourly: quota counter reconciliation.

### 2.4 API
#### GET /api/v1/usage/summary
`usage:read`. Query `from`, `to` (dates, ≤ 400 days), `group_by` (`day|metric|agent|user|team|model_alias`, up to 2 comma-separated), `metric?`, `agent_id?`, `user_id?`, `team_id?`. Response `{currency, rows: [{keys: {...}, quantity, cost_micros}], totals: {...}}`; includes today's not-yet-rolled-up data from `usage_events`.

#### GET /api/v1/usage/export
`usage:read`. Same filters, `format=csv` (UTF-8, header row) streaming; columns `day, metric, user_email, team, agent_slug, model_alias, quantity, cost_micros, currency`. Used for chargeback/billing.

#### GET /api/v1/me/usage
Any user: own usage summary for the current month and applicable quotas (`{quotas: [{id, metric, period, limit, used, resets_at}]}`).

#### GET /api/v1/quotas
`usage:read`. Items `Quota {id, scope_type, scope: {id, name}|null, metric, period, limit_value, action, warn_at_pct, used, resets_at}`.

#### POST /api/v1/quotas
`quotas:manage`. Body as the table columns. 409 on duplicate scope/metric/period.

#### PATCH /api/v1/quotas/{quota_id}
#### DELETE /api/v1/quotas/{quota_id}

#### GET /api/v1/platform/usage
`platform_admin`. Query `from`, `to`, `group_by=tenant|day|metric`. Cross-tenant aggregation (uses `ar_platform` role) for SaaS billing.

#### GET /api/v1/platform/usage/export
CSV per tenant per day per metric with plan key; this is the input for the SaaS invoicing system (invoicing itself is out of scope).

## 3. Retention (`RetentionSweepWorkflow`)

Temporal Schedule `retention-sweep` daily 01:00 platform time; one child per tenant (`retention-{tenant_id}-{date}`), batches of 1,000 rows per activity with heartbeats:

| Data | Rule (tenant settings `retention.*`) |
|---|---|
| Conversations (`retention_class='standard'`) | delete when `last_message_at < now() - conversations_days` (cascade messages, runs, run_steps, run_events, tool_calls; files detached and deleted by file rule) |
| `extended` | 3× `conversations_days`; `legal_hold` never; `ephemeral` 1 day |
| Soft-deleted conversations | hard delete after `deleted_conversation_days` |
| `run_events` | older than `run_events_days` (even when the conversation is kept) |
| Files | `retention_until < now()` and not on legal hold → delete object then row |
| Memory facts | `last_recalled_at` (or `created_at`) older than `memory_inactive_days`; superseded facts after 30 days |
| Audit events | older than `audit_years` → export to archive bucket (`AuditExportWorkflow`) then delete; the first remaining row keeps its `prev_hash` so verification continues from there |
| `usage_events` | older than 400 days (`usage_daily` kept 7 years) |
| `idempotency_keys` | expired |
| `notifications` | read and older than 90 days |
| `outbox_events` | delivered and older than 7 days |
| `webhook_deliveries` | older than 30 days |
| Sandboxes snapshots | template `retention_days` after termination |
| Pending approvals of terminal runs | → `cancelled` |

Every sweep writes one audit event `retention.swept` with counts.

## 4. Configuration

| Variable | Default |
|---|---|
| `AR_BILLING_CURRENCY` | `INR` |
| `AR_AUDIT_ARCHIVE_BUCKET` | `ar-audit-archive` |
| `AR_USAGE_ROLLUP_INTERVAL` | `15m` |
| `AR_RETENTION_SWEEP_CRON` | `0 1 * * *` |

## 5. Metrics

`ar_audit_events_total{action_prefix}`, `ar_audit_write_seconds`, `ar_usage_events_total{metric,source}`, `ar_quota_blocks_total{metric,scope}`, `ar_quota_check_bypass_total`, `ar_usage_rollup_lag_seconds`, `ar_retention_deleted_total{kind}`.

## 6. Test plan

- Unit: hash chain computation (known vectors), redaction, quota applicability, period keys across timezones/month ends, CSV export format.
- Integration: concurrent audit writes for one tenant produce gapless `tenant_seq` and a valid chain (100 parallel transactions); tampering with a row (as `ar_owner`) is detected by `:verify`; usage dedupe (same key twice → one row); quota block at limit and warning notification once; rollup correctness vs raw events; retention sweep honours legal hold and classes.

## 7. Legal hold interaction

From M14-T09, `RetentionSweepWorkflow` and `ErasureWorkflow` skip any row listed in `legal_hold_members` for an active hold ([spec 21 §2](21-records-governance.md#2-legal-hold-and-retention-schedules)). The conversation class `legal_hold` remains the denormalised marker this sweep already honours. Erasure completion detail includes `held_record_ids` for rows that were kept. Audit archive objects under hold are not passed to `purge_audit_events`.
