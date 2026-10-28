# Environments and configuration

## 1. Environments

| Environment | Purpose | Deployment | Data | Models |
|---|---|---|---|---|
| `dev` (local) | Developer laptops | Docker Compose (`make up`) + services via `uv run`/`pnpm dev` ([local-dev](local-dev.md)) | Seed data (`make seed`) | `fake-llm` or a local OpenAI-compatible endpoint |
| `ci` | Pull-request checks | Testcontainers + Temporal test server; `kind` cluster for e2e/Helm ([ci-cd](ci-cd.md)) | Ephemeral | `fake-llm` |
| `staging` | Release candidates, eval gates, load tests | Helm, preset `small` (single-tenant) and `saas` (multi-tenant) | Synthetic tenants; anonymised copies never used | Company staging model endpoints |
| `prod` | Customers | Helm, preset `large` or `saas` ([helm-k8s](helm-k8s.md)) | Real | Company model endpoints |

Promotion: the same image digests move `ci → staging → prod`; only values differ ([ci-cd §6](ci-cd.md#6-releases-and-upgrades)).

## 2. Configuration rules

- All backend configuration is environment variables with prefix `AR_`, loaded by one `pydantic-settings` class per deployable that composes shared fragments from `ar_common.settings` (`DatabaseSettings`, `ValkeySettings`, `TemporalSettings`, `TelemetrySettings`, `S3Settings`, `SecretsSettings`, `InternalAuthSettings`). Unknown `AR_` variables log a warning at startup; missing required variables fail startup with a list of all missing names.
- Secrets (keys, passwords, tokens) come from Kubernetes Secrets (Helm `existingSecret` references) or files (`AR_*_FILE` variant accepted for every secret variable: the value is read from that path).
- Tenant-level behaviour is **not** configured by env vars; it lives in `tenants.settings` ([spec 02](../03-specs/02-identity-tenancy.md)). Env vars are platform/operator knobs.
- The web app reads only `AR_PUBLIC_URL`, `AR_API_INTERNAL_URL` and `NEXT_PUBLIC_*` build-time values ([spec 19](../03-specs/19-web-app.md)).
- Helm maps `values.yaml` keys to these variables ([helm-k8s §4](helm-k8s.md#4-values-to-environment-mapping)); `.env.example` at the repo root lists every variable with its dev default and is checked by CI against this catalogue (`scripts/check_env_catalogue.py`).

## 3. Variable catalogue

Default = value when unset (dev-oriented); `(required)` = startup fails without it in `staging`/`prod`. "Defined in" links to the spec that owns the behaviour.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_API_INTERNAL_URL` | `http://api:8000` | Internal base URL of `api` (used by web server-side and channels) | [spec 16](../03-specs/16-channels.md), [spec 19](../03-specs/19-web-app.md) |
| `AR_ASGI_SERVER` | `uvicorn` | `uvicorn` or `granian` for api/channels/gateways | [stack](../stack.md) |
| `AR_AUDIT_ARCHIVE_BUCKET` | `ar-audit-archive` | Object Lock bucket for audit archives | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_BILLING_CURRENCY` | `INR` | Currency of platform model prices and the default `tenants.billing_currency` | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_BOOTSTRAP_ADMIN_EMAIL` | (required in single_tenant) | First tenant_admin; receives the invitation | [deployment-modes](../00-overview/deployment-modes.md) |
| `AR_BOOTSTRAP_TENANT_NAME` | `Default` | Single-tenant mode: display name of the bootstrap tenant | [deployment-modes](../00-overview/deployment-modes.md) |
| `AR_BOOTSTRAP_TENANT_SLUG` | `default` | Single-tenant mode: slug of the tenant created by the bootstrap Job | [deployment-modes](../00-overview/deployment-modes.md) |
| `AR_CHANNELS_EMAIL_POLL_S` | `60` | IMAP poll interval for email channels | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_PORT` | `8004` | Listen port of `channels` | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_SLACK_UPDATE_INTERVAL_MS` | `1500` | Minimum interval between streamed Slack message edits | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNELS_TEAMS_UPDATE_INTERVAL_MS` | `2000` | Minimum interval between streamed Teams message updates | [spec 16](../03-specs/16-channels.md) |
| `AR_CHANNEL_LINK_TTL_S` | `900` | Lifetime of account-link tokens | [spec 16](../03-specs/16-channels.md) |
| `AR_CLAMAV_ADDRESS` | `clamav:3310` | clamd host:port for malware scanning | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_CONSECUTIVE_TOOL_ERROR_LIMIT` | `8` | Run fails after this many consecutive tool errors | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_CURSOR_SECRET` | (secret) | HMAC for pagination cursors | [spec 01](../03-specs/01-api-bff.md) |
| `AR_DATABASE_URL` | (required) | Read registry | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_DB_ENCRYPTION_ACTIVE_KEY` | `k1` | Active KEK id | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_DB_ENCRYPTION_KEYS` | (secret) | KEKs for `db_encrypted` | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_DEV_MODEL_BASE_URL` | (empty) | Dev only: `make seed` registers this OpenAI-compatible endpoint instead of `fake-llm` | [local-dev](local-dev.md) |
| `AR_DURABLE_STATE` | (empty) | `postgres` binds HTTP state even under pytest; `memory` keeps the process cache. Empty uses Postgres outside pytest | M10 |
| `AR_DEV_MODEL_API_KEY` | (empty) | Dev only: API key for `AR_DEV_MODEL_BASE_URL` | [local-dev](local-dev.md) |
| `AR_DELTA_COALESCE_MS` | `50` | Token delta coalescing window for stream events | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_DEPLOYMENT_MODE` | `single_tenant` | `saas` or `single_tenant` | [spec 01](../03-specs/01-api-bff.md) |
| `AR_EGRESS_DENY_CIDRS` | metadata + RFC1918 + cluster | CIDRs always denied for sandbox/tool egress | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_EGRESS_PROXY_URL` | `http://squid:3128` | For `web.fetch` and remote MCP outside the cluster | [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 10](../03-specs/10-knowledge.md) |
| `AR_ENV` | `dev` | `dev`, `ci`, `staging`, `prod`; dev-only features (Docker sandbox driver, API docs UI, fake-llm provider) are refused when `prod` | [local-dev](local-dev.md) |
| `AR_EVAL_CONCURRENCY` | `4` | Parallel cases per eval run | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_FASTEMBED_CACHE_DIR` | `/var/cache/fastembed` | BM25 model cache for the optional qdrant adapter (pre-baked in image for air-gapped) | [spec 10](../03-specs/10-knowledge.md) |
| `AR_FILES_PROXY_DOWNLOADS` | `false` | Stream downloads through `api` instead of presigned URLs | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_FILES_SCANNER` | `clamav` (prod) / `none` (dev) | `clamav` or `none` | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_GUARDRAIL_INPUT_ALIAS` | `fast` | Model alias for the input safety classifier (empty disables) | [prompt-injection §4](../06-security/prompt-injection.md) |
| `AR_GUARDRAIL_OUTPUT_ALIAS` | `fast` | Model alias for the output safety classifier (empty disables) | [prompt-injection §4](../06-security/prompt-injection.md) |
| `AR_INGEST_ACTIVITY_CONCURRENCY` | `32` | Per worker | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INGEST_MAX_BYTES` | `209715200` | Maximum size of a single ingested document | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INGEST_SYNC_CONCURRENCY` | `16` | Child workflows per sync | [spec 10](../03-specs/10-knowledge.md) |
| `AR_INJECTION_CLASSIFIER_TIMEOUT_MS` | `1000` | Timeout for the tool-result injection classifier (fail-open with flag) | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_INPUT_WAIT_TIMEOUT_S` | `1800` | Elicitation wait | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_INTERNAL_JWT_JWKS` | `http://api:8000/internal/v1/.well-known/jwks.json` | JWKS URL or inline JSON for verifying internal JWTs | [internal-apis](../05-contracts/internal-apis.md) |
| `AR_INTERNAL_JWT_PRIVATE_KEY` | (required) | Ed25519 PEM for signing internal service JWTs; mounted Secret | [authn-authz §8](../06-security/authn-authz.md) |
| `AR_KNOWLEDGE_RERANK_CANDIDATES` | `50` | Candidates passed to the reranker | [spec 10](../03-specs/10-knowledge.md) |
| `AR_LOG_HASH_USER_IDS` | `false` (`true` in saas) | Hash user ids in logs and Langfuse | [data-protection](../06-security/data-protection.md) |
| `AR_MAX_DEPTH` | `3` | Platform cap for subagents | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MAX_JSON_BODY_BYTES` | `1048576` | Maximum JSON request body | [spec 01](../03-specs/01-api-bff.md) |
| `AR_MAX_MESSAGE_CHARS` | `100000` | Maximum user message length | [spec 06](../03-specs/06-conversations-runs.md) |
| `AR_MCPG_PORT` | `8002` | Listen port of `mcp-gateway` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MCP_GATEWAY_URL` | `http://localhost:8002` | Internal URL of `mcp-gateway` | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS` | cluster CIDRs | CIDRs `internal_http` tool servers may resolve to | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MCP_OPENAPI_URL` | `http://mcp-openapi:8011/mcp` | Internal URL of `mcp-openapi` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MCP_SQL_URL` | `http://mcp-sql:8010/mcp` | Internal URL of `mcp-sql` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_MEMORY_DEDUPE_SIM` | `0.92` | Cosine similarity above which facts are merged | [spec 11](../03-specs/11-memory.md) |
| `AR_MEMORY_RECALL_MIN_SIM` | `0.25` | Minimum similarity for memory recall | [spec 11](../03-specs/11-memory.md) |
| `AR_MG_CB_FAILURES` | `5` | Consecutive failures to open | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_CB_OPEN_S` | `30` | Circuit-breaker open duration | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_HEALTH_INTERVAL_S` | `30` | Provider health probe interval | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_MAX_FALLBACKS` | `2` | Maximum fallback hops per request | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_PORT` | `8001` | Listen port of `model-gateway` | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MG_SEMAPHORE_WAIT_S` | `10` | Max wait for a concurrency slot before 429 | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_MODEL_GATEWAY_URL` | `http://localhost:8001` | Internal URL of `model-gateway` | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_MODEL_PROVIDER_DENY_CIDRS` | RFC1918 + link-local + cluster CIDRs (SaaS) | SSRF guard for tenant providers | [spec 04](../03-specs/04-model-gateway.md) |
| `AR_OFFLINE_SESSION_MAX_DAYS` | `60` | Must match Keycloak realm offline session max | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_OIDC_API_AUDIENCE` | `ar-api` | Audience for bearer tokens | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_CLIENT_ID` | `ar-web` | BFF confidential client | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_CLIENT_SECRET` | (secret) | Confidential client secret of `ar-web` | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OIDC_ISSUER` | `http://localhost:8180/realms/agentic-runtime` | Keycloak realm issuer | [spec 01](../03-specs/01-api-bff.md) |
| `AR_OPA_BUNDLE_TOKEN` | secret | Bearer token OPA uses to fetch policy bundles from `api` | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OPA_TIMEOUT_MS` | `200` | Policy decision timeout (fail closed) | [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OPA_URL` | `http://opa:8181` | OPA decision API URL | [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP gRPC endpoint of the collector | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_OUTBOX_BATCH_SIZE` | `500` | Rows per outbox relay batch | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_PGVECTOR_DIMENSIONS` | `1024` (memory and tool-search embeddings only; knowledge supports 384/768/1024/1536/3072, [spec 10 §7.1](../03-specs/10-knowledge.md#71-storage); fixed; changing requires a migration and re-embed job `scripts/reembed_memory.py`) |  | [spec 11](../03-specs/11-memory.md) |
| `AR_PUBLIC_URL` | `http://localhost:3000` | Origin of the web app (cookies, CSRF origin check, redirects) | [spec 01](../03-specs/01-api-bff.md), [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 16](../03-specs/16-channels.md), [spec 19](../03-specs/19-web-app.md) |
| `AR_QDRANT_API_KEY` | (secret, unset) | Qdrant API key; only with the optional qdrant adapter | [spec 10](../03-specs/10-knowledge.md) |
| `AR_QDRANT_URL` | (unset) | Qdrant URL; required only when `AR_VECTOR_BACKEND=qdrant` or a collection uses the qdrant adapter (local `qdrant` profile: `http://localhost:6333`) | [spec 10](../03-specs/10-knowledge.md) |
| `AR_RETENTION_SWEEP_CRON` | `0 1 * * *` | Schedule of `RetentionSweepWorkflow` | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_ROUTINE_MIN_INTERVAL_S` | `300` | Minimum schedule interval for routines | [spec 15](../03-specs/15-routines-triggers.md) |
| `AR_RUNTIME_MAX_CONCURRENT_ACTIVITIES` | `200` | Per worker process | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_RUNTIME_MAX_CONCURRENT_WORKFLOW_TASKS` | `100` | Temporal worker workflow-task slots | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_RUNTIME_TENANT_MAX_ACTIVE_RUNS` | `50` (plan `max_concurrent_runs` takes precedence when lower) | Per-tenant cap of concurrently executing runs (excess runs stay `queued`) | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_RUN_STREAM_TTL_S` | `86400` | TTL of Valkey run event streams | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_S3_ACCESS_KEY_ID` | (empty → IRSA/instance role) | Object store credentials | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_BUCKET` | `ar-files` | Bucket for files and artifacts | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_ENDPOINT` | `http://localhost:8333` | Internal endpoint | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_PRESIGN_TTL_S` | `300` | Presigned URL lifetime | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_PUBLIC_ENDPOINT` | `http://localhost:8333` | Browser-reachable endpoint for presigned URLs | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_REGION` | `us-east-1` | Object store region | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_SECRET_ACCESS_KEY` | (empty → IRSA/instance role) | Object store credentials | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_S3_SSE` | `AES256` | `none` to disable | [spec 13](../03-specs/13-files-artifacts.md) |
| `AR_SAAS_SELF_SIGNUP` | `false` | Enables public `POST /api/v1/signup` (saas only) | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_SANDBOX_ALLOWED_REGISTRIES` | `registry.local/ar` | Registries sandbox template images may come from | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DEFAULT_RUNTIME_CLASS` | `gvisor` | Kubernetes RuntimeClass for sandboxes | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DOCKER_RUNTIME` | `runc` | `runsc` if installed | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_DRIVER` | `docker` (dev) / `kubernetes` | `docker` (dev only) or `kubernetes` | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_ENSURE_TIMEOUT_S` | `30` | Max time to obtain a ready sandbox | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_MANAGER_URL` | `http://sandbox-manager:8003` | Internal URL of `sandbox-manager` | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_SANDBOX_MAX_PER_TENANT` | plan `max_concurrent_sandboxes` (default 50) | Hard cap of concurrent sandboxes per tenant | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_NAMESPACE` | `ar-sandboxes` | Namespace for sandbox pods (shared tier) | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_PACKAGE_MIRRORS` | empty | JSON `{pypi,npm,apt}` mirror URLs | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_SNAPSHOT_INTERVAL_S` | `600` | Periodic workspace snapshot interval while active | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SANDBOX_WARM_POOL` | `default=4,browser=2` | Warm pods per template | [spec 12](../03-specs/12-sandbox-manager.md) |
| `AR_SEARCH_API_KEY` | (empty) | Key for the configured web search provider. Never logged or returned | [M21b](../09-plan/M21b-general-tools.md) |
| `AR_SEARCH_PROVIDER` | `none` | `none`, `brave` or `tavily`. Empty results until a provider answers | [M21b](../09-plan/M21b-general-tools.md) |
| `AR_SECRETS_BACKEND` | `db_encrypted` (local) / `vault` (prod) | Backend selection | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_SECRET_CACHE_TTL_S` | `60` | In-process cache | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_SESSION_ENCRYPTION_KEY` | (secret, 32 bytes b64) | Encrypt tokens stored in sessions | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SESSION_ENCRYPTION_KEY_PREVIOUS` | (empty) | Previous session key accepted for decryption during rotation | [secrets](../06-security/secrets.md) |
| `AR_SESSION_MAX_AGE_S` | `604800` | Absolute session max | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SESSION_TTL_S` | `43200` | Sliding session TTL | [spec 01](../03-specs/01-api-bff.md) |
| `AR_SMTP_FROM` | `Agentic Runtime <no-reply@localhost>` | Sender address | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_HOST` | `localhost` | SMTP host (Mailpit in dev) | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_PASSWORD` | (empty) | SMTP auth password (Secret) | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_PORT` | `1025` | SMTP port | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_STARTTLS` | `false` (dev) | Use STARTTLS | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SMTP_USERNAME` | (empty) | SMTP auth user | [spec 20](../03-specs/20-notifications-events.md) |
| `AR_SSE_MAX_PER_USER` | `20` | Concurrent SSE streams per user | [spec 01](../03-specs/01-api-bff.md) |
| `AR_STEP_UP_TTL_S` | `600` | Step-up validity | [spec 01](../03-specs/01-api-bff.md), [spec 09](../03-specs/09-policy-approvals.md) |
| `AR_TEMPORAL_ADDRESS` | `localhost:7233` | Temporal frontend host:port | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_TEMPORAL_NAMESPACE` | `agentic-runtime` | One namespace per environment; dedicated tenants may get their own (`AR_TENANT_TEMPORAL_NAMESPACES`) | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_TENANT_DB_ROUTES` | `{}` | JSON map `tenant_id → database URL` for `dedicated_db` tenants | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_TENANT_DELETE_GRACE_DAYS` | `7` | Grace period before tenant data deletion | [spec 02](../03-specs/02-identity-tenancy.md) |
| `AR_TENANT_TEMPORAL_NAMESPACES` | `{}` | JSON map `tenant_id → Temporal namespace` for dedicated tenants | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| `AR_TOKEN_CACHE_KEY` | (secret) | Encrypts cached access tokens in Valkey | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_TOOL_DRIFT_INTERVAL` | `1h` | Tool manifest drift check interval | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_TOOL_RESULT_MAX_FILE_BYTES` | `20971520` | 20 MiB | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| `AR_TRACE_SAMPLE_RATIO` | `0.1` | Head sampling ratio (errors kept by tail sampling) | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_TRACE_UI_URL` | `http://localhost:3001` | Base URL used to build `trace_url` links to the trace UI | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_USAGE_ROLLUP_INTERVAL` | `15m` | `usage_daily` rollup interval | [spec 17](../03-specs/17-audit-usage-metering.md) |
| `AR_VALKEY_URL` | (required) | Caches, semaphores, circuit state, quota counters | [spec 04](../03-specs/04-model-gateway.md), [spec 16](../03-specs/16-channels.md) |
| `AR_VAULT_ADDR` | `http://localhost:8200` | OpenBao/Vault address | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_AUTH` | `kubernetes` | `kubernetes` or `token` | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_KV_MOUNT` | `ar` | KV v2 mount | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_ROLE` | `ar-{service}` | Kubernetes auth role | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VAULT_TOKEN` | (dev) | Token auth | [spec 03](../03-specs/03-secrets-credentials.md) |
| `AR_VECTOR_BACKEND` | `pgvector` | Retrieval backend for new knowledge collections and migration target: `pgvector` \| `qdrant` | [spec 10](../03-specs/10-knowledge.md#11-configuration), [ADR-0009](../02-architecture/adr/ADR-0009-retrieval-stores.md) |
| `AR_VECTOR_MIGRATION_RETAIN_HOURS` | `24` | Rollback window after a retrieval backend switch | [spec 10](../03-specs/10-knowledge.md#9-migrating-between-backends) |
| `AR_VECTOR_PG_EF_SEARCH` | `100` | `hnsw.ef_search` for knowledge searches on pgvector | [spec 10](../03-specs/10-knowledge.md#73-hybrid-query-one-sql-statement-per-search) |
| `AR_VECTOR_PG_READ_DSN` | (unset) | Optional read-replica DSN for knowledge searches on pgvector | [spec 10](../03-specs/10-knowledge.md#11-configuration), [scaling](scaling.md) |
| `AR_WEBHOOK_ALLOW_PRIVATE` | `false` | Allow webhook targets in private ranges (dev only) | [spec 20](../03-specs/20-notifications-events.md) |

### 3.1 Variables added for records, grounding and packs

These names are part of the catalogue. The task that implements each one adds it to `ar_common.settings` and `.env.example` in the same change. They are not required for M1.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_BINDER_MAX_ITEMS` | `5000` | Maximum records in one binder selection | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_BUCKET` | `ar-evidence` | Object Lock bucket for evidence bytes | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_DEFAULT_LOCK_DAYS` | `2555` | Object Lock retain-until offset | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_LOCK_MODE` | `compliance` | `compliance` or `governance` | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_SIGNING_KEY` | (secret) | Ed25519 PEM for evidence and run-record manifests | [spec 21](../03-specs/21-records-governance.md) |
| `AR_EVIDENCE_SIGNING_KEY_ID` | `evidence-k1` | `signature_key_id` written on new items | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GROUNDING_MAX_SENTENCES` | `200` | Claim cap per answer | [spec 07](../03-specs/07-agent-runtime.md) |
| `AR_GRC_CONNECTOR_MAX_PAGES` | `50` | Page cap for one GRC connector collection | [GRC connectors](../10-grc-pack/connectors.md) |
| `AR_GRC_PACK_ENABLED` | `false` | When false, the GRC pack is not installed for the dev tenant and stays out of the default workspace. The package remains on disk. | [M21](../09-plan/M21-agentic-workspace.md) |
| `AR_GUEST_MAGIC_LINK_TTL_S` | `900` | Guest magic-link lifetime | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GUEST_MAX_TTL_DAYS` | `90` | Longest guest principal lifetime | [spec 21](../03-specs/21-records-governance.md) |
| `AR_GUEST_SESSION_TTL_S` | `28800` | Guest session TTL | [spec 21](../03-specs/21-records-governance.md) |
| `AR_PACK_SIGNATURE_REQUIRED` | `true` (`false` when `AR_ENV=dev`) | Reject unsigned content packs | [spec 05](../03-specs/05-agent-registry.md) |
| `AR_PACK_TRUSTED_KEYS` | (secret JSON) | `{key_id, public_key_pem}` entries | [spec 05](../03-specs/05-agent-registry.md) |
| `AR_PACKS_DIR` | `packs` | Directory scanned for pack packages | [spec 21](../03-specs/21-records-governance.md) |
| `AR_RUN_RECORD_MAX_BLOB_BYTES` | `52428800` | Max encrypted tool I/O stored with a run record | [spec 18](../03-specs/18-observability-eval.md) |
| `AR_TSA_TIMEOUT_MS` | `2000` | RFC 3161 call timeout | [spec 21](../03-specs/21-records-governance.md) |
| `AR_TSA_URL` | empty | Platform TSA used when a tenant enables timestamping without its own URL | [spec 21](../03-specs/21-records-governance.md) |

### 3.2 Required versus defaulted

A deployment starts once secrets and identity exist. Every other variable in §3 and §3.1 has a default and must not be set for a normal tenant.

Required in `staging` and `prod` (startup fails when missing):

| Variable | Why it cannot be guessed |
|---|---|
| `AR_DATABASE_URL` | The database |
| `AR_VALKEY_URL` | The cache |
| `AR_INTERNAL_JWT_PRIVATE_KEY` | Service identity |
| `AR_OIDC_CLIENT_SECRET` | Login to the identity provider |
| `AR_SESSION_ENCRYPTION_KEY` | Session cookie contents |

`AR_OIDC_ISSUER` and `AR_OIDC_CLIENT_ID` have defaults for local dev. Production sets them to the customer's issuer; they are identity, not product behaviour.

Everything else, including evidence, guests, packs and grounding, runs on the default in the catalogue. Tenant behaviour lives in `tenants.settings` with the defaults in the owning spec. Settings screens use Simple and Advanced modes ([spec 19 §12](../03-specs/19-web-app.md#12-simple-and-advanced-settings)).

### 3.3 Local host ports

These are laptop publish ports. They are not set in Helm. `make ports-check` copies a non-default value into the localhost URL named in [local-dev](local-dev.md#5-host-ports). `AR_MG_PORT`, `AR_MCPG_PORT`, `AR_CHANNELS_PORT` and `AR_SMTP_PORT` are already in §3 and are the host ports for those processes.

| Variable | Default | Description | Defined in |
|---|---|---|---|
| `AR_CLICKHOUSE_HOST_PORT` | `8123` | Host port for ClickHouse HTTP | [local-dev](local-dev.md#5-host-ports) |
| `AR_CLAMAV_HOST_PORT` | `3310` | Host port for clamd. Updates `AR_CLAMAV_ADDRESS` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_EGRESS_HOST_PORT` | `3128` | Host port for Squid. Updates `AR_EGRESS_PROXY_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_FAKE_LLM_HOST_PORT` | `8099` | Host port for fake-llm. `FAKE_LLM_PORT` is still accepted | [local-dev](local-dev.md#5-host-ports) |
| `AR_GRAFANA_HOST_PORT` | `3001` | Host port for Grafana. Updates `AR_TRACE_UI_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_INGEST_HOST_PORT` | `8014` | Host port for ingest-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_KEYCLOAK_HOST_PORT` | `8180` | Host port for Keycloak. Updates `AR_OIDC_ISSUER` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_LANGFUSE_HOST_PORT` | `3100` | Host port for Langfuse | [local-dev](local-dev.md#5-host-ports) |
| `AR_MAILPIT_UI_HOST_PORT` | `8025` | Host port for the Mailpit UI | [local-dev](local-dev.md#5-host-ports) |
| `AR_MCP_OPENAPI_HOST_PORT` | `8011` | Host port for mcp-openapi | [local-dev](local-dev.md#5-host-ports) |
| `AR_MCP_SQL_HOST_PORT` | `8010` | Host port for mcp-sql | [local-dev](local-dev.md#5-host-ports) |
| `AR_OPA_HOST_PORT` | `8181` | Host port for OPA. Updates `AR_OPA_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_OTEL_GRPC_HOST_PORT` | `4317` | Host port for OTLP gRPC. Updates `AR_OTEL_EXPORTER_OTLP_ENDPOINT` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_OTEL_HTTP_HOST_PORT` | `4318` | Host port for OTLP HTTP | [local-dev](local-dev.md#5-host-ports) |
| `AR_PG_HOST_PORT` | `5432` | Host port for Postgres. Updates `AR_DATABASE_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_PORT` | `8000` | API listen port and host port. Updates `AR_API_INTERNAL_URL` and `API_PROXY_URL` | [local-dev](local-dev.md#5-host-ports) |
| `AR_PROMETHEUS_HOST_PORT` | `9090` | Host port for Prometheus | [local-dev](local-dev.md#5-host-ports) |
| `AR_QDRANT_GRPC_HOST_PORT` | `6334` | Host port for Qdrant gRPC | [local-dev](local-dev.md#5-host-ports) |
| `AR_QDRANT_HTTP_HOST_PORT` | `6333` | Host port for Qdrant HTTP. Updates `AR_QDRANT_URL` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_RUNTIME_HOST_PORT` | `8012` | Host port for runtime-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_S3_HOST_PORT` | `8333` | Host port for SeaweedFS S3. Updates `AR_S3_ENDPOINT` and `AR_S3_PUBLIC_ENDPOINT` | [local-dev](local-dev.md#5-host-ports) |
| `AR_SANDBOX_AGENT_HOST_PORT` | `8080` | Host port for sandbox-agent | [local-dev](local-dev.md#5-host-ports) |
| `AR_SANDBOX_MANAGER_HOST_PORT` | `8003` | Host port for sandbox-manager | [local-dev](local-dev.md#5-host-ports) |
| `AR_SYSTEM_HOST_PORT` | `8013` | Host port for system-worker health | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPO_HOST_PORT` | `3200` | Host port for Tempo | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPORAL_HOST_PORT` | `7233` | Host port for Temporal gRPC. Updates `AR_TEMPORAL_ADDRESS` | [local-dev](local-dev.md#5-host-ports) |
| `AR_TEMPORAL_UI_HOST_PORT` | `8233` | Host port for the Temporal UI | [local-dev](local-dev.md#5-host-ports) |
| `AR_VALKEY_HOST_PORT` | `6379` | Host port for Valkey. Updates `AR_VALKEY_URL` | [local-dev](local-dev.md#5-host-ports) |
| `AR_VAULT_HOST_PORT` | `8200` | Host port for OpenBao. Updates `AR_VAULT_ADDR` on localhost | [local-dev](local-dev.md#5-host-ports) |
| `AR_WEB_HOST_PORT` | `3000` | Host port for the web app. Updates `AR_PUBLIC_URL` | [local-dev](local-dev.md#5-host-ports) |

## 4. Mirrors and air-gapped installs

| What | Variable / value | Notes |
|---|---|---|
| Container images | Helm `global.imageRegistry` | All images (ours and dependencies) pulled from the customer registry; `make images-bundle` produces a tarball + manifest |
| Sandbox images | `AR_SANDBOX_ALLOWED_REGISTRIES` | Only these registries are accepted for templates |
| Package mirrors in sandboxes | `AR_SANDBOX_PACKAGE_MIRRORS` | JSON `{pypi, npm, apt}` URLs written into the sandbox (`pip.conf`, `.npmrc`, apt sources) |
| BM25 model for the optional qdrant adapter | `AR_FASTEMBED_CACHE_DIR` | Pre-baked in the image or a pre-populated volume; no downloads at runtime when `AR_ENV=prod`; unused with the default pgvector adapter |
| Python/Node build deps | `UV_INDEX_URL`, `npm_config_registry` (build-time) | Used by Dockerfiles and CI only |
