# Helm and Kubernetes

One umbrella chart `deploy/helm/agentic-runtime` installs every deployable for both deployment modes ([deployment-modes](../00-overview/deployment-modes.md)). Kubernetes ≥ 1.33. Gateway API ingress (Envoy Gateway or any conformant implementation), cert-manager, KEDA, and the CloudNativePG operator are prerequisites when the bundled options are enabled.

## 1. Workloads

| Deployable | Kind | Replicas (small / large) | Probes | Scaling | Notes |
|---|---|---|---|---|---|
| `web` | Deployment | 2 / 4–20 | `/healthz` | HPA CPU 60 % | Stateless |
| `api` | Deployment | 2 / 4–30 | `/healthz` (liveness), `/readyz` (Postgres; Valkey when shared; Temporal when `AR_TEMPORAL_REQUIRED`) | HPA CPU 60 % + RPS | More than one replica requires `process.shared` (Valkey sessions, Postgres idempotency, the run-event bus). Production sandboxes use the kubernetes driver only. |
| `runtime-worker` | Deployment | 2 / 4–50 | `/healthz` on 8012 | KEDA on `ar-runtime` backlog (target 20 per pod) | `AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES` 100 |
| `system-worker` | Deployment | 2 / 2–10 | `/healthz` on 8013 | KEDA on `ar-system` + `ar-eval` | |
| `ingest-worker` | Deployment | 1 / 2–20 | `/healthz` on 8014 | KEDA on `ar-ingest` | 2 CPU / 4 GiB (parsing, OCR) |
| `model-gateway` | Deployment | 2 / 3–20 | `/healthz` | HPA CPU 60 % | |
| `mcp-gateway` | Deployment | 2 / 3–20 | `/healthz` | HPA CPU 60 % | Egress via `squid` |
| `sandbox-manager` | Deployment | 2 / 2–4 | `/healthz` | fixed | Leader election (Lease) for the reaper and warm pool; RBAC limited to sandbox namespaces |
| `channels` | Deployment | 2 / 2–10 | `/healthz` | HPA CPU | Socket-mode connections pinned via Lease per integration |
| `mcp-sql`, `mcp-openapi` | Deployment | 2 / 2–10 | `/healthz` | HPA CPU | |
| `opa` | Deployment | 2 / 3 | `/health?bundles` | fixed | Sidecar-free; bundle from `api` |
| `squid` (egress proxy) | Deployment | 2 / 3–10 | TCP 3128 | HPA CPU | Only path to the internet for sandboxes and tools |
| `fake-llm` | Deployment | dev / CI only | | | Disabled unless `fakeLlm.enabled` |
| `migrate` | Job (post-install/post-upgrade hook) | — | | | `python -m ar_domain.db.schema_gate`: wait until Postgres accepts `ar_owner`, then `alembic upgrade head` under an advisory lock. The same command is the init container on database workloads. |
| `bootstrap` | Job (post-install, single_tenant) | — | | | `python -m ar_domain.bootstrap` |
| Sandboxes | Pods created by sandbox-manager | per run | | warm pool | Namespace `ar-sandboxes` (or `ar-sbx-{tenant_slug}` for dedicated tenants); `runtimeClassName` gVisor/Kata |

Every Python deployable runs the shared `python-service` image, whose entrypoint is `python -m ar_common.serve`. The chart sets `AR_APP_MODULE` and `AR_PORT` per workload (`workloads.<name>.appModule`) for the HTTP services, and overrides `command` with the worker console script (`ar-runtime`, `ar-system`, `ar-ingest`) for the Temporal workers, because only their `main()` starts the poller; the ASGI factory alone serves health probes and nothing else.

All pods: `runAsNonRoot`, UID 10001, `readOnlyRootFilesystem: true` (writable `emptyDir` at `/tmp`), drop ALL capabilities, `seccompProfile: RuntimeDefault`, resource requests/limits from values, topology spread across zones, PodDisruptionBudget `minAvailable: 1` (≥ 2 replicas), automountServiceAccountToken false except sandbox-manager and workers using Kubernetes API.

## 2. Networking

