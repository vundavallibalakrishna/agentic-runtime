# Tenancy and isolation model

A **tenant** is a company (Keycloak Organization ↔ `tenants` row). Every tenant-owned record carries `tenant_id`. Isolation is enforced at every layer independently, so that one bug never crosses a tenant boundary on its own ([ADR-0008](adr/ADR-0008-shared-schema-rls.md)).

## 1. Isolation tiers

| Tier (`tenants.isolation_tier`) | Data | Compute | Typical use |
|---|---|---|---|
| `shared` | Shared Postgres schema with RLS; knowledge vectors in the same RLS-protected Postgres (`chunk_embeddings`; with the optional qdrant adapter: shared collections with tenant payload index); shared bucket with prefix `t/{tenant_id}/` | Shared deployables; sandboxes in shared namespace `ar-sandboxes` | SaaS default |
| `dedicated_db` | Own Postgres database (`AR_TENANT_DB_ROUTES`), knowledge vectors in that database (optional qdrant adapter: own collections `ar_kn_t_{tenant_short}_*`), own bucket `ar-t-{slug}`, optional own Transit key | Shared deployables; sandboxes in `ar-sbx-{tenant_slug}` namespace; optional own Temporal namespace (`AR_TENANT_TEMPORAL_NAMESPACES`) | Regulated SaaS customers |
| `dedicated_cluster` | Separate install | Separate install (`AR_DEPLOYMENT_MODE=single_tenant`) | On-prem / private cloud ([deployment-modes](../00-overview/deployment-modes.md)) |

## 2. Enforcement layers

| Layer | Mechanism | Reference |
|---|---|---|
| Identity | Keycloak Organization membership; `tenant` claim verified against the session/token; users belong to exactly one tenant (platform admins may switch via `POST /api/v1/auth/switch-tenant`, audited) | [spec 02](../03-specs/02-identity-tenancy.md) |
| API | `TenantContext` resolved per request from the principal only (never from client headers or body); suspended tenants → 403 `tenant_suspended` | [spec 01](../03-specs/01-api-bff.md) |
| Database | RLS on every tenant table using `app.tenant_id` set with `set_config(..., true)` per transaction; app role `ar_app` has no BYPASSRLS; cross-tenant jobs use `ar_platform` explicitly; fail-closed when unset | [rls.md](../04-data/rls.md) |
| Repositories | Every repository method takes `TenantContext`; queries also filter `tenant_id` explicitly (belt and braces) | [coding-standards-python](../08-quality/coding-standards-python.md) |
| Vector store | Every Qdrant query has a mandatory `tenant_id` must-filter built by one function (`knowledge.retrieval.build_filter`), unit-tested; ACL principals filter in-query | [spec 10 §6](../03-specs/10-knowledge.md#6-retrieval-store-port-retrievalstore) |
| Object storage | Keys `t/{tenant_id}/…`; access only via `files.service` after `can_read`; presigned URLs ≤ 300 s | [spec 13](../03-specs/13-files-artifacts.md) |
| Caches / Valkey | All keys include tenant (`ar:{area}:{tenant_id}:…`) except run/conversation streams keyed by globally unique UUIDv7 ids that are authorised by the API before reading | [stream-events](../05-contracts/stream-events.md) |
| Temporal | Workflow inputs carry `tenant_id`; activities set tenant context before DB access; search attribute `TenantId` for visibility queries | [spec 07](../03-specs/07-agent-runtime.md) |
| Internal calls | Internal JWT carries `tenant_id`; targets never accept tenant from body | [internal-apis](../05-contracts/internal-apis.md) |
| Model gateway | Aliases/models resolved per tenant; usage and quotas per tenant | [spec 04](../03-specs/04-model-gateway.md) |
| Tools | Tool servers are tenant-scoped (platform built-ins excepted); `X-AR-Tenant` header and per-user credentials | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| Sandboxes | Pod per sandbox, no cross-pod networking, per-sandbox token and egress identity; dedicated namespaces for dedicated tiers | [spec 12](../03-specs/12-sandbox-manager.md) |
| Observability | Tenant id on logs/spans; no content; Langfuse access restricted | [spec 18](../03-specs/18-observability-eval.md) |
| Noisy neighbours | Per-tenant rate limits (`api_rpm`), concurrency caps (runs, sandboxes), quotas, provider semaphores, Temporal fairness via per-tenant concurrency limits in the runtime (`AR_RUNTIME_TENANT_MAX_ACTIVE_RUNS`, default plan `max_concurrent_runs`) | [scaling](../07-ops/scaling.md) |

## 3. Within-tenant isolation

- **Users**: conversations, memory (`user`, `agent_user`), credentials, files are private by default; sharing is explicit (`conversation_shares`).
- **On-behalf-of**: every run executes as `runs.user_id`; tools receive that user's identity (OAuth grant, token exchange, internal JWT `sub`); knowledge retrieval filters by that user's principals. Routines run as their owner. Agents never hold standing privileges beyond the user's.
- **Teams**: agents, skills, collections can be team-visible; team leads manage team resources.
- **Classifications**: `public < internal < confidential < restricted` on documents, tools, sandboxes, conversations; users have `attributes.clearance` (default `confidential`).

## 4. Tenant lifecycle

`provisioning → active → suspended ↔ active → deleting (7-day grace) → deleted` via `TenantProvisioningWorkflow` and `TenantDeletionWorkflow` ([spec 02 §4](../03-specs/02-identity-tenancy.md)). Deletion removes rows (FK cascade), vectors (filter delete), objects (prefix delete), Keycloak organization, sandboxes; audit chain exported to the archive bucket first.

## 5. Mandatory isolation tests

1. RLS suite ([rls.md §5](../04-data/rls.md#5-tests-mandatory)).
2. API cross-tenant suite: for every `GET/PATCH/DELETE /api/v1/{resource}/{id}` in the OpenAPI document, a resource created in tenant A is requested with tenant B's session → must be 404 (generated test, `tests/security/test_cross_tenant.py`).
3. Retrieval leak test ([spec 10 §10](../03-specs/10-knowledge.md#10-retrievalstore-conformance-suite)).
4. Sandbox network isolation test ([spec 12 §11](../03-specs/12-sandbox-manager.md#11-test-plan)).
5. Cache key lint: grep-based test that every Valkey key builder in `ar_common.keys` includes `tenant_id` or a globally unique id.
