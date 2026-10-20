# M1 — Data, identity, tenancy, audit, events

Goal: the multi-tenant backbone. After M1 a user signs in through Keycloak, admins manage users, teams, roles, service accounts, API keys, secrets and SSO; every write is audited in a hash chain; domain events flow through the outbox; in-app/email notifications and outbound webhooks work.

Exit criteria: RLS suite and cross-tenant suite green; `admin@dev.local` logs in at `http://localhost:3000`, invites a user, assigns `builder`, creates an API key and calls `GET /api/v1/me` with it; audit chain verifies.

---

### M1-T01 · Database core in `ar_domain`
- **Depends on:** M0-T12
- **Areas:** `libs/ar_domain/src/ar_domain/db/{engine.py,base.py,context.py,session.py,repository.py,types.py}`
- **Spec:** [rls §2](../04-data/rls.md#2-session-variables), [rls §6](../04-data/rls.md#6-dedicated-database-tier), [schema §0](../04-data/schema.md#0-conventions), [tenancy-isolation](../02-architecture/tenancy-isolation.md)
- **Do:** Async engine factory (asyncpg, pool sizing from settings), declarative `Base` with naming conventions, `TenantContext(tenant_id, user_id, principal, request_id)`, `tenant_session(ctx)` that opens a transaction and runs `set_config('app.tenant_id', …, true)` etc., `platform_session(reason)` using the `ar_platform` DSN and writing `platform.session_opened` (audit hook injected later by M1-T05), `engine_for(tenant)` routing via `AR_TENANT_DB_ROUTES`, `BaseRepository` requiring `TenantContext`, common column mixins (`id` UUIDv7 default, `tenant_id`, timestamps), JSONB/citext/vector types.
- **Done when:** repositories cannot be constructed without a context (type-checked); session sets the three `app.*` variables per transaction.
- **Tests:** integration: variables are set and reset between transactions; routing picks dedicated DSN for a mapped tenant.

### M1-T02 · Alembic setup and revision 0001 `extensions_and_helpers`
- **Depends on:** M1-T01
- **Areas:** `libs/ar_domain/src/ar_domain/migrations/{env.py,script.py.mako,helpers.py,versions/*_0001_extensions_and_helpers.py}`, `alembic.ini`
- **Spec:** [migrations](../04-data/migrations.md), [rls §1, §3](../04-data/rls.md), [schema §0, §18](../04-data/schema.md)
- **Do:** Alembic async env, file template and linear-history check; revision 0001 creating extensions (`pgcrypto`, `citext`, `pg_trgm`, `vector`), functions `set_updated_at()`, `app_tenant_id()`, `app_user_id()`, `forbid_update_delete()` (append-only), grants for `ar_app`/`ar_platform`/`ar_readonly`; helpers `enable_tenant_rls`, `enable_platform_or_own_rls`, `add_updated_at_trigger`, `add_append_only_trigger`. `make migrate` and the `migrate` entry point (`python -m ar_domain.migrations.run`, then `ar_domain.seed.apply()`).
- **Done when:** `alembic upgrade head` / `downgrade base` round-trips; CI `migrations` job enabled (`alembic heads` = 1, `alembic check` empty).
- **Tests:** `tests/integration/test_migrations.py` (upgrade/downgrade/upgrade).

### M1-T03 · Revision 0002 `identity_core`, models and seed
- **Depends on:** M1-T02
- **Areas:** `ar_domain/identity/{models.py,repository.py,schemas.py,service.py,errors.py,permissions.py}`, `ar_domain/seed/{__init__.py,roles.py,plans.py}`, migration 0002, `ar_testing/factories/identity.py`
- **Spec:** [schema §1](../04-data/schema.md#1-identity-and-tenancy-ar_domainidentity), [authn-authz §3–4](../06-security/authn-authz.md), [spec 02](../03-specs/02-identity-tenancy.md)
- **Do:** Tables of schema §1 (including `support_access_grants`) with RLS per table type; SQLAlchemy models; repositories (incl. the platform lookups in rls §4); permission catalogue constant `PERMISSIONS` exactly as authn-authz §3; system roles seed exactly as authn-authz §4; plans seed (`free`, `team`, `enterprise`, `self_hosted`) with PlanLimits defaults from spec 02 §3.10; effective-permission resolver (user → direct + group + team assignments, team-scoped permissions).
- **Done when:** seed is idempotent; effective permissions for each seeded role equal the RBAC matrix.
- **Tests:** unit: resolver against the matrix (table-driven from authn-authz §4); integration: seed twice → no duplicates.

### M1-T04 · RLS and cross-tenant test suites
- **Depends on:** M1-T03
- **Areas:** `libs/ar_domain/tests/integration/test_rls.py`, `services/api/tests/security/test_cross_tenant.py` (generator scaffold), `ar_testing/tenancy.py`
- **Spec:** [rls §5](../04-data/rls.md#5-tests-mandatory), [tenancy-isolation §5](../02-architecture/tenancy-isolation.md#5-mandatory-isolation-tests)
- **Do:** RLS tests parameterised over every table in `Base.metadata` with a `tenant_id` column (so new tables are covered automatically): no context → 0 rows; tenant A context cannot read/update/delete B's rows; insert with foreign tenant_id fails. Cross-tenant API test generator that walks `openapi.json` paths with `{…_id}` parameters and uses registered factories; initially covers identity routes as they appear.
- **Done when:** suites run in CI; a table without RLS makes the suite fail (verified with a temporary test table).
- **Tests:** the suites themselves.

### M1-T05 · Revision 0003 `audit_events` and audit service
- **Depends on:** M1-T03
- **Areas:** `ar_domain/audit/**`, migration 0003
- **Spec:** [spec 17 §1](../03-specs/17-audit-usage-metering.md#1-audit), [audit](../06-security/audit.md), [schema §15](../04-data/schema.md#15-audit-and-usage-ar_domainaudit-ar_domainusage)
- **Do:** `audit_events` with append-only trigger; `audit.service.record(ctx, action, target, detail, outcome)` computing the per-tenant hash chain (`prev_hash`, `hash` = sha256 of JCS of the event without `hash`) under a per-tenant advisory lock; action names validated against the catalogue in audit.md §3 (enum in `ar_domain.audit.actions`); detail redaction (no secrets, no message content); `verify_chain(tenant, from, to)`. Hook `platform_session` to write `platform.session_opened`.
- **Done when:** concurrent writers produce a valid chain; updates/deletes rejected by the DB.
- **Tests:** integration: 50 concurrent records → chain verifies; tamper a row as `ar_owner` → verification reports the first broken id; hypothesis test of hash determinism.

### M1-T06 · Revision 0004 `events_core`, outbox relay, idempotency
- **Depends on:** M1-T05
- **Areas:** `ar_domain/events/**`, migration 0004, `services/system/src/ar_system/{worker.py,workflows/outbox_relay.py,subscribers/__init__.py}`, `services/api/src/ar_api/middleware/idempotency.py`
- **Spec:** [spec 20 §1, §4](../03-specs/20-notifications-events.md), [domain-events](../05-contracts/domain-events.md), [schema §17](../04-data/schema.md#17-events-webhooks-notifications-idempotency-ar_domainevents)
- **Do:** Tables of schema §17; `events.service.emit(ctx, type, payload)` (validates payload against `ar_contracts.events` models; same transaction as caller); `system-worker` process (Temporal worker on `ar-system` and `ar-eval`); `OutboxRelayWorkflow` (continuous: claim batch `FOR UPDATE SKIP LOCKED`, dispatch to subscribers registry, mark delivered, retries with backoff, continue-as-new every 1,000 events); `Idempotency-Key` middleware per spec 20 §4.
- **Done when:** emitted events reach a test subscriber exactly once even with two relay workers; idempotent POST replays the stored response.
- **Tests:** Temporal test env: relay with 2 workers; integration: idempotency replay, conflict on different body (409 `idempotency_key_reused`).

### M1-T07 · Revision 0005 `secrets`, secret backends and secrets API
- **Depends on:** M1-T05
- **Areas:** `ar_domain/secrets/{models.py,repository.py,service.py,store.py,stores/{vault.py,db_encrypted.py}}`, migration 0005, `ar_api/routers/secrets.py`
- **Spec:** [spec 03](../03-specs/03-secrets-credentials.md), [secrets](../06-security/secrets.md), [ADR-0012](../02-architecture/adr/ADR-0012-secrets-backend.md)
- **Do:** Tables of schema §2 (credential tables created now; their service logic lands in M4-T02); `SecretStore` protocol (`ar_domain.secrets.store`, spec 03 §2) with backends selected by `AR_SECRETS_BACKEND`: `vault` (OpenBao KV v2, Kubernetes or token auth) and `db_encrypted` (AES-256-GCM envelope, key ring `AR_DB_ENCRYPTION_KEYS`, active key id); `secrets.service` create/read-metadata/resolve/rotate/delete with personal secrets (`owner_user_id`) and in-process cache (`AR_SECRET_CACHE_TTL_S`); endpoints `GET/POST /api/v1/secrets`, `GET/PATCH/DELETE /api/v1/secrets/{secret_id}`, `POST /api/v1/secrets/{secret_id}:rotate` (routers wired to auth in M1-T09; until then tested at service level).
- **Done when:** both backends pass the same contract test; secret values never appear in logs, audit or API responses.
- **Tests:** backend contract tests (OpenBao container + db_encrypted); key rotation re-encrypt test; log scrubbing test.

### M1-T08 · Keycloak realm and BFF login
- **Depends on:** M1-T07, M0-T06
- **Areas:** `ar_api/auth/{oidc.py,session.py,routes.py,csrf.py,step_up.py}`, `ar_domain/identity/keycloak_admin.py`, `deploy/compose/keycloak/*`
- **Spec:** [spec 01 §3](../03-specs/01-api-bff.md#3-authentication-endpoints-bff), [spec 02 §2](../03-specs/02-identity-tenancy.md), [ADR-0011](../02-architecture/adr/ADR-0011-identity-keycloak-bff.md), [request-flows §1](../02-architecture/request-flows.md#1-login-bff)
- **Do:** `GET /api/v1/auth/login`, `GET /api/v1/auth/callback` (PKCE, organization → tenant, JIT user upsert, group claim sync, offline token stored as personal secret `__delegation__`), `POST /api/v1/auth/logout`, `GET /api/v1/auth/session`, `POST /api/v1/auth/switch-tenant`, `POST /api/v1/auth/step-up`, `GET /api/v1/.well-known/jwks.json`; Valkey session store (encrypted tokens, sliding/absolute TTL), cookies `ar_session`/`ar_csrf`, token refresh; Keycloak admin client wrapper used by later tasks.
- **Done when:** Playwright logs in as `member@dev.local` against the compose Keycloak and `GET /api/v1/auth/session` returns the user, tenant, permissions.
- **Tests:** integration with Keycloak container (login via direct grant for tests), CSRF rejection, session expiry with time-machine, step-up flag lifetime.

### M1-T09 · Request pipeline: principals, permissions, rate limits
- **Depends on:** M1-T08
- **Areas:** `ar_api/{deps.py,middleware/*,principal.py,ratelimit.py}`, `ar_api/routers/meta.py`
- **Spec:** [spec 01 §4–6](../03-specs/01-api-bff.md#4-request-pipeline-middleware-order), [api-conventions §2, §6](../05-contracts/api-conventions.md), [authn-authz](../06-security/authn-authz.md)
- **Do:** Middleware order per spec 01 §4; principal resolution from session cookie, OIDC bearer (audience `ar-api`), API key (`ark_` prefix, sha256 compare, scopes); `TenantContext` dependency; `require_permission(key, scope=…)` dependency including team-scoped checks; suspended tenant/user → 403; Valkey token-bucket rate limiting (`api_rpm`, per principal and per tenant, headers `RateLimit-*`); `GET /api/v1/meta`, `GET /api/v1/schemas/{kind}`. Wire M1-T07 routers.
- **Done when:** every router declares permissions (a test fails if any route lacks a permission dependency or an explicit `public=True`).
- **Tests:** unit: principal resolution matrix; integration: 429 after limit; route-permission lint test.

### M1-T10 · Identity API part 1: tenant, users, invitations, groups, teams, self
- **Depends on:** M1-T09
- **Areas:** `ar_api/routers/{tenant.py,users.py,invitations.py,groups.py,teams.py,me.py}`, `ar_domain/identity/service.py`
- **Spec:** [spec 02 §3.1, §3.3–3.6](../03-specs/02-identity-tenancy.md#3-public-api)
- **Do:** `GET/PATCH /api/v1/tenant`; `GET/PATCH /api/v1/me`; `GET /api/v1/users`, `GET/PATCH /api/v1/users/{user_id}` (suspension cascade hooks: sessions, API keys; routine/run hooks registered later); invitations (`GET/POST /api/v1/invitations`, `DELETE /api/v1/invitations/{invitation_id}`, `POST /api/v1/invitations/{token}:accept`, email via SMTP); groups (`GET/POST /api/v1/groups`, `DELETE /api/v1/groups/{group_id}`, members GET/PUT/DELETE); teams (`GET/POST /api/v1/teams`, `GET/PATCH/DELETE /api/v1/teams/{team_id}`, `POST /api/v1/teams/{team_id}/members`, `DELETE /api/v1/teams/{team_id}/members/{user_id}`). Audit and domain events per spec 02 §5. `GET /api/v1/me/export` and `POST /api/v1/users/{user_id}:erase` are implemented in M14-T02.
- **Done when:** all listed endpoints match the spec's request/response shapes and errors; TenantSettings validation enforces plan limits.
- **Tests:** integration per endpoint (happy, 403, 404, 409/422); cross-tenant generator covers them; email captured in Mailpit/GreenMail.

### M1-T11 · Identity API part 2: roles, service accounts, API keys, audit read
- **Depends on:** M1-T10
- **Areas:** `ar_api/routers/{roles.py,service_accounts.py,api_keys.py,audit.py}`
- **Spec:** [spec 02 §3.7–3.8](../03-specs/02-identity-tenancy.md#37-roles-and-assignments), [spec 17 §1.3](../03-specs/17-audit-usage-metering.md#13-api)
- **Do:** `GET /api/v1/permissions`; roles `GET/POST /api/v1/roles`, `PATCH/DELETE /api/v1/roles/{role_id}`; `GET/POST /api/v1/role-assignments`, `DELETE /api/v1/role-assignments/{assignment_id}` (last-admin guard); service accounts `GET/POST /api/v1/service-accounts`, `PATCH/DELETE /api/v1/service-accounts/{service_account_id}`; API keys `GET/POST /api/v1/api-keys`, `DELETE /api/v1/api-keys/{api_key_id}` (secret shown once); audit `GET /api/v1/audit-events`, `GET /api/v1/audit-events/{event_id}`, `POST /api/v1/audit-events:verify`.
- **Done when:** permission changes take effect on the next request (permission cache invalidated via outbox `cache_invalidation` subscriber).
- **Tests:** integration per endpoint; last-admin guard; API key with restricted scopes denied outside scopes.

### M1-T12 · SSO, domains and SCIM
- **Depends on:** M1-T11
- **Areas:** `ar_api/routers/{identity_providers.py,domains.py,scim.py,scim_tokens.py}`, `ar_domain/identity/{scim.py,keycloak_admin.py}`
- **Spec:** [spec 02 §3.1–3.2, §3.8–3.9](../03-specs/02-identity-tenancy.md#32-identity-providers-enterprise-sso)
- **Do:** `GET/POST /api/v1/tenant/domains`, `POST /api/v1/tenant/domains/{domain_id}:verify`, `DELETE /api/v1/tenant/domains/{domain_id}`; identity providers `GET/POST /api/v1/identity-providers`, `PATCH/DELETE /api/v1/identity-providers/{idp_id}` with Keycloak brokering and mappers; SCIM tokens `GET/POST /api/v1/scim-tokens`, `DELETE /api/v1/scim-tokens/{scim_token_id}`; SCIM 2.0 `/scim/v2/ServiceProviderConfig`, `/scim/v2/Schemas`, `/scim/v2/ResourceTypes`, Users and Groups CRUD with filtering (`userName eq`, `externalId eq`), PATCH ops, deprovision cascade.
- **Done when:** SCIM compliance subset passes (create, get by filter, patch active=false, group membership patch).
- **Tests:** integration with Keycloak container for IdP creation; SCIM request fixtures from RFC 7644 examples; DNS verification with a stub resolver.

### M1-T13 · Tenant lifecycle, platform admin, support access
- **Depends on:** M1-T12, M1-T06
- **Areas:** `ar_system/workflows/{tenant_provisioning.py,tenant_deletion.py}`, `ar_domain/bootstrap.py`, `ar_api/routers/{platform_tenants.py,platform_plans.py,support_access.py,signup.py}`
- **Spec:** [spec 02 §3.10–3.11, §4](../03-specs/02-identity-tenancy.md#310-platform-administration-saas-mode-only-keycloak-realm-role-platform_admin), [deployment-modes](../00-overview/deployment-modes.md), [authn-authz §6](../06-security/authn-authz.md#6-support-access-saas)
- **Do:** `TenantProvisioningWorkflow` (Keycloak org, tenants row, `seed_tenant_defaults` hook list — modules append defaults later, owner invitation); `TenantDeletionWorkflow` with grace period (steps registered by modules; v1 deletes rows, objects prefix, Keycloak org); `python -m ar_domain.bootstrap` for single-tenant mode (`AR_BOOTSTRAP_TENANT_SLUG`, `AR_BOOTSTRAP_TENANT_NAME`, `AR_BOOTSTRAP_ADMIN_EMAIL`); platform endpoints `GET/POST /api/v1/platform/tenants`, `GET/PATCH /api/v1/platform/tenants/{tenant_id}`, `:suspend`, `:resume`, `:delete`, `GET/POST /api/v1/platform/plans`, `PATCH /api/v1/platform/plans/{plan_id}`; support access `GET/POST /api/v1/tenant/support-access`, `POST /api/v1/tenant/support-access/{grant_id}:revoke`; `POST /api/v1/signup` behind `AR_SAAS_SELF_SIGNUP`. Platform routes return 404 in single-tenant mode except those listed in deployment-modes §1.
- **Done when:** provisioning is idempotent (re-running the workflow is a no-op); deletion during grace can be resumed.
- **Tests:** Temporal tests for both workflows; mode matrix tests for platform routes; support-grant expiry test.

### M1-T14 · Notifications and outbound webhooks (base)
- **Depends on:** M1-T13
- **Areas:** `ar_system/workflows/{notification_fanout.py,webhook_delivery.py}`, `ar_system/templates/email/*.html.j2`, `ar_system/subscribers/{notifications.py,webhooks.py,cache_invalidation.py}`, `ar_api/routers/{notifications.py,webhooks.py}`
- **Spec:** [spec 20 §2–3](../03-specs/20-notifications-events.md#2-notifications)
- **Do:** `NotificationFanoutWorkflow` (in-app + email channels now; Slack/Teams added in M11-T07), `GET /api/v1/notifications`, `POST /api/v1/notifications/{notification_id}:read`, `POST /api/v1/notifications:read-all`, SSE `GET /api/v1/notifications/events`; webhooks `GET/POST /api/v1/webhooks`, `GET/PATCH/DELETE /api/v1/webhooks/{webhook_id}`, `:rotate-secret`, `:test`, deliveries list, `:redeliver`; `WebhookDeliveryWorkflow` (HMAC signature, retries schedule, SSRF guard with `AR_WEBHOOK_ALLOW_PRIVATE`); `POST /api/v1/tenant/run-callback-secret:rotate`.
- **Done when:** an `invitation.created`-style event produces an in-app notification and an email; a webhook endpoint receives signed events and retries on 500.
- **Tests:** Temporal tests for delivery retries and signature; SSRF guard (private IPs blocked); SSE notification test.

### M1-T15 · Web: login, shell and admin area
- **Depends on:** M1-T14, M0-T08, M0-T09
- **Areas:** `apps/web/src/app/(auth)/**`, `apps/web/src/app/(app)/layout.tsx`, `apps/web/src/app/(admin)/admin/{users,teams,roles,api-keys,secrets,settings,sso,support-access,audit,webhooks}/**`, `apps/web/src/app/(app)/settings/{profile,notifications}/**`, `apps/web/src/components/{app-shell,permission-gate,notifications-bell}/**`, `apps/web/src/app/(platform)/platform/{tenants,plans}/**`
- **Spec:** [spec 19](../03-specs/19-web-app.md)
- **Do:** Login redirect handling, `/select-tenant`, app shell (sidebar by permission, user menu, notification bell with SSE), admin pages for every M1 endpoint group (tables with filters/pagination, create/edit dialogs, destructive confirmations, step-up prompts), platform pages (SaaS only).
- **Done when:** the spec 19 routes `/login`, `/select-tenant`, `/invite/[token]`, `/suspended`, `/settings/*`, `/admin/{users,teams,roles,sso,api-keys,secrets,audit,webhooks,settings,support-access}` and `/platform/{tenants,plans}` render with loading/empty/error states and permission gating.
- **Tests:** Vitest component tests per page; Playwright: login, invite user, create API key, verify audit chain button; axe checks.

### M1-T16 · Public JSON camelCase
- **Depends on:** M0-T09
- **Areas:** `libs/ar_contracts/src/ar_contracts/api_model.py`, response models in `ar_api` and `ar_domain/*/schemas.py`, `scripts/check_public_camel_case.py`
- **Spec:** [ADR-0026](../02-architecture/adr/ADR-0026-public-json-camel-case.md), [api-conventions §3](../05-contracts/api-conventions.md#3-request-conventions), [principles §1](../00-overview/principles.md#1-api-and-ui-casing)
- **Do:** Every public request and response model subclasses `ApiModel`. Identity routes included. `ArError.to_problem` emits `requestId` (the key in `ar_common.errors` is still `request_id`; change that key and the assertion in `libs/ar_common/tests/unit/test_core.py`). Do not rename database columns or the permission catalogue. `make gen` so the TypeScript and Zod types are camelCase. The docs CI job already runs `scripts/check_public_camel_case.py`. Apply this while writing M1 models; if models already exist on the branch, retrofit them here before M1 is finished. Do not rewrite earlier M1 tasks.
- **Done when:** `GET /api/v1/me` JSON uses `displayName` and `createdAt`, and `model_validate` still accepts the snake_case form. The camelCase check passes.
- **Tests:** one identity response round-trip (alias and python name); the schema check.
