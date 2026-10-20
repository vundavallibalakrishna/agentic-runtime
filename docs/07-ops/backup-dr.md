# Backup and disaster recovery

Objectives (production presets `small`, `large`, `saas`): **RPO 15 minutes, RTO 4 hours** for a full-region/cluster loss; single-component failures recover automatically via HA (see [helm-k8s §3](helm-k8s.md#3-stateful-dependencies)).

## 1. What is backed up

| Data | Method | Frequency | Retention | RPO contribution |
|---|---|---|---|---|
| Postgres `ar` (system of record), `temporal`, `temporal_visibility`, `keycloak`, `langfuse` | CloudNativePG Barman: base backup + continuous WAL archiving to S3 (DR bucket in another zone/region) | Base daily 01:30 IST; WAL archived at least every 5 min (`archive_timeout=300`) | 35 days PITR | ≤ 5 min |
| Object storage (`ar-files`) | Bucket versioning + asynchronous replication to DR bucket | Continuous | Non-current versions 30 days | ≤ 15 min |
| Audit archive (`ar-audit-archive`) | Object Lock (compliance mode) + replication | Continuous | `audit_years` (7 y) | ≤ 15 min |
| Knowledge vectors, default pgvector adapter (`chunk_embeddings`) | Part of the Postgres `ar` backup (no separate step) | — | — | Same as Postgres |
| Qdrant (only with the optional qdrant adapter) | Collection snapshots to S3 | Every 6 h | 7 days | Rebuilt from Postgres `documents`/`document_chunks` metadata + sources via `ReindexCollectionWorkflow` if snapshot is stale; deltas since snapshot replayed by re-running `SourceSyncWorkflow` |
| OpenBao | Raft snapshots to S3 (encrypted) | Hourly | 30 days | ≤ 60 min (secrets change rarely; rotation events are audited so gaps can be re-applied) |
| Keycloak | Postgres backup + nightly realm export (JSON, without secrets) | Nightly | 30 days | Via Postgres |
| Helm values + Secrets | GitOps repo (values) + sealed/external secrets | On change | Git history | 0 |
| Valkey | Not backed up | — | — | Sessions lost (users re-login); live streams lost (clients fall back to `run_events`) |

Encryption: all backups encrypted at rest (S3 SSE-KMS or SSE-S3 per `AR_S3_SSE`); DR bucket credentials separate from production write credentials (backups cannot be deleted by the app role).

## 2. Recovery procedures

### 2.1 Point-in-time restore (logical corruption, bad migration)
1. Declare incident; pause traffic (`helm upgrade --set global.maintenance=true` serves a maintenance page from web and 503 from api).
2. Stop workers (scale `runtime-worker`, `system-worker`, `ingest-worker` to 0).
3. Create a new CNPG cluster `ar-pg-restore` with `bootstrap.recovery` and `recoveryTarget.targetTime` = just before the incident.
4. Verify: `scripts/dr/verify_restore.py` (row counts vs expected, `alembic current`, audit chain verification for all tenants, sample queries).
5. Switch `AR_DATABASE_URL` secret to the restored cluster; scale workers up; leave maintenance.
6. Temporal: workflows that completed after the target time are re-driven idempotently where applicable (deterministic workflow ids); runs whose DB rows no longer exist are terminated by `scripts/dr/reconcile_temporal.py`.

### 2.2 Full cluster/region loss
1. Provision the target cluster (same chart version) in the DR region; restore secrets (OpenBao snapshot restore, then unseal).
2. Restore Postgres from the DR bucket (latest WAL).
3. Point object storage to the replicated DR bucket.
4. Knowledge vectors come back with Postgres (pgvector adapter). Only if the optional qdrant adapter is in use: restore Qdrant snapshots; start `ReindexCollectionWorkflow` for collections whose snapshot is older than the Postgres restore point (marks them `reindexing`; retrieval works on stale data meanwhile).
5. Install the chart with `migrate` Job (no-op if schema current); update DNS / Gateway to the DR cluster.
6. Run smoke + `audit-events:verify` for all tenants; announce recovery.
Target timeline: infra 60 min, data restore 90 min, validation 45 min, DNS + smoke 30 min (≈ 3.75 h).

### 2.3 Single tenant restore (SaaS)
No per-tenant PITR in shared tier. Procedure: restore PITR into a scratch cluster, export the tenant's rows with `scripts/dr/export_tenant.py --tenant <id>` (respects FK order), import into production after the tenant confirms the overwrite scope. Dedicated-tier tenants (`dedicated_db`) are restored like §2.1 on their own database.

## 3. Drills

- Weekly automated restore verification (M15-T03): latest backup restored into namespace `ar-dr-drill`, verification script, report artefact; alert `ARBackupVerificationFailed` on failure.
- Quarterly full DR exercise in staging following §2.2 with measured RTO/RPO recorded in `docs/07-ops/dr-drills.md` (created by the first drill).

## 4. Alerts

`ARPostgresWALArchiveLag` (> 10 min), `ARBackupMissing` (no base backup in 26 h), `ARQdrantSnapshotMissing` (> 8 h; only when `qdrant.enabled`), `ARBaoSnapshotMissing` (> 2 h), `ARBackupVerificationFailed`. Runbook: [rb-11-postgres](runbooks.md#rb-11-postgres).
