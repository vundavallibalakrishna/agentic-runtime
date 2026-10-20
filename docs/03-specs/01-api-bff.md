# Spec 01: `api` service (public API, BFF, cross-cutting HTTP concerns)

Deployable: `api` (`services/api`, package `ar_api`). Hosts the routers of every domain module (each module's endpoints are specified in its own spec) plus the cross-cutting concerns defined here: authentication/session (BFF), CSRF, tenancy context, RBAC enforcement, errors, pagination, idempotency, rate limiting, SSE plumbing, OpenAPI, health. Conventions: [api-conventions.md](../05-contracts/api-conventions.md).

## 1. Responsibilities

1. OIDC login for the web app as a confidential client (authorization code + PKCE) against Keycloak; server-side sessions in Valkey; session cookie `ar_session`.
2. Authenticate every request (session, bearer JWT, API key, SCIM token, webhook HMAC) into a `Principal`; build `RequestContext` (tenant, principal, permissions, request id, trace).
3. Enforce RBAC via route dependencies `require(permission)`; resource-level checks in services.
4. Open a tenant-scoped DB session per request (`tenant_session(ctx)`), commit/rollback.
5. Problem-details error mapping; request validation; response serialisation.
6. Idempotency-Key handling, rate limits, request size limits (JSON bodies ≤ 1 MiB except definitions ≤ 2 MiB).
7. SSE endpoints (run and conversation streams; notifications stream).
8. Start Temporal workflows on behalf of domain services (via `ar_domain.temporal.client`).
9. Serve the OPA bundle, JWKS, internal endpoints for `channels`.
10. Generate and serve OpenAPI (`/api/v1/openapi.json`, docs UI at `/api/docs` only when `AR_ENV != prod`).

## 2. Internal structure

```text
services/api/src/ar_api/
  main.py              # create_app(): middleware, routers, lifespan (DB engine, Valkey, Temporal client, OTel)
  deps.py              # get_ctx, require(perm), get_session, pagination params, idempotency
  auth/                # oidc.py (BFF flow), session.py, csrf.py, api_keys.py, bearer.py, scim_auth.py, webhook_sig.py
  middleware/          # request_id.py, ratelimit.py, body_limit.py, errors.py, security_headers.py
  routers/             # one module per domain: identity.py, agents.py, conversations.py, runs.py, tools.py, ...
  sse.py               # stream helpers (Valkey XREAD → SSE)
  internal/            # /internal/v1 routers (opa bundle, jwks, channels, connectors)
  openapi.py           # ERROR_RESPONSES, operation id generator
```

## 3. Authentication endpoints (BFF)

All under `/api/v1/auth`. No authentication required unless stated.

#### GET /api/v1/auth/login
Query: `return_to` (relative path, default `/chat`; absolute URLs rejected), `tenant` (optional slug hint), `idp` (optional `keycloak_alias` for IdP hint). Behaviour: creates a login state in Valkey (`ar:login:{state}` TTL 10 min: `{code_verifier, nonce, return_to, tenant_hint}`), redirects (302) to Keycloak authorize endpoint with `scope=openid profile email offline_access organization`, PKCE S256, `kc_idp_hint` if `idp`, and `organization` hint if `tenant`.

#### GET /api/v1/auth/callback
Query: `code`, `state`. Exchanges code, validates ID token (issuer, audience, nonce, `exp`), reads `organization` claim (Keycloak Organizations) to resolve the tenant (`find_tenant_for_login`). If the user belongs to several organizations and no hint was given → redirect to `/select-tenant`. Upserts `users` (JIT provisioning; status must not be `suspended`/`deprovisioned`), syncs groups from the `groups` claim when the tenant has no SCIM (source `idp_claim`), stores the offline refresh token as the user's delegation token ([spec 03](03-secrets-credentials.md) §5). Creates session `ar:sess:{sid}` (TTL = `AR_SESSION_TTL_S`, default 12 h sliding, absolute max 7 days): `{tenant_id, user_id, access_token (encrypted), refresh_token (encrypted), csrf_token, created_at, last_seen_at, ip_hash, ua_hash}`. Sets cookies `ar_session=<sid>` (HttpOnly, Secure, SameSite=Lax) and `ar_csrf=<csrf_token>` (not HttpOnly, SameSite=Strict). Audits `auth.login`. Redirects to `return_to`.
Errors (rendered as redirect to `/login?error=<code>`): `invalid_state`, `tenant_not_found`, `user_suspended`, `tenant_suspended`.

#### POST /api/v1/auth/logout
Auth: session. Deletes the session, revokes the Keycloak refresh token (RP-initiated logout back-channel), clears cookies, returns `{logout_url}` (Keycloak end-session URL) for the browser to visit. Audits `auth.logout`.

#### GET /api/v1/auth/session
Auth: session or bearer. Response `SessionInfo`:
```json
{"user": {"id":"...","email":"...","display_name":"...","locale":"en-IN","timezone":"Asia/Kolkata"},
 "tenant": {"id":"...","slug":"talentfino","name":"TalentFino","plan":"enterprise","deployment_mode":"saas"},
 "permissions": ["chat:use","agents:read", "..."], "roles": ["member","builder"],
 "memberships": [{"tenant_id":"...","slug":"...","name":"..."}],
 "csrf_token": "...", "features": {"custom_rego": false, "teams_channel": true}}
```

#### POST /api/v1/auth/switch-tenant
Auth: session. Body `{tenant_id}`. Requires that the Keycloak user is a member of that organization, or (SaaS, realm role `platform_admin`) that an active `support_access_grants` row exists for that tenant and operator ([spec 02 §3.11](02-identity-tenancy.md#311-support-access-saas-mode-only)), else 403 `forbidden`; re-runs login silently (`prompt=none`) for the new organization; returns `{redirect_url}`.

#### POST /api/v1/auth/step-up
Auth: session. Body `{return_to}`. Returns `{redirect_url}` to Keycloak with `acr_values=mfa` and `max_age=0`. On callback with `acr=mfa`, the session gets `step_up_at` (valid 10 min, `AR_STEP_UP_TTL_S`). Used by W3 approvals.

#### GET /api/v1/.well-known/jwks.json
Public JWKS for `internal_jwt`-mode tool servers outside the cluster ([mcp-integration](../05-contracts/mcp-integration.md) §4.5).

## 4. Request pipeline (middleware order)

1. `request_id` (accept/generate `X-Request-Id`), OTel server span.
2. `security_headers`: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Cross-Origin-Resource-Policy: same-origin`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (API responses only).
3. `body_limit`.
4. `authenticate` → `Principal | None` (no principal on public routes).
5. `tenant_guard`: tenant `status='active'` (else 403 `tenant_suspended`; platform admins exempt on `/api/v1/platform/*`).
6. `csrf`: for session-authenticated unsafe methods, `X-CSRF-Token` must equal the session's csrf token (constant-time compare); also `Origin` header must equal `AR_PUBLIC_URL` origin.
7. `ratelimit`.
8. Router → dependency `require(...)` → service.
9. `errors` maps `ArError` subclasses to problem+json; unknown exceptions → 500 `internal_error` with request id.

## 5. Principal resolution

| Credential | Resolution |
|---|---|
| `ar_session` | Valkey lookup; refresh Keycloak access token when < 60 s to expiry (refresh token rotation); if refresh fails → 401 and session deleted. |
| Bearer JWT (`eyJ...`) | Verify against Keycloak JWKS (cached 10 min), `aud` contains `ar-api`, map `sub` + `organization` → user. |
| `ark_...` | Prefix lookup (`find_api_key_by_prefix`), constant-time hash compare, not revoked/expired; principal = service account or the owning user; effective permissions = principal permissions ∩ key scopes (if non-empty). Updates `last_used_at` at most once per minute. |
| `scim_...` | Only on `/scim/v2/*`. |

Permissions are computed by `identity.service.effective_permissions(principal)` = union of permissions of roles assigned to the user directly, via groups, and via teams (team-scoped assignments add permissions only for resources owned by that team). Cached in Valkey `ar:perms:{tenant_id}:{principal_id}` for 60 s and invalidated on role/membership changes.

## 6. Health and meta endpoints

#### GET /healthz
Liveness: 200 `{"status":"ok"}` if the process is up.

#### GET /readyz
Readiness: checks Postgres (`SELECT 1`), Valkey `PING`, Temporal `GetSystemInfo` (cached 10 s). 503 with details if any fails.

#### GET /metrics
Prometheus exposition (not routed by public ingress).

#### GET /api/v1/meta
Public. `{"version": "1.4.2", "deployment_mode": "saas|single_tenant", "features": {...}, "oidc": {"login_url": "/api/v1/auth/login"}}`.

#### GET /api/v1/openapi.json
Auth: any signed-in principal (public when `AR_ENV != prod`). The OpenAPI 3.1 document generated by FastAPI; also committed to the repo by `make gen`.

#### GET /api/v1/schemas/{kind}
Auth: any. Returns the JSON Schema for a definition kind (`Agent`, `ToolServer`, `DataConnection`, `KnowledgeCollection`, `Routine`, `Policy`, `Skill`, `ModelAlias`, `SandboxTemplate`, `ChannelIntegration`, `Bundle`). Used by the web YAML editor.

## 7. SSE plumbing (`ar_api.sse`)

- `stream_run(run_id, after_seq)`: authorise (caller can view the run's conversation, or is the run's user, or has `conversations:read_all`), replay from Valkey `XRANGE ar:run:{id}:events (after_seq` … then `XREAD BLOCK 15000`; fallback to `run_events` table if the Valkey stream is missing; close after terminal event.
- Response headers: `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`, `Connection: keep-alive`.
- Max concurrent SSE connections per user: 20 (`AR_SSE_MAX_PER_USER`); excess → 429.
- Each SSE connection holds no DB session while waiting.

## 8. Configuration (env vars, all `AR_` prefixed; full catalogue in [environments.md](../07-ops/environments.md))

| Variable | Default | Purpose |
|---|---|---|
| `AR_PUBLIC_URL` | `http://localhost:3000` | Origin of the web app (cookies, CSRF origin check, redirects) |
| `AR_OIDC_ISSUER` | `http://localhost:8180/realms/agentic-runtime` | Keycloak realm issuer |
| `AR_OIDC_CLIENT_ID` | `ar-web` | BFF confidential client |
| `AR_OIDC_CLIENT_SECRET` | (secret) | |
| `AR_OIDC_API_AUDIENCE` | `ar-api` | Audience for bearer tokens |
| `AR_SESSION_TTL_S` | `43200` | Sliding session TTL |
| `AR_SESSION_MAX_AGE_S` | `604800` | Absolute session max |
| `AR_SESSION_ENCRYPTION_KEY` | (secret, 32 bytes b64) | Encrypt tokens stored in sessions |
| `AR_CURSOR_SECRET` | (secret) | HMAC for pagination cursors |
| `AR_STEP_UP_TTL_S` | `600` | Step-up validity |
| `AR_SSE_MAX_PER_USER` | `20` | |
| `AR_MAX_JSON_BODY_BYTES` | `1048576` | |
| `AR_DEPLOYMENT_MODE` | `single_tenant` | `saas` or `single_tenant` |

## 9. Failure modes

| Failure | Behaviour |
|---|---|
| Valkey down | Session auth fails → 503 `unavailable` (bearer/API-key requests still work for non-SSE endpoints; rate limiting fails open with a warning log and metric `ar_ratelimit_bypass_total`). |
| Postgres down | `/readyz` 503; requests 503. |
| Temporal down | Endpoints that start work still return `202`: message + run (`queued`) + outbox `run.start_requested` are committed in one transaction; the immediate workflow start fails silently (logged, metric `ar_run_start_deferred_total`) and `OutboxRelayWorkflow` (or, if the system worker is also down, the next relay pass after recovery) starts it. The UI shows "queued". Synchronous calls (`POST /api/v1/runs` with `wait=true`) return 503 `unavailable` after the run is recorded as queued. |
| Keycloak down | New logins fail (redirect to `/login?error=idp_unavailable`); existing sessions continue until access token refresh is needed. |

Workflow start reliability: `conversations.service.post_message` inserts message + run (`queued`) + outbox `run.start_requested` in one transaction, then attempts `start_workflow` immediately (fast path). `OutboxRelayWorkflow` handles `run.start_requested` events whose run is still `queued` after 5 s by starting the workflow (idempotent: workflow id `run-{run_id}`, `WorkflowIDReusePolicy.REJECT_DUPLICATE`).

## 10. Metrics

- `ar_http_requests_total{route,method,status}`, `ar_http_request_duration_seconds{route,method}` (histogram).
- `ar_sse_connections{stream}` (gauge), `ar_sse_events_sent_total`.
- `ar_auth_failures_total{mechanism,reason}`.
- `ar_ratelimit_rejections_total{scope}`.

## 11. Test plan

- Unit: cursor encode/decode/tamper; problem mapping for every `ArError`; CSRF; `return_to` validation (open redirect attempts); permission computation.
- Integration (testcontainers Postgres + Valkey, Keycloak mocked with a local JWKS + `respx` for token endpoint): full login callback creates user + session; session refresh; logout; API key auth; tenant suspended → 403; idempotency replay and conflict; rate-limit 429 with headers.
- Contract: schemathesis against `openapi.json` for all `GET` endpoints with a seeded tenant (no 500s, responses match schema).
- E2E (Playwright, real Keycloak in compose): login, session persists across reload, logout.