- Gateway API `HTTPRoute`s: `/` → web, `/api/` → api (also `/scim/v2/`, `/api/v1/hooks/`), `/channels/` → channels (Slack/Teams callbacks). TLS via cert-manager.
- NetworkPolicies (default deny per namespace): web and channels → api, plus `gateway.namespace` and `networkPolicy.apiIngress` (a namespace list or labels). There is no match of every namespace. api → Postgres, Valkey, Temporal, Qdrant (only when `qdrant.enabled`), S3, OPA, model-gateway, mcp-gateway, sandbox-manager, OpenBao; workers → same. With `airgap.lockdown` off, `api` and `runtime-worker` also open TCP 443 to any destination, the same rule `mcp-gateway` uses for model calls. With lockdown on, that rule is absent and `airgap.egressCIDRs` is the only allowlist; the render fails when the list is empty and `config.AR_DEV_MODEL_BASE_URL` is outside the cluster. Squid stays the sandbox egress path. Sandboxes → squid + DNS only (no cluster access, no metadata IP).
- Internal mTLS is optional (service mesh); internal JWTs are always required ([authn-authz §8](../06-security/authn-authz.md#8-internal-service-authorisation)).

## 3. Stateful dependencies

Each dependency is either **bundled** (installed by the chart/operator) or **external** (connection settings only). Production recommendation: external managed services where the customer has them.

| Dependency | Bundled option | HA (large) | Backups | External settings |
|---|---|---|---|---|
| Postgres 18 + pgvector | CloudNativePG `Cluster` (3 instances, synchronous replica), PgBouncer pooler (transaction mode; app uses `statement_cache_size=0`). `values-dev` uses a single StatefulSet instead of the operator. Both init paths create `ar_owner` (and `ar_app`, `ar_platform`, `ar_readonly`) and install `vector` and the other extensions as the image superuser before the migrate Job connects. None of those roles is a superuser. `ar_owner` is `LOGIN` and `BYPASSRLS` only and is not a member of the other roles. Alembic logs in as `ar_owner`. `<release>-secrets-hook` is a pre-install,pre-upgrade hook at weight -20. `<release>-secrets` is the release Secret pods mount, with the same bytes. A StatefulSet upgrade then runs `reconcile-roles` at weight -10, as `postgres.superuserUsername`, reading the hook Secret. Migrate is post-install,post-upgrade and reads the release Secret. The init paths also create `ar_temporal`. After the one-time upgrade, point `postgres.superuserUsername` at the image `postgres` role. Every hook Job sets `AR_ENV` from `global.env`. `secrets.create: false` is enforced when the API, Alembic and bootstrap start. CloudNativePG with `secrets.create: false` also fails the render until `postgres.existingRoleSecrets` is true. Passwords are the `AR_DB_*_PASSWORD` keys of the install secret. | yes | Barman to S3: base backup daily, WAL continuous ([backup-dr](backup-dr.md)) | `AR_DATABASE_URL`, `AR_DB_OWNER_PASSWORD`, `AR_DB_APP_PASSWORD`, `AR_DB_PLATFORM_PASSWORD`, `AR_DB_READONLY_PASSWORD`. Separate DBs: `ar` (app), `temporal`, `temporal_visibility`, `keycloak`, `langfuse` |
| Valkey | Primary + replica + Sentinel (or cluster mode via values) | yes | Not backed up (cache/streams; loss tolerated) | `AR_VALKEY_URL` |
| Temporal | In-chart Deployments of `temporalio/server:1.32.1`. `temporal.ha: true` runs frontend, history × `temporal.replicas.history` (default 3), matching and worker. `temporal.ha: false` runs all four services in one pod. Both persist to Postgres (`temporal` and `temporal.visibilityDatabase`) as `ar_temporal`. Schema setup is `temporalio/admin-tools:1.32.1` (`temporal-sql-tool` setup then update), as an init container and as a post-install job. `temporal.numHistoryShards` (default 512) is fixed for the life of the cluster. CloudNativePG dials `<release>-pg-rw` (the primary), not the transaction-mode pooler. Compose still uses `temporal server start-dev` (SQLite). | yes | Via Postgres backups | `AR_TEMPORAL_ADDRESS`, `AR_TEMPORAL_NAMESPACE`, `AR_DB_TEMPORAL_PASSWORD` |
| Qdrant (**optional**, disabled by default) | Subchart `qdrant` (official chart) with `qdrant.enabled: false` by default; when enabled: StatefulSet 3 replicas, replication factor 2. Needed only for the optional qdrant retrieval adapter ([ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md)); the default pgvector adapter keeps knowledge in Postgres | yes | Snapshots to S3 every 6 h; re-indexable from Postgres `document_chunks` | `AR_VECTOR_BACKEND=qdrant`, `AR_QDRANT_URL`, `AR_QDRANT_API_KEY` |
| Object storage | SeaweedFS (master ×3, volume ×3, filer, S3 gateway) | yes | Versioning + replication to DR bucket; audit bucket with Object Lock | `AR_S3_*` |
| Keycloak | 2+ replicas, Infinispan cache, realm import Job | yes | Realm export nightly + Postgres | `AR_OIDC_*` |
| OpenBao | 3-node Raft, auto-unseal via cloud KMS or Transit | yes | Raft snapshots hourly | `AR_VAULT_*` (`AR_SECRETS_BACKEND=vault`) |
| OPA | Stateless | — | — | `AR_OPA_URL` |
| Observability (collector, Prometheus, Tempo, Loki, Grafana, Langfuse) | Optional subchart `observability.enabled` | — | Not backed up beyond retention | `AR_OTEL_EXPORTER_OTLP_ENDPOINT`, `AR_TRACE_UI_URL` |
| ClamAV | Optional Deployment | — | — | `AR_CLAMAV_ADDRESS` |

## 4. Values to environment mapping

`values.yaml` structure (validated by `values.schema.json`):

```yaml
global:
  imageRegistry: registry.example.internal/ar
  imageTag: "1.0.0"            # overridden by digests in release bundles
  deploymentMode: single_tenant # → AR_DEPLOYMENT_MODE
  env: prod                     # → AR_ENV
  publicUrl: https://agents.example.com   # → AR_PUBLIC_URL
config: {}                      # free-form AR_* overrides (ConfigMap), e.g. AR_TRACE_SAMPLE_RATIO: "0.1"
secrets:
  existingSecret: ar-secrets    # keys = AR_* secret variable names
bootstrap: {tenantSlug, tenantName, adminEmail}   # → AR_BOOTSTRAP_*
postgres: {bundled: true, instances: 3, storage: 200Gi, externalUrlSecretKey: AR_DATABASE_URL}
valkey: {bundled: true, mode: sentinel}
temporal: {bundled: true, ha: true, namespace: agentic-runtime, numHistoryShards: 512, database: temporal, visibilityDatabase: temporal_visibility}
retrieval: {backend: pgvector, pgReadDsnSecretKey: "", efSearch: 100}   # → AR_VECTOR_BACKEND, AR_VECTOR_PG_READ_DSN, AR_VECTOR_PG_EF_SEARCH
qdrant: {enabled: false, external: false, url: "", replicas: 3, storage: 200Gi}   # optional subchart; enabled → AR_QDRANT_URL from the subchart service; external → url
objectStorage: {bundled: true, bucket: ar-files, auditBucket: ar-audit-archive}
keycloak: {bundled: true, replicas: 2}
openbao: {bundled: true}
sandboxes: {driver: kubernetes, runtimeClass: gvisor, namespace: ar-sandboxes, warmPool: "default=4,browser=2", nodeSelector: {ar.io/pool: sandbox}, tolerations: [...]}
egress: {packageMirrors: {pypi: "", npm: "", apt: ""}, denyCidrs: [...]}
api: {replicas: 2, resources: {...}, hpa: {...}}
# one block per deployable with replicas, resources, hpa/keda, nodeSelector, extraEnv
observability: {enabled: false}
fakeLlm: {enabled: false}
```

Rule: every `AR_*` variable in [environments §3](environments.md#3-variable-catalogue) is settable via `config` (non-secret) or `secrets.existingSecret` (secret); named values above are conveniences that render the same variables. The chart fails rendering if `deploymentMode=single_tenant` and `bootstrap.adminEmail` is empty, or if `env=prod` with `sandboxes.driver=docker`.

## 5. Sandbox node pool

Dedicated node pool (label `ar.io/pool=sandbox`, taint `ar.io/sandbox=true:NoSchedule`), gVisor RuntimeClass installed by the cluster admin (Kata optional), Falco DaemonSet on that pool, no other workloads scheduled there. ResourceQuota and LimitRange per sandbox namespace from plan limits. Details: [spec 12](../03-specs/12-sandbox-manager.md).

## 6. Upgrades

`helm upgrade --atomic --wait --timeout 20m`. Hook order, for every database shape:

| Shape | Fresh install | Upgrade |
|---|---|---|
| Secret | pre-install `<release>-secrets-hook` at weight -20, then the release Secret is created with the same bytes. The hook copy is deleted when the pre-install phase finishes. | pre-upgrade hook at -20 writes the new bytes. The release Secret is updated after that phase. |
| Roles | StatefulSet init script, or CloudNativePG `postInitSQL` plus managed roles. External Postgres is the operator's job: create `ar_temporal` and the two databases before install. | StatefulSet `reconcile-roles` at pre-upgrade weight -10, as the image superuser, sets every role password including `ar_temporal` and creates the Temporal databases if they are missing. CloudNativePG reconciles managed role secrets itself. Migrate and Temporal retry until the new password is accepted, so it is not used before that reconciliation. |
| Schema | post-install `migrate` and `temporal-schema` wait for the login, then upgrade. Database pods run the same schema gate as an init container, so `--wait` becomes Ready only after the head revision. `/readyz` checks `alembic_version`. | post-upgrade jobs repeat the upgrade. New pods do not start the process until their init container finishes. Rolling update keeps `maxUnavailable: 0`. |
| External Postgres | Same post-install jobs. Set `postgres.host` and, when NetworkPolicy is on, `postgres.externalCidrs`. | Same. There is no in-chart superuser reconcile unless `AR_DB_RECONCILE=run` is pointed at one. |

Workers drain on SIGTERM and finish in-flight activities within `terminationGracePeriodSeconds: 300`. See [ci-cd §6](ci-cd.md#6-releases-and-upgrades) and [OQ-139](../open-questions.md).

Worker probes listen on 8012, 8013 and 8014 ([OQ-21](../open-questions.md)). The web probe is `/healthz`. Model and MCP gateways expose `/healthz` for both liveness and readiness.

## 7. Install

Prerequisites when the bundled options are on: Kubernetes ≥ 1.33, Helm 4.3, the CloudNativePG operator, cert-manager, KEDA and a Gateway API controller. `values-dev.yaml` does not need those operators.

```bash
helm lint deploy/helm/agentic-runtime -f deploy/helm/agentic-runtime/values-small.yaml
helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  --namespace agentic-runtime --create-namespace \
  -f deploy/helm/agentic-runtime/values-small.yaml \
  --atomic --wait --timeout 20m
helm test agentic-runtime -n agentic-runtime
```

SaaS: `-f deploy/helm/agentic-runtime/values-saas.yaml` with `secrets.existingSecret` holding the secret `AR_*` keys. External stateful services: `-f deploy/helm/agentic-runtime/values-external.yaml`. Air-gapped registry: `-f deploy/helm/agentic-runtime/values-small.yaml -f deploy/helm/agentic-runtime/values-airgap.yaml` after `REGISTRY=registry.example.internal/ar deploy/airgap/mirror.sh`.

Offline model servers stay outside the chart. Point aliases at them with config:

```yaml
config:
  AR_DEV_MODEL_BASE_URL: http://vllm.models.svc:8000/v1
```

vLLM `v0.32.0` (`ghcr.io/vllm-project/vllm-openai`) and Hugging Face TEI `1.9.4` are listed in `deploy/airgap/images.txt`. Sandbox package mirrors are `egress.packageMirrors` (`AR_SANDBOX_PACKAGE_MIRRORS`).

`global.maintenance=true` scales the three worker deployments to 0 during a restore. The dev preset (`make kind-up`) installs onto kind without hooks so missing images do not block the API objects.
