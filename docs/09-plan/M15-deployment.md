# M15 — Deployment

Goal: shippable product. One Helm umbrella chart deploys both modes; installs work air-gapped; backups and DR are proven; performance budgets are met under load; upgrade path tested; release 1.0 cut.

Exit criteria: `helm install` on a fresh kind cluster (single-tenant, `values-small.yaml`) and on a SaaS-like cluster (`values-saas.yaml`) passes the e2e smoke suite; a DR drill restores Postgres (PITR; includes knowledge vectors with the default pgvector adapter) and object storage into a new namespace within the RTO; load test meets [performance-budgets](../08-quality/performance-budgets.md); upgrade from the previous release candidate with live traffic has no failed requests beyond budget.

---

### M15-T01 · Helm umbrella chart
- **Depends on:** M14-T07
- **Areas:** `deploy/helm/agentic-runtime/**` (Chart.yaml, values*.yaml, templates per deployable, migrate/bootstrap Jobs, NetworkPolicies, PDBs, HPAs, KEDA ScaledObjects, ServiceMonitors, Gateway API routes, RuntimeClass refs, sandbox namespace), `deploy/helm/agentic-runtime/values.schema.json`
- **Spec:** [helm-k8s](../07-ops/helm-k8s.md), [deployment-modes](../00-overview/deployment-modes.md), [environments](../07-ops/environments.md)
- **Do:** Chart per helm-k8s (all deployables, config via ConfigMap/Secret with every `AR_*` variable from environments.md, external-or-bundled dependencies toggles, presets `values-dev.yaml`, `values-small.yaml`, `values-large.yaml`, `values-saas.yaml`), `values.schema.json` validation, `helm test` hooks (health checks), `global.imageRegistry` for air-gapped installs.
- **Done when:** `helm lint`, `helm template | kubeconform`, and `helm install` on kind succeed for every preset.
- **Tests:** CI chart job (lint, kubeconform, chart-testing install on kind).

### M15-T02 · Stateful dependencies and operators
- **Depends on:** M15-T01
- **Areas:** `deploy/helm/agentic-runtime/charts/` (dependencies), `deploy/helm/agentic-runtime/templates/{cnpg-cluster.yaml,valkey.yaml,temporal-values.yaml,keycloak.yaml,openbao.yaml,seaweedfs.yaml}`
- **Spec:** [helm-k8s §3](../07-ops/helm-k8s.md#3-stateful-dependencies), [backup-dr](../07-ops/backup-dr.md)
- **Do:** CloudNativePG cluster (3 instances, PITR to S3), optional Qdrant subchart (`qdrant.enabled: false` by default; 3 replicas and snapshots when enabled; `retrieval.backend` → `AR_VECTOR_BACKEND`), Valkey (primary + replica + sentinel or cluster per values), Temporal (Postgres persistence, separate DB), Keycloak (2 replicas, realm import job), OpenBao (HA Raft), SeaweedFS (or external S3), each optional for "bring your own".
- **Done when:** `values-small.yaml` bundled install and an "external services" install both pass smoke tests.
- **Tests:** kind installs in nightly CI.

### M15-T03 · Backup, restore and DR drill automation
- **Depends on:** M15-T02
- **Areas:** `scripts/dr/{backup_verify.sh,restore_drill.sh}`, `deploy/helm/agentic-runtime/templates/backup-cronjobs.yaml`
- **Spec:** [backup-dr](../07-ops/backup-dr.md)
- **Do:** Scheduled backups (CNPG base backups + WAL, Qdrant snapshots to S3 only when `qdrant.enabled`, object storage replication/versioning, OpenBao Raft snapshots, Keycloak realm export), verification job restoring the latest backup weekly into a scratch namespace and running integrity checks (row counts, audit chain verification, sample retrieval).
- **Done when:** the drill script restores a full environment within RTO 4 h and data loss ≤ RPO 15 min on the test dataset.
- **Tests:** nightly/weekly drill job with report artefact.

### M15-T04 · Load and soak testing
- **Depends on:** M15-T02
- **Areas:** `tests/load/{locustfile.py,scenarios/*.py}`, `deploy/helm/agentic-runtime/values-loadtest.yaml`
- **Spec:** [performance-budgets](../08-quality/performance-budgets.md), [scaling](../07-ops/scaling.md)
- **Do:** Locust scenarios (chat turns with streaming via fake-llm with realistic latency, tool calls, retrieval, uploads, approvals, routine bursts), 24 h soak at nominal load, autoscaling validation (HPA/KEDA), tuning of pool sizes and worker concurrency recorded in scaling.md.
- **Done when:** all budgets met at the target load of performance-budgets §3; no memory growth > 10 % over the soak.
- **Tests:** load-test report committed under `docs/08-quality/reports/` (created by this task).

### M15-T05 · Upgrade path and zero-downtime rollout
- **Depends on:** M15-T01
- **Areas:** `deploy/helm/agentic-runtime/templates/*` (rollout strategies), `tests/e2e/test_upgrade.py`, Temporal worker versioning config
- **Spec:** [ci-cd §6](../07-ops/ci-cd.md#6-releases-and-upgrades), [migrations §2](../04-data/migrations.md#2-rules-never-skip)
- **Do:** Rolling updates with PDBs, migrate Job pre-upgrade hook, Temporal worker versioning (build ids) so in-flight runs replay on compatible workers, SSE reconnect on pod rotation, upgrade test from previous tag under load.
- **Done when:** upgrade under load completes with error rate < 0.1 % and no failed runs.
- **Tests:** CI upgrade test on kind.

### M15-T06 · Single-tenant and air-gapped installation
- **Depends on:** M15-T02
- **Areas:** `deploy/airgap/{images.txt,mirror.sh}`, `docs/07-ops/helm-k8s.md` (install guide sections), `deploy/helm/agentic-runtime/values-small.yaml`
- **Spec:** [deployment-modes §4](../00-overview/deployment-modes.md#4-air-gapped-installs), [helm-k8s](../07-ops/helm-k8s.md)
- **Do:** Image list generation and mirroring script, offline model/embedding server guidance (vLLM/TEI values examples), package mirrors for sandboxes, bootstrap Job for the single tenant, install verification checklist; test install with network egress blocked.
- **Done when:** install with egress denied (NetworkPolicy on the whole cluster) passes smoke tests.
- **Tests:** nightly air-gapped kind install.

### M15-T07 · Release 1.0
- **Depends on:** M15-T03, M15-T04, M15-T05, M15-T06, M7-T10, M1-T16, M3-T09, M3-T10, M5-T08, M5-T09, M7-T11, M13-T07, M14-T08, M14-T09, M14-T10, M14-T11, M14-T12, M14-T13
- **Areas:** `CHANGELOG.md`, `.github/workflows/release.yml`, `README.md`
- **Spec:** [ci-cd §6](../07-ops/ci-cd.md#6-releases-and-upgrades), [AGENTS.md](../../AGENTS.md#definition-of-done)
- **Do:** Release workflow (semver tag → images signed, chart packaged and pushed to OCI registry, SBOMs, release notes from conventional commits), final consistency check of docs vs implementation (`scripts/check_docs.py`), manual release checklist (real Slack/Teams workspace test, real IdP test, DR drill report, security verification log).
- **Done when:** `v1.0.0` tag produces signed artefacts and the checklist is complete.
- **Tests:** release workflow dry-run.
