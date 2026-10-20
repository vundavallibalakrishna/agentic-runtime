# Runbooks

Each alert in [spec 18 §2](../03-specs/18-observability-eval.md) links here. Format: **Symptom → Check → Mitigate → Follow-up**. Dashboards referenced (`ar-*`) are provisioned by the chart. Commands assume `kubectl -n agentic-runtime` and the `temporal` CLI pointed at `AR_TEMPORAL_ADDRESS`.

General rules: open an incident channel, assign an incident lead, record actions with timestamps (IST), never edit production data by hand except via the scripts named here, and write a post-incident review within 5 working days.

## rb-01-api-errors
Alert `ARApiHighErrorRate` (5xx > 2 % for 5 min).
- **Check:** dashboard `ar-api` → errors by route and `error.code`; `kubectl logs deploy/api --since=15m | jq 'select(.level=="error")'`; `/readyz` of api pods (DB, Valkey, Temporal); recent deploy (`helm history`).
- **Mitigate:** recent deploy → `helm rollback agentic-runtime <rev>`; DB saturation → see rb-11; Valkey down → sessions/rate-limits fail: restart/failover Valkey (Sentinel), api degrades to 503 for streaming; a single route failing → disable the feature flag for affected tenants (`PATCH /api/v1/platform/tenants/{tenant_id}` features).
- **Follow-up:** add regression test; check error budget.

## rb-02-slow-run-start
Alert `ARRunStartLatencyHigh` (p95 `ar_run_start_latency_seconds` > 3 s).
- **Check:** split of latency: API insert → workflow start (`ar_run_start_deferred_total` rising means Temporal start failures), schedule-to-start on `ar-runtime` (rb-05), context assembly spans (`ar_runtime.context.build_prompt`), knowledge/memory recall latency (`ar_knowledge_search_seconds`, `ar_memory_recall_seconds`), sandbox ensure (`ar_sandbox_ensure_seconds`).
- **Mitigate:** scale runtime-worker (`kubectl scale deploy/runtime-worker --replicas=N`, KEDA max), raise warm pool (`AR_SANDBOX_WARM_POOL`), check retrieval latency (rb-07, retrieval part), check Postgres slow queries (`pg_stat_statements`).
- **Follow-up:** record in scaling §6.

## rb-03-runs-stuck-in-queued
Alert `ARRunsStuckQueued` (runs `queued` > 60 s).
- **Check:** `SELECT tenant_id, count(*) FROM runs WHERE status='queued' AND created_at < now()-interval '60 seconds' GROUP BY 1;` (as `ar_platform`). One tenant only → tenant concurrency cap (`AR_RUNTIME_TENANT_MAX_ACTIVE_RUNS` / plan) is working as designed; inform tenant or raise plan limit. All tenants → Temporal or worker issue: `temporal task-queue describe --task-queue ar-runtime` (pollers present?), `ar_run_start_deferred_total`.
- **Mitigate:** restart runtime-worker; if Temporal was unavailable, `OutboxRelayWorkflow` re-delivers the committed `run.start_requested` outbox events and starts the workflows (deterministic id `run-{run_id}`, so duplicates are no-ops) — verify the relay is running (rb-13).
- **Follow-up:** confirm reconciler metrics.

## rb-04-model-upstream-down
Alert `ARModelNoHealthyUpstream`.
- **Check:** dashboard `ar-models` (circuit state, `ar_mg_requests_total{outcome}`, `ar_mg_fallbacks_total`); provider health in **Admin → Models**; model-gateway logs for upstream status codes; network policy/CIDR allowlist changes.
- **Mitigate:** add/enable a fallback target on the alias (`PATCH /api/v1/model-aliases/{alias_id}`); if a provider credential expired, rotate the secret; communicate degraded mode (runs fail fast with `model_unavailable`).
- **Follow-up:** ensure every production alias has ≥ 2 targets.

## rb-05-temporal-backlog
Alert `ARTemporalBacklog` (schedule-to-start p95 > 5 s).
- **Check:** `temporal task-queue describe` for `ar-runtime`, `ar-system`, `ar-eval`, `ar-ingest`; worker pod CPU/memory; KEDA ScaledObject status; Temporal history service CPU and persistence latency.
- **Mitigate:** increase KEDA `maxReplicaCount`; raise `AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES` if CPU is low; for `ar-ingest` floods pause large syncs (`POST /api/v1/knowledge/sources/{source_id}:pause`, later `:resume`); scale Temporal history/matching pods.
- **Follow-up:** revisit capacity formula (scaling §5).

