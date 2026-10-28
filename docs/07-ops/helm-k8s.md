# Helm and Kubernetes

One umbrella chart `deploy/helm/agentic-runtime` installs every deployable for both deployment modes ([deployment-modes](../00-overview/deployment-modes.md)). Kubernetes ≥ 1.33. Gateway API ingress (Envoy Gateway or any conformant implementation), cert-manager, KEDA, and the CloudNativePG operator are prerequisites when the bundled options are enabled.

## 1. Workloads

| Deployable | Kind | Replicas (small / large) | Probes | Scaling | Notes |
|---|---|---|---|---|---|
| `web` | Deployment | 2 / 4–20 | `/healthz` | HPA CPU 60 % | Stateless |
| `api` | Deployment | 2 / 4–30 | `/healthz` (liveness), `/readyz` (DB, Valkey, Temporal) | HPA CPU 60 % + RPS | Long-lived SSE: `terminationGracePeriodSeconds: 60`, preStop sleep 10 s |
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
| `migrate` | Job (pre-install/pre-upgrade hook) | — | | | `alembic upgrade head`, then OPA bundle warmup |
| `bootstrap` | Job (post-install, single_tenant) | — | | | `python -m ar_domain.bootstrap` |
| Sandboxes | Pods created by sandbox-manager | per run | | warm pool | Namespace `ar-sandboxes` (or `ar-sbx-{tenant_slug}` for dedicated tenants); `runtimeClassName` gVisor/Kata |

All pods: `runAsNonRoot`, UID 10001, `readOnlyRootFilesystem: true` (writable `emptyDir` at `/tmp`), drop ALL capabilities, `seccompProfile: RuntimeDefault`, resource requests/limits from values, topology spread across zones, PodDisruptionBudget `minAvailable: 1` (≥ 2 replicas), automountServiceAccountToken false except sandbox-manager and workers using Kubernetes API.

## 2. Networking

- Gateway API `HTTPRoute`s: `/` → web, `/api/` → api (also `/scim/v2/`, `/api/v1/hooks/`), `/channels/` → channels (Slack/Teams callbacks). TLS via cert-manager.
- NetworkPolicies (default deny per namespace): web → api; api → Postgres, Valkey, Temporal, Qdrant (only when `qdrant.enabled`), S3, Keycloak, OPA, model-gateway, mcp-gateway, sandbox-manager, OpenBao; workers → same + model/mcp gateways; mcp-gateway → squid, mcp-sql, mcp-openapi, internal tool servers (`AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS`); model-gateway → model endpoints (CIDR allowlist from values); sandboxes → squid + DNS only (no cluster access, no metadata IP).
- Internal mTLS is optional (service mesh); internal JWTs are always required ([authn-authz §8](../06-security/authn-authz.md#8-internal-service-authorisation)).

## 3. Stateful dependencies

Each dependency is either **bundled** (installed by the chart/operator) or **external** (connection settings only). Production recommendation: external managed services where the customer has them.

| Dependency | Bundled option | HA (large) | Backups | External settings |
|---|---|---|---|---|
| Postgres 18 + pgvector | CloudNativePG `Cluster` (3 instances, synchronous replica), PgBouncer pooler (transaction mode; app uses `statement_cache_size=0`) | yes | Barman to S3: base backup daily, WAL continuous ([backup-dr](backup-dr.md)) | `AR_DATABASE_URL`, separate DBs: `ar` (app), `temporal`, `temporal_visibility`, `keycloak`, `langfuse` |
| Valkey | Primary + replica + Sentinel (or cluster mode via values) | yes | Not backed up (cache/streams; loss tolerated) | `AR_VALKEY_URL` |
| Temporal | Official Temporal chart (frontend, history ×3, matching, worker), Postgres persistence | yes | Via Postgres backups | `AR_TEMPORAL_ADDRESS`, `AR_TEMPORAL_NAMESPACE` |
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
temporal: {bundled: true, namespace: agentic-runtime}
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

`helm upgrade --atomic --wait --timeout 20m`. Order enforced by hooks: migrate Job → stateless rollouts (maxUnavailable 0, maxSurge 25 %) → workers drain (Temporal workers stop polling on SIGTERM and finish in-flight activities within `terminationGracePeriodSeconds: 300`). See [ci-cd §6](ci-cd.md#6-releases-and-upgrades).

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
