# Spec 01: `api` service (public API, BFF, cross-cutting HTTP concerns)

Deployable: `api` (`services/api`, package `ar_api`). Hosts the routers of every domain module (each module's endpoints are specified in its own spec) plus the cross-cutting concerns defined here: authentication/session (BFF), CSRF, tenancy context, RBAC enforcement, errors, pagination, idempotency, rate limiting, SSE plumbing, OpenAPI, health. Conventions: [api-conventions.md](../05-contracts/api-conventions.md).

## 1. Responsibilities

1. Sign-in. Production is the customer's OIDC provider: authorization code in the browser, and a JWT bearer checked against that issuer's JWKS ([ADR-0031](../02-architecture/adr/ADR-0031-oidc-production-identity.md)). Userid/password is the dev and single-tenant mode and is not the Helm default. Server-side sessions live in Valkey. The session cookie is `ar_session` (HttpOnly, SameSite=Lax, and Secure outside dev and ci).
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
  auth/                # routes.py (password login), identity.py, session.py, csrf.py, credentials.py (api keys, scim), step_up.py
  middleware/          # request_id.py, ratelimit.py, body_limit.py, errors.py, security_headers.py
  routers/             # one module per domain: identity.py, agents.py, conversations.py, runs.py, tools.py, ...
  sse.py               # stream helpers (Valkey XREAD → SSE)
  internal/            # /internal/v1 routers (opa bundle, jwks, channels, connectors)
  openapi.py           # ERROR_RESPONSES, operation id generator
```

## 3. Authentication endpoints (BFF)

All under `/api/v1/auth`. No authentication required unless stated.

#### POST /api/v1/auth/login
Served only when auth mode is `password` (dev, ci, or `AR_PASSWORD_LOGIN=true` on a single-tenant install). Body `{email, password, otp?}`. Verifies the password against the argon2id `users.password_hash`. When the user has `attributes.totp_secret`, or `AR_PASSWORD_MFA` is set, `otp` must match that TOTP. On success creates session `ar:sess:{sid}` (TTL = `AR_SESSION_TTL_S`, default 12 h sliding, absolute max 7 days), sets cookies `ar_session` (HttpOnly, SameSite=Lax, Secure outside dev and ci) and `ar_csrf` (not HttpOnly, SameSite=Strict, Secure outside dev and ci), audits `auth.login`, returns `{ok: true}`. Failures are `application/problem+json`. A missing user, an unset password and a wrong password are all `401` `unauthenticated` with the same detail. Repeated failures lock the address in Valkey (`429` `rate_limited` with `Retry-After`). A suspended tenant is `403` `tenant_suspended`.

#### GET /api/v1/auth/oidc/start
Served only when auth mode is `oidc`. Redirects the browser to the configured issuer's authorization endpoint (PKCE S256). `purpose=step-up` asks the provider for a fresh MFA sign-in.

#### GET /api/v1/auth/callback
Exchanges the code, checks the id token against the issuer JWKS, and requires a configured `amr` or `acr` when `AR_OIDC_REQUIRE_MFA` is set. The email (or subject) must already be a person of the tenant. Issues the same session cookies.

Integrator calls send `Authorization: Bearer` with an access token from that issuer (`aud` = `AR_OIDC_AUDIENCE`, default `ar-api`). This does not replace `ark_` keys.

#### POST /api/v1/auth/logout
Auth: session. Deletes the session, clears the cookies, returns `{ok: true}`. Audits `auth.logout`.

#### GET /api/v1/auth/session
Auth: session or bearer. Response `SessionInfo`:
```json
{"user": {"id":"...","email":"...","displayName":"...","locale":"en","timezone":"UTC"},
 "tenant": {"id":"...","slug":"talentfino","name":"TalentFino","plan":"enterprise","deploymentMode":"saas"},
 "permissions": ["chat:use","agents:read", "..."], "roles": ["member","builder"],
 "memberships": [{"tenantId":"...","slug":"...","name":"..."}],
 "csrfToken": "...", "features": {"customRego": false, "teamsChannel": true}}
```

#### POST /api/v1/auth/switch-tenant
Auth: session. Body `{tenant_id}`. A single-tenant install serves one tenant, so this confirms the caller's own tenant (else 403 `forbidden`) and returns `{redirect_url: "/login"}`. Multi-tenant switching returns with multi-tenant login ([OQ-122](../open-questions.md)).

#### POST /api/v1/auth/step-up
Auth: session. Body `{confirmed: true}`. Without an external IdP there is no MFA redirect: the person confirms and the session's `step_up_at` is stamped fresh (valid `AR_STEP_UP_TTL_S`, default 10 min). Used by W3 approvals. TOTP step-up is a follow-up ([OQ-122](../open-questions.md)).

#### GET /api/v1/.well-known/jwks.json
Public JWKS for `internal_jwt`-mode tool servers outside the cluster ([mcp-integration](../05-contracts/mcp-integration.md) §4.5).

## 4. Request pipeline (middleware order)

1. `request_id` (accept/generate `X-Request-Id`), OTel server span.
2. `security_headers`: `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Cross-Origin-Resource-Policy: same-origin`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` (API responses only).
3. `body_limit`.
4. `authenticate` → `Principal | None` (no principal on public routes).
5. `tenant_guard`: tenant `status='active'` (else 403 `tenant_suspended`; platform admins exempt on `/api/v1/platform/*`).
6. `csrf`: for session-authenticated unsafe methods, `X-CSRF-Token` must equal the session's csrf token (constant-time compare). `Origin`, when present, must be `AR_PUBLIC_URL` or a host listed in `AR_CSRF_ALLOWED_ORIGINS`. In dev and CI only, localhost, 127.0.0.1 and ::1 are the same host. Production does not treat those names as equivalent.
7. `ratelimit`.
8. Router → dependency `require(...)` → service.
9. `errors` maps `ArError` subclasses to problem+json; unknown exceptions → 500 `internal_error` with request id.

## 5. Principal resolution

| Credential | Resolution |
|---|---|
| `ar_session` | Valkey lookup; sliding TTL refreshed on use; absolute max age enforced; on expiry or revocation → 401 and the session is deleted. |
| API key (`ark_` or key id + secret) | Prefix lookup, constant-time secret compare, resolves to the key's personal or service-account `Principal` ([spec 02 §3.8](02-identity-tenancy.md#38-service-accounts-and-api-keys)). |
| `ark_...` | Prefix lookup (`find_api_key_by_prefix`), constant-time hash compare, not revoked/expired; principal = service account or the owning user; effective permissions = principal permissions ∩ key scopes (if non-empty). Updates `last_used_at` at most once per minute. |
| `scim_...` | Only on `/scim/v2/*`. |

Permissions are computed by `identity.service.effective_permissions(principal)` = union of permissions of roles assigned to the user directly, via groups, and via teams (team-scoped assignments add permissions only for resources owned by that team). Cached in Valkey `ar:perms:{tenant_id}:{principal_id}` for 60 s and invalidated on role/membership changes.

## 6. Health and meta endpoints

#### GET /healthz
Liveness: 200 `{"status":"ok"}` if the process is up.

#### GET /readyz
Readiness, cached 10 s. Always checks Postgres (`SELECT 1`). Checks Valkey `PING` when sessions and the rate limiter are shared (not `dev` or `ci`). Checks Temporal health when `AR_TEMPORAL_REQUIRED` is set. 503 with the failing check names. `/healthz` does not connect.

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
| `AR_SESSION_TTL_S` | `43200` | Sliding session TTL |
| `AR_SESSION_MAX_AGE_S` | `604800` | Absolute session max |
| `AR_SESSION_ENCRYPTION_KEY` | (secret, 32 bytes b64) | Encrypt tokens stored in sessions |
| `AR_CURSOR_SECRET` | (secret) | HMAC for pagination cursors. Outside `dev` and `ci` the process refuses to boot when this is missing or still `dev-cursor-secret`. |
| `AR_STEP_UP_TTL_S` | `600` | Step-up validity |
| `AR_SSE_MAX_PER_USER` | `20` | |
| `AR_MAX_JSON_BODY_BYTES` | `1048576` | |
| `AR_DEPLOYMENT_MODE` | `single_tenant` | `saas` or `single_tenant` |

## 9. Failure modes

| Failure | Behaviour |
|---|---|
| Valkey down | Session auth fails → 503 `unavailable` (bearer/API-key requests still work for non-SSE endpoints). The shared rate limiter retries, then denies the request (`ar_ratelimit_unavailable_total`). It does not latch open. |
| Postgres down | `/readyz` 503; requests 503. |
| Temporal down | When `AR_TEMPORAL_REQUIRED` is unset, the API still runs the turn in process. When it is set, the turn is not run in process: it is marked failed with error `code` `interrupted` and `reason` `not_resumed`. `/readyz` is 503 while the check fails. |
| Database unreachable at sign-in | Login fails closed (`invalid_credentials`); existing sessions continue until their TTL. |

Workflow start reliability: `conversations.service.post_message` inserts message + run (`queued`) + outbox `run.start_requested` in one transaction, then attempts `start_workflow` immediately (fast path). `OutboxRelayWorkflow` handles `run.start_requested` events whose run is still `queued` after 5 s by starting the workflow (idempotent: workflow id `run-{run_id}`, `WorkflowIDReusePolicy.REJECT_DUPLICATE`).

## 10. Metrics

- `ar_http_requests_total{route,method,status}`, `ar_http_request_duration_seconds{route,method}` (histogram).
- `ar_sse_connections{stream}` (gauge), `ar_sse_events_sent_total`.
- `ar_auth_failures_total{mechanism,reason}`.
- `ar_auth_principal_total{method,outcome}` — one per credential resolution, labelled by auth method (`api_key`, `scim`, `session`, …) and `outcome` (`ok`, `denied`). Labels only; no token or tenant content.
- `ar_ratelimit_rejections_total{scope}`.

## 11. Test plan

- Unit: cursor encode/decode/tamper; problem mapping for every `ArError`; CSRF; `return_to` validation (open redirect attempts); permission computation.
- Integration (testcontainers Postgres + Valkey, Keycloak mocked with a local JWKS + `respx` for token endpoint): full login callback creates user + session; session refresh; logout; API key auth; tenant suspended → 403; idempotency replay and conflict; rate-limit 429 with headers.
- Contract: schemathesis against `openapi.json` for all `GET` endpoints with a seeded tenant (no 500s, responses match schema).
- E2E (Playwright, real Keycloak in compose): login, session persists across reload, logout.