## rb-06-opa-unavailable
Alert `AROpaUnavailable` (`ar_policy_fallback_total` increasing). Tool calls are **fail-closed**: calls are denied (reason `policy_unavailable`) while OPA is unreachable, except the R0 built-ins (`knowledge.*`, `memory.search`, `files.list/read`, `plan.update`) allowed by the in-process fallback evaluator ([spec 08 §13](../03-specs/08-tool-registry-mcp.md#13-failure-modes)).
- **Check:** `kubectl get pods -l app=opa`; `/health?bundles` (bundle download from `api` failing? check `AR_OPA_BUNDLE_TOKEN`); `ar_opa_bundle_build_seconds`.
- **Mitigate:** restart OPA; if a bad bundle was activated, re-activate the previous policy version (`POST /api/v1/policies/{policy_id}:activate` with body `{version}` of the last good version).
- **Follow-up:** add the failing case to `opa test`.

## rb-07-ingestion-failures
Alerts `ARIngestFailures` (> 10 % failure ratio for 30 min), `ARRetrievalLatencyHigh`, `ARRetrievalStoreErrors`. Covers ingestion and retrieval.
- **Check:** `ar_ingest_documents_total{outcome="failed"}` by `error_code`; `GET /api/v1/knowledge/collections/{collection_id}/jobs?status=failed`; source credentials (connection expired?), parser errors (ingest-worker logs), retrieval store health in `GET /api/v1/platform/health` (pgvector: Postgres up, `vector` extension ≥ 0.8; qdrant adapter: `/readyz`, disk), embedding alias health (rb-04). Retrieval latency: `ar_retrieval_store_seconds` by backend; for pgvector check HNSW index size vs memory (`pg_relation_size('ix_chunk_emb_hnsw_1024')`, buffer hit ratio in `pg_statio_user_indexes`) and `EXPLAIN (ANALYZE, BUFFERS)` of a sample search from the `debug` output of `POST /api/v1/knowledge/search`.
- **Mitigate:** reconnect the source credential; retry documents (`POST /api/v1/knowledge/documents/{document_id}:reingest`) or the whole source (`POST /api/v1/knowledge/sources/{source_id}:sync`); pgvector latency: enable or scale the read replica (`AR_VECTOR_PG_READ_DSN`), add RAM, lower `AR_VECTOR_PG_EF_SEARCH` temporarily (recall drops), or follow [scaling §4](scaling.md#4-retrieval-store-sizing) to move to the qdrant adapter; qdrant disk pressure: expand the PVC; for a poison document, the job is skipped after 3 attempts and marked `failed` (no action needed).
- **Follow-up:** add the document type to parser tests if it is a bug.

## rb-08-sandbox-capacity
Alert `ARSandboxEnsureSlow` (p95 ensure > 20 s).
- **Check:** pending sandbox pods (`kubectl -n ar-sandboxes get pods --field-selector=status.phase=Pending`), node pool autoscaler events, ResourceQuota exhaustion, image pull times (registry), warm pool size vs demand.
- **Mitigate:** scale node pool; increase warm pool; reduce `AR_SANDBOX_MAX_PER_TENANT` for a noisy tenant; reaper health (`SandboxReaperWorkflow` running?) — orphaned pods: `uv run python -m ar_sandbox_manager.reap --dry-run` then without `--dry-run`.
- **Follow-up:** pre-pull images via DaemonSet.

## rb-09-audit-chain-broken
Alert `ARAuditChainBroken`. **Treat as a potential security incident.**
- **Check:** `POST /api/v1/audit-events:verify` result for the tenant (first broken `tenant_seq`); Postgres logs for superuser sessions around the event time; whether a restore (backup-dr §2) happened (a PITR can legitimately truncate the chain tail — compare with the archive).
- **Mitigate:** do not modify `audit_events`. Preserve evidence (snapshot DB, export archive). Compare with the Object Lock archive to identify altered/missing rows. Notify security lead and, for SaaS, the tenant within 24 h.
- **Follow-up:** post-incident review; rotate database credentials.

## rb-10-certificates
Alert `ARCertificateExpiry` (< 14 days).
- **Check:** `kubectl get certificates -A`; cert-manager logs; ACME/issuer reachability; customer-provided certificates (single-tenant) in Secret referenced by values.
- **Mitigate:** `cmctl renew <cert>`; for customer-provided certs request a new one; internal JWT keys are separate (rotate per [secrets](../06-security/secrets.md)).

## rb-11-postgres
Alerts `ARPostgresReplicationLag`, `ARPostgresWALArchiveLag`, `ARBackupMissing`, `ARBackupVerificationFailed`, connection saturation.
- **Check:** `kubectl cnpg status ar-pg`; replication lag; WAL archive status; `pg_stat_activity` (long transactions, idle in transaction), PgBouncer pools; disk usage; `pg_stat_statements` top queries.
- **Mitigate:** kill runaway queries (`pg_terminate_backend`); expand storage; failover (`kubectl cnpg promote ar-pg <replica>`) if primary unhealthy; fix archive credentials; trigger a manual backup (`kubectl cnpg backup ar-pg`).
- **Follow-up:** index or query fix with migration; capacity review.

## rb-12-partition-a-large-table
When `run_events`, `usage_events`, `audit_events` or `messages` exceed ~200 M rows or vacuum falls behind ([migrations §4](../04-data/migrations.md#4-partitioning-roadmap), decision rule: OQ-07).
- **Procedure:** expand/contract over two releases: (1) migration creates `<table>_p` partitioned by range on the time column (monthly) with identical columns, indexes, RLS policies and grants (and the append-only trigger for `audit_events`); (2) dual-write via trigger from old to new; (3) backfill in batches of 50k rows with `scripts/db/backfill_partition.py --table <t>` (throttled, resumable); (4) verify counts and audit chain; (5) swap names in a short lock window (`ALTER TABLE … RENAME`), drop the trigger; (6) retention switches from `DELETE` to dropping partitions (`purge_audit_events` handles both).
- **Rollback:** before step 5, drop the new table; after, keep the old table for one release.

## rb-13-outbox-backlog
Alert `ARQueueDepthOutbox` (unpublished events > 60 s).
- **Check:** `ar_outbox_lag_seconds`; `OutboxRelayWorkflow` running (`temporal workflow describe -w outbox-relay`); `ar_outbox_subscriber_errors_total` by subscriber; Postgres locks on `outbox_events`.
- **Mitigate:** restart system-worker; if a subscriber keeps failing, its events are retried with backoff and do not block others; terminate and restart the relay workflow (`temporal workflow terminate -w outbox-relay` — it is re-created by system-worker on start).

## rb-14-secret-leak
A secret (API key, provider credential, signing key, OAuth token) is suspected exposed (log, repo, ticket, scanner finding).
1. Identify the secret and its owner from [secrets §1](../06-security/secrets.md).
2. **Rotate first, investigate second**: tenant secrets via `POST /api/v1/secrets/{secret_id}:rotate`; API keys revoke (`DELETE /api/v1/api-keys/{api_key_id}`); platform keys per secrets.md rotation procedure (session key: set `AR_SESSION_ENCRYPTION_KEY_PREVIOUS` to the old key, new key in `AR_SESSION_ENCRYPTION_KEY`, roll api, remove previous after `AR_SESSION_MAX_AGE_S`); internal JWT keys: publish new kid, roll, retire old.
3. Search audit (`secret.*`, `api_key.*`, `tool.called` by the credential) and upstream provider logs for misuse in the exposure window.
4. If personal data may be affected, continue with rb-15.
5. Remove the secret from the leak location (history rewrite for repos via security team).

## rb-15-personal-data-breach
1. Contain (revoke access, rotate credentials, isolate affected components).
2. Assess: which tenants, which data categories ([data-protection §1](../06-security/data-protection.md#1-personal-data-inventory)), number of data principals, time window — use audit queries and access logs.
3. SaaS: notify affected tenants (Data Fiduciaries) without undue delay using template `deploy/templates/breach-notice.md` with facts, likely consequences, mitigation, contact. Tenants notify the Data Protection Board and affected principals per DPDP Rules timelines. Single-tenant: the customer's process applies; vendor supports with logs.
4. Preserve evidence; post-incident review with corrective actions tracked.

## Break-glass access

For emergencies when normal access paths fail (IdP outage, locked-out admins, data repair).
- **Platform (operator) DB access:** role `ar_readonly` for diagnosis; write access only via `ar_platform` credentials stored in the operator vault under dual control (two operators must approve retrieval). Every session is recorded (terminal recording) and logged in the incident ticket; `platform.session_opened` audit event is written by `scripts/breakglass/open_session.py`, which must be used to obtain credentials.
- **Tenant admin lockout (IdP down):** Keycloak realm has a per-tenant local break-glass admin (`breakglass@<tenant-domain>`) with hardware-key WebAuthn, disabled by default; enabling it requires a platform admin + tenant contact confirmation and writes `auth.login` with `detail.break_glass=true`.
- **SaaS tenant content:** never via break-glass; only via support-access grants ([authn-authz §6](../06-security/authn-authz.md#6-support-access-saas)).
- After use: rotate the used credentials, disable the break-glass account, review the audit trail within 24 h.
