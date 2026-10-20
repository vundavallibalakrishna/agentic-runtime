# Spec 02: Identity and tenancy (`ar_domain.identity`)

Hosted in `api` (routers `ar_api.routers.identity`, `ar_api.routers.scim`, `ar_api.routers.platform`) with workflows in `system-worker`. Owns tables: `plans`, `tenants`, `tenant_domains`, `identity_providers`, `users`, `groups`, `group_members`, `teams`, `team_members`, `roles`, `role_assignments`, `service_accounts`, `api_keys`, `scim_tokens`, `invitations` ([schema §1](../04-data/schema.md#1-identity-and-tenancy-ar_domainidentity)). Security model: [authn-authz.md](../06-security/authn-authz.md). Isolation: [tenancy-isolation.md](../02-architecture/tenancy-isolation.md).

## 1. Responsibilities

- Tenant lifecycle (provision, configure, suspend, delete) in both deployment modes.
- Users (JIT on login, SCIM, invitations), groups (SCIM/IdP claims/local), teams (platform org units), roles and assignments, effective permissions.
- Enterprise SSO configuration per tenant (brokered IdPs in Keycloak Organizations), domain verification.
- Service accounts, API keys, SCIM tokens.
- Deprovisioning cascade (sessions, API keys, credential grants, routines pause) and DPDP erasure / export.

## 2. Keycloak model ([ADR-0011](../02-architecture/adr/ADR-0011-identity-keycloak-bff.md))

- One realm `agentic-runtime`. Clients: `ar-web` (confidential, BFF), `ar-api` (bearer audience), `ar-admin` (service account with `realm-management: manage-users, manage-identity-providers, manage-realm (organizations)`), `ar-token-exchange` (used by `mcp-gateway` for RFC 8693).
- Each tenant = one Keycloak **Organization** (`tenants.keycloak_org_id`). Org domains = verified `tenant_domains`. Brokered IdPs (`identity_providers.keycloak_alias`) are linked to the org with domain-based routing so users are sent to their company IdP after entering their email.
- Token claims mapped by client scopes: `organization` (org id/alias), `groups` (IdP group names, when the tenant does not use SCIM), `email`, `name`, `acr`.
- Single-tenant mode: the same realm layout with exactly one organization created by `TenantProvisioningWorkflow` at install (`AR_BOOTSTRAP_TENANT_SLUG`); org selection is skipped.
- Keycloak admin calls go through `ar_domain.identity.keycloak.KeycloakAdmin` (httpx, client-credentials token cached until expiry - 30 s).

## 3. Public API

Permissions are from [authn-authz.md](../06-security/authn-authz.md) §3. All list endpoints paginate per [conventions §4](../05-contracts/api-conventions.md#4-pagination).

### 3.1 Current tenant

#### GET /api/v1/tenant
Permission: `tenant:read`. Response `Tenant`: `{id, slug, name, status, plan: {key, name, limits}, isolation_tier, data_residency, billing_currency, settings: TenantSettings, created_at}`.

`TenantSettings`: `{default_timezone: "Asia/Kolkata", default_locale: "en-IN", retention: {conversations_days: 365, run_events_days: 90, files_days: 365, audit_years: 7, memory_inactive_days: 730, deleted_conversation_days: 30}, egress_allowlist: [domain], run_budget_caps: RunBudget, features: {custom_rego: false, teams_channel: true, email_channel: true, widget: false, web_fetch: false, guardrails: false, injection_classifier: true, pii_redaction: true}, chat: {allow_sharing: true}, limits: {max_active_runs_per_user: 5}, branding: {product_name, logo_file_id, primary_color}, memory: {enabled: true, extraction: true}, approvals: {default_ttl_s: 86400}, security: {require_step_up_for_w3: true, allow_self_review: false, allowed_upload_mime_types: [...], max_upload_mb: 100}, audit: {siem: {enabled: false, webhook_id: null}}, observability: {capture_content: false}, privacy: {notice_text_md: "", notice_version: "0", grievance_contact: {name: "", email: ""}}}` ([data-protection §3](../06-security/data-protection.md#3-data-principal-rights)).

#### PATCH /api/v1/tenant
Permission: `tenant:manage`. Body: partial `{name, settings}` (merge patch). Validation: retention values within plan limits; `egress_allowlist` entries are domains (no wildcards except leading `*.`). Audit `tenant.updated` (diff).

#### GET /api/v1/tenant/domains
Permission: `tenant:manage`. List `TenantDomain {id, domain, verified_at, verification_token}`.

#### POST /api/v1/tenant/domains
Permission: `tenant:manage`. Body `{domain}`. Creates with random `verification_token`; instructions: DNS TXT `_ar-verify.<domain>` = token. 409 if the domain is used by another tenant.

#### POST /api/v1/tenant/domains/{domain_id}:verify
Permission: `tenant:manage`. Resolves TXT record (DNS over the system resolver, timeout 5 s); on match sets `verified_at` and adds the domain to the Keycloak organization. Errors: `422 domain_verification_failed`.

#### DELETE /api/v1/tenant/domains/{domain_id}
Permission: `tenant:manage`. Removes from Keycloak org too.

### 3.2 Identity providers (enterprise SSO)

#### GET /api/v1/identity-providers
Permission: `tenant:manage`.

#### POST /api/v1/identity-providers
Permission: `tenant:manage`. Body `{kind: "oidc"|"saml", display_name, config: IdpConfig, client_secret?: string}`. `IdpConfig` (oidc): `{issuer, client_id, scopes: ["openid","email","profile"], groups_claim?: "groups", attribute_mappings: {department: "dept", location: "loc"}}`; (saml): `{metadata_url | metadata_xml, entity_id, name_id_format, attribute_mappings}`. The client secret is stored via secrets service and referenced by `secret_ref_id`. Creates the brokered IdP in Keycloak (`keycloak_alias = "{tenant_slug}-{kind}-{n}"`) with mappers, links it to the org. Audit `idp.created`.

#### PATCH /api/v1/identity-providers/{idp_id}
Permission: `tenant:manage`. Updates display name/config/status; syncs Keycloak.

#### DELETE /api/v1/identity-providers/{idp_id}
Permission: `tenant:manage`. 409 `invalid_state` if it is the only active IdP and the tenant has no local-password users (prevents lock-out). Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)).

### 3.3 Users and self

#### GET /api/v1/me
Any authenticated user. `User` + `{settings, roles, teams: [{id, name, team_role}], groups: [{id, name}]}`.

#### PATCH /api/v1/me
Body `{display_name?, settings?: {locale, timezone, memory_enabled, notifications: {email: bool, slack: bool, teams: bool}, theme: "system"|"light"|"dark"}}`. Optional `accept_notice_version: string`: must equal the tenant's current `settings.privacy.notice_version`; stores it in `users.attributes.notice_version` with timestamp and writes audit `user.notice_accepted`. `GET /api/v1/me` returns `notice: {version, text_md, accepted: bool}`; the web app blocks navigation with a notice dialog until accepted when the tenant has a non-empty notice.

#### GET /api/v1/me/export
Starts a personal data export (DPDP right to access): returns `202 {export_id}`; `ErasureWorkflow` in export mode builds a ZIP (`files.kind='export'`) of the user's conversations, messages, memory facts, files metadata, and notifies when ready.

#### GET /api/v1/users
Permission: `users:read`. Filters: `q` (email/name trigram), `status`, `group_id`, `team_id`. Item `UserSummary {id, email, display_name, status, last_login_at, roles: [key]}`.

#### GET /api/v1/users/{user_id}
Permission: `users:read`.

#### PATCH /api/v1/users/{user_id}
Permission: `users:manage`. Body `{status?: "active"|"suspended", attributes?: object}`. Suspending: deletes sessions (`ar:sess:*` index `ar:user-sessions:{user_id}`), revokes the user's personal API keys, pauses routines owned (`paused_reason='owner_suspended'`), cancels non-terminal runs. Audit `user.suspended`.

#### POST /api/v1/users/{user_id}:erase
Permission: `users:manage` + step-up. Starts `ErasureWorkflow` (DPDP erasure): deletes conversations/messages/files/memory/credential grants of the user, does not delete `audit_events`: they are retained (legal basis: security logging) but `detail` never contains message content. Response `202 {request_id}`. Audit `user.erasure_requested`. Refused with `409 invalid_state` while the user owns active routines or agents (UI forces reassignment first).

### 3.4 Invitations (tenants without SCIM, or SaaS)

#### GET /api/v1/invitations
Permission: `users:manage`.

#### POST /api/v1/invitations
Permission: `users:manage`. Body `{emails: [string] (≤ 100), role_keys: [string]}`. For each email: creates the Keycloak user in the org (if absent; sends Keycloak "execute actions" email for password/MFA setup when the org has no IdP), inserts `invitations` (token hash, expires 7 days), sends email via SMTP with link `/invite/{token}`. Response: list of `Invitation`.

#### DELETE /api/v1/invitations/{invitation_id}
Permission: `users:manage`. Revoke.

#### POST /api/v1/invitations/{token}:accept
Public (then redirects to login). Validates token and expiry; marks accepted on first successful login of that email in the tenant (role assignments applied then).

### 3.5 Groups

#### GET /api/v1/groups
Permission: `users:read`. Filters `q`, `source`.

#### POST /api/v1/groups
Permission: `users:manage`. Body `{name}` → `source='local'`.

#### DELETE /api/v1/groups/{group_id}
Permission: `users:manage`. Only `source='local'` (SCIM/IdP groups are managed upstream → 409).

#### GET /api/v1/groups/{group_id}/members
Permission: `users:read`.

#### PUT /api/v1/groups/{group_id}/members/{user_id}
Permission: `users:manage`. Local groups only.

#### DELETE /api/v1/groups/{group_id}/members/{user_id}
Permission: `users:manage`. Local groups only.

### 3.6 Teams

#### GET /api/v1/teams
Permission: `users:read`.

#### POST /api/v1/teams
Permission: `teams:manage`. Body `{slug, name, description?, group_id?}`. If `group_id` set, membership mirrors that group (members API read-only; sync on SCIM/group changes).

#### GET /api/v1/teams/{team_id}
Permission: `users:read`.

#### PATCH /api/v1/teams/{team_id}
Permission: `teams:manage` or team lead.

#### DELETE /api/v1/teams/{team_id}
Permission: `teams:manage`. 409 if it owns agents/tool servers/collections (must reassign).

#### POST /api/v1/teams/{team_id}/members
Permission: `teams:manage` or team lead. Body `{user_id, team_role}`.

#### DELETE /api/v1/teams/{team_id}/members/{user_id}
Permission: `teams:manage` or team lead.

### 3.7 Roles and assignments

#### GET /api/v1/permissions
Any authenticated. The permission catalogue `[{key, description, category}]`.

#### GET /api/v1/roles
Permission: `users:read`. System roles + tenant custom roles.

#### POST /api/v1/roles
Permission: `roles:manage`. Body `{key, name, description, permissions: [key]}`. Cannot include `platform:*`.

#### PATCH /api/v1/roles/{role_id}
Permission: `roles:manage`. System roles are immutable (409).

#### DELETE /api/v1/roles/{role_id}
Permission: `roles:manage`. Custom roles only; cascades assignments.

#### GET /api/v1/role-assignments
Permission: `users:read`. Filters `principal_type`, `principal_id`, `role_id`, `scope_id`.

#### POST /api/v1/role-assignments
Permission: `roles:manage`. Body `{role_id, principal_type, principal_id, scope_type: "tenant"|"team", scope_id?}`. Guard: at least one active user must keep `tenant_admin` (cannot remove the last one → 409). Assigning the `tenant_admin` role requires step-up ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)).

#### DELETE /api/v1/role-assignments/{assignment_id}
Permission: `roles:manage`.

### 3.8 Service accounts and API keys

#### GET /api/v1/service-accounts
Permission: `service_accounts:manage`.

#### POST /api/v1/service-accounts
Permission: `service_accounts:manage`. Body `{name, description, allow_on_behalf_of?: false}`. Service accounts receive roles through role assignments. `allow_on_behalf_of=true` lets the account start runs as a tenant user (`POST /api/v1/runs` with `on_behalf_of_user_id`); enabling it is audited (`service_account.on_behalf_of_enabled`).

#### PATCH /api/v1/service-accounts/{service_account_id}
Permission: `service_accounts:manage`. `{description?, status?, allow_on_behalf_of?}`; disabling revokes keys.

#### DELETE /api/v1/service-accounts/{service_account_id}
Permission: `service_accounts:manage`.

#### GET /api/v1/api-keys
Permission: `api_keys:manage_own` (own personal keys) or `service_accounts:manage` (filter `service_account_id`). Never returns secrets.

#### POST /api/v1/api-keys
Body `{name, service_account_id?: uuid, scopes?: [permission], expires_in_days?: 1..365 (default 90)}`. Response includes `key` (`ark_` + 12-char prefix + 43-char secret) **once**. Audit `api_key.created`.

#### DELETE /api/v1/api-keys/{api_key_id}
Revoke (`revoked_at`). Audit `api_key.revoked`.

#### GET /api/v1/scim-tokens
Permission: `tenant:manage`.

#### POST /api/v1/scim-tokens
Permission: `tenant:manage`. Response includes the token (`scim_...`) once.

#### DELETE /api/v1/scim-tokens/{scim_token_id}
Permission: `tenant:manage`.

### 3.9 SCIM 2.0 (RFC 7643/7644)

Base `/scim/v2`, auth SCIM token, `Content-Type: application/scim+json`. Supported: `Users` (`userName` = email, `name`, `emails`, `active`, `externalId`, enterprise extension `department`, `manager`), `Groups` (`displayName`, `members`, `externalId`), filtering `eq` on `userName`/`externalId`/`displayName`, `startIndex`/`count` pagination, PATCH ops `add`/`replace`/`remove`.

#### GET /scim/v2/ServiceProviderConfig
#### GET /scim/v2/Schemas
#### GET /scim/v2/ResourceTypes
#### GET /scim/v2/Users
#### POST /scim/v2/Users
#### GET /scim/v2/Users/{scim_user_id}
#### PUT /scim/v2/Users/{scim_user_id}
#### PATCH /scim/v2/Users/{scim_user_id}
#### DELETE /scim/v2/Users/{scim_user_id}
#### GET /scim/v2/Groups
#### POST /scim/v2/Groups
#### GET /scim/v2/Groups/{scim_group_id}
#### PUT /scim/v2/Groups/{scim_group_id}
#### PATCH /scim/v2/Groups/{scim_group_id}
#### DELETE /scim/v2/Groups/{scim_group_id}

Semantics: `active=false` or DELETE → user `status='deprovisioned'` + the suspension cascade (§3.3) + Keycloak user disabled; groups map to `groups.source='scim'`; `scim_user_id` = `users.id`. All SCIM writes are audited (`scim.user.*`, `scim.group.*`).

### 3.10 Platform administration (SaaS mode only; Keycloak realm role `platform_admin`)

#### GET /api/v1/platform/tenants
Filters `q`, `status`, `plan_key`.

#### POST /api/v1/platform/tenants
Body `{slug, name, plan_key, owner_email, data_residency?, isolation_tier?}` → starts `TenantProvisioningWorkflow`, returns `202 {tenant_id}` (status `provisioning`).

#### GET /api/v1/platform/tenants/{tenant_id}
#### PATCH /api/v1/platform/tenants/{tenant_id}
Body `{name?, plan_key?, isolation_tier?, settings?}`.

#### POST /api/v1/platform/tenants/{tenant_id}:suspend
Body `{reason}`. Sets `suspended`; all requests from tenant principals get 403; running workflows are cancelled; schedules paused.

#### POST /api/v1/platform/tenants/{tenant_id}:resume

#### POST /api/v1/platform/tenants/{tenant_id}:delete
Body `{confirm_slug}`. Starts `TenantDeletionWorkflow` (status `deleting`): exports audit to the audit bucket, deletes the tenant's retrieval entries (`RetrievalStore.delete` per collection; pgvector rows also cascade), deletes objects under `t/{tenant_id}/`, deletes Keycloak org/users, deletes rows (FK cascade from `tenants`), marks `deleted`. Irreversible after a 7-day grace (`AR_TENANT_DELETE_GRACE_DAYS`) during which `:resume` restores. Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)).

#### GET /api/v1/platform/plans
#### POST /api/v1/platform/plans
#### PATCH /api/v1/platform/plans/{plan_id}
`PlanLimits`: `{max_users, max_agents (default 200), max_tool_servers, max_collections, max_knowledge_documents (default 100000), max_knowledge_bytes (default 50 GiB), max_storage_gb, max_routines (default 500), max_concurrent_runs (default 100), max_concurrent_sandboxes (default 50), max_sandbox_cpu_millis (default 8000), max_sandbox_memory_mb (default 16384), monthly_cost_micros (implicit tenant quota), api_rpm, unit_prices: {metric: micros_per_unit}, max_retention: {conversations_days, audit_years}, features: {custom_rego, widget, teams_channel, email_channel, web_fetch, guardrails, tenant_model_providers}}`. Tenant `settings.features` can only enable features the plan allows.

### 3.11 Support access (SaaS mode only)

Platform admins cannot read tenant content by default. A tenant admin grants time-boxed access ([authn-authz §6](../06-security/authn-authz.md#6-support-access-saas)); `api` checks for an active `support_access_grants` row whenever a `platform_admin` principal switches into a tenant (`POST /api/v1/auth/switch-tenant`). Level `metadata` = read configuration, runs and audit without message/file/tool-result content; `content` additionally allows reading conversations and files (step-up required for the operator). Every request under a grant is audited with `actor_type='platform_admin'` and `detail.support_grant_id`.

#### GET /api/v1/tenant/support-access
Permission `tenant:manage`. Lists grants (active first).

#### POST /api/v1/tenant/support-access
Permission `tenant:manage` + step-up. Body `{operator_email, level: "metadata"|"content", reason, ticket_ref?, duration_hours: 1..72}`. Resolves `operator_subject` from Keycloak realm users holding `platform_admin` (422 `validation_failed` if not found). Audit `support_access.granted`; notification to all tenant admins.

#### POST /api/v1/tenant/support-access/{grant_id}:revoke
Permission `tenant:manage`. Sets `revoked_at`; active operator sessions in that tenant end on next request. Audit `support_access.revoked`.

#### POST /api/v1/signup
Public; only when `AR_SAAS_SELF_SIGNUP=true`. Body `{company_name, slug, email, captcha_token}`. Creates tenant on plan `free` via `TenantProvisioningWorkflow`; owner receives a Keycloak verification email.

## 4. Workflows (task queue `ar-system`)

### TenantProvisioningWorkflow (id `tenant-provision-{tenant_id}`)
Activities (each idempotent; retry policy: initial 2 s, backoff 2.0, max 10 attempts):
1. `create_keycloak_org(tenant)` → stores `keycloak_org_id`.
2. `seed_tenant_defaults(tenant_id)`: built-in default agent `assistant` (instructions "You are a helpful assistant for {tenant name}…", tools: knowledge, memory, sandbox, files, skills, plan, agents), team `everyone`, default quotas from plan, tenant settings defaults.
3. `invite_owner(tenant_id, owner_email)`: creates invitation with role `tenant_admin`.
4. `mark_active(tenant_id)`; emit `tenant.created`; audit `tenant.provisioned`.

### TenantDeletionWorkflow (id `tenant-delete-{tenant_id}`)
Timer for grace period, then activities: `export_audit_chain`, `delete_vectors`, `delete_objects`, `delete_keycloak_org`, `terminate_sandboxes`, `delete_rows`, `mark_deleted`. Each activity heartbeats and resumes from a checkpoint (cursor in heartbeat details).

### ErasureWorkflow (id `erase-{user_id}-{request_id}`)
Modes `erase` | `export`. Erase: cancel runs → delete sandboxes scoped to the user → delete files objects → delete conversations (cascade messages, run data) → delete memory facts → revoke credential grants and delete their secrets → mark user `deprovisioned`, scrub `display_name` to `"Erased user"`, `email` to `erased+{id}@invalid` → emit `erasure.completed` → audit. SLA: complete within 72 h (target minutes); backups purge per retention ([data-protection](../06-security/data-protection.md)).

## 5. Domain events and audit

Events: `tenant.created`, `tenant.suspended`, `user.provisioned`, `user.deprovisioned`, `erasure.completed`. Audit actions: `auth.login`, `auth.logout`, `auth.login_failed`, `tenant.updated`, `tenant.provisioned`, `tenant.suspended`, `tenant.deleted`, `idp.created|updated|deleted`, `user.updated`, `user.suspended`, `user.erasure_requested`, `role.created|updated|deleted`, `role_assignment.created|deleted`, `team.*`, `group.*`, `service_account.*`, `api_key.created|revoked`, `scim.user.*`, `scim.group.*`, `invitation.*`, `platform.session_opened`.

## 6. Limits

| Limit | Default |
|---|---|
| Users per tenant | plan `max_users` |
| Groups per user (ACL principal set size) | 2,000 (beyond: truncated with warning; ACL filter uses all of them: one `text[]` overlap predicate on pgvector, `should` blocks of 500 on the qdrant adapter) |
| API keys per principal | 20 |
| Custom roles per tenant | 50 |
| Invitations per request | 100 |

## 7. Failure modes

- Keycloak admin API unavailable during provisioning → workflow retries; tenant stays `provisioning`; platform UI shows status.
- SCIM bursts → SCIM endpoints rate-limited separately (300 req/min per token).
- JIT login race (two tabs) → upsert on `(tenant_id, idp_subject)`.

## 8. Metrics

`ar_logins_total{tenant,result}`, `ar_scim_requests_total{op,result}`, `ar_tenants{status}`, `ar_active_users_daily` (gauge computed by `UsageRollupWorkflow`).

## 9. Test plan

- Unit: permission union over direct/group/team assignments; last-admin guard; API key format/hash/verify; SCIM filter parser; domain validation.
- Integration: SCIM create/patch/deactivate user → status and cascade (sessions deleted, routines paused); invitation accept flow; RLS cross-tenant for every identity table; KeycloakAdmin against a real Keycloak container (compose profile `keycloak`) in a nightly suite.
- Workflow tests (Temporal `WorkflowEnvironment` time-skipping): provisioning happy path and retry on Keycloak failure; deletion grace + resume; erasure removes all user rows (assert by querying every table with `user_id`/`owner_user_id`).
- E2E: admin invites user → user logs in → sees default agent.
