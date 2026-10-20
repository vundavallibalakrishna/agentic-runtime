# Authentication and authorisation

Canonical permission catalogue and system roles. `ar_domain.identity.permissions.PERMISSIONS` and the seed in `ar_domain.seed.roles` must match this file exactly (test `test_permissions_match_docs` parses the tables below).

## 1. Authentication methods

| Principal | Method | Where |
|---|---|---|
| Browser user | BFF: OIDC authorization code + PKCE with Keycloak (organization = tenant, brokered company IdP); `ar_session` (HttpOnly, Secure, SameSite=Lax) + `ar_csrf` cookies | [spec 01 §3](../03-specs/01-api-bff.md#3-authentication-endpoints-bff), [ADR-0011](../02-architecture/adr/ADR-0011-identity-keycloak-bff.md) |
| User via API | OIDC bearer token (audience `ar-api`) or personal API key (`ark_…`) | [api-conventions §2](../05-contracts/api-conventions.md#2-authentication) |
| Service account | API key (`ark_…`), optional `on_behalf_of_user_id` when `allow_on_behalf_of` | [spec 02 §3.8](../03-specs/02-identity-tenancy.md#38-service-accounts-and-api-keys) |
| SCIM client | SCIM bearer token (`scim_tokens`) | spec 02 §3.9 |
| Channel users | Slack/Teams/email identity mapped to a platform user (`channel_identities`); unmapped users must link (`/api/v1/me/channel-identities:link`) | [spec 16](../03-specs/16-channels.md) |
| Widget users | Host-signed JWT exchanged at `POST /api/v1/widget/sessions` for an `ar_widget_session` limited to `chat:use` | spec 16 §7 |
| Routine webhooks | Unguessable path token + HMAC signature | [spec 15](../03-specs/15-routines-triggers.md) |
| Internal services | Internal JWT (EdDSA, ≤ 60 s, `aud` = target, acting context) | [internal-apis §1](../05-contracts/internal-apis.md#1-internal-service-authentication) |
| Platform admin (SaaS) | Keycloak realm role `platform_admin` + MFA | [spec 02 §3.10](../03-specs/02-identity-tenancy.md#310-platform-administration-saas-mode-only-keycloak-realm-role-platform_admin) |

MFA is enforced at the IdP (company IdP or Keycloak OTP/WebAuthn for local users). Step-up uses `acr_values=mfa`, `max_age=0`.

## 2. Authorisation model

1. **RBAC**: roles are sets of permission keys. Assignments bind a role to a user, group, team or service account at **tenant** scope or **team** scope (`role_assignments.scope_type`). Effective permissions = union of all assignments; team-scoped permissions apply only to resources owned by that team.
2. **Resource ownership and visibility** (ABAC-lite): resources have `owner_user_id`, `owner_team_id`, `visibility` (`private`, `team`, `tenant`); owners and team editors can act on their resources without tenant-wide permissions (rules per spec, e.g. [spec 05 §2](../03-specs/05-agent-registry.md#2-access-rules)).
3. **Data-level**: conversations are private to their owner plus explicit shares; knowledge is filtered by ACL principals; memory by scope; files by `can_read`.
4. **Agent actions**: never use RBAC of the agent — the run's user identity and policies decide ([spec 09](../03-specs/09-policy-approvals.md)).
5. **Deny by default**: every route declares its permission (lint test, M1-T09). Missing permission → 403 `forbidden`; invisible resource → 404 `not_found`.
6. **API key scopes** restrict a key to a subset of its principal's permissions.

## 3. Permission catalogue

| Permission | Category | Allows |
|---|---|---|
| `tenant:read` | tenant | Read tenant profile and settings |
| `tenant:manage` | tenant | Update settings, domains, IdPs, SCIM tokens, support-access grants, run-callback secret |
| `users:read` | identity | List users, groups, teams, roles, assignments |
| `users:manage` | identity | Invite, suspend, edit attributes, erase users; manage local groups |
| `teams:manage` | identity | Create/update/delete teams and memberships (team leads manage their own team without it) |
| `roles:manage` | identity | Custom roles and role assignments |
| `service_accounts:manage` | identity | Service accounts and their API keys |
| `api_keys:manage_own` | identity | Personal API keys |
| `secrets:use` | secrets | List secret names in pickers and reference them in definitions |
| `secrets:manage` | secrets | Create, rotate, delete tenant secrets; credential providers |
| `connections:manage_own` | secrets | Connect/disconnect own OAuth accounts |
| `models:read` | models | View providers, models, aliases |
| `models:manage` | models | Manage tenant providers, models, aliases |
| `chat:use` | chat | Chat with visible agents, upload files, manage own conversations and memory |
| `conversations:read_all` | chat | Read any conversation in the tenant (investigations; audited) |
| `agents:read` | agents | Browse the agent catalogue |
| `agents:create` | agents | Create agents (become owner) |
| `agents:edit` | agents | Edit drafts of agents owned by the scope (team-scoped typical) |
| `agents:publish` | agents | Publish/rollback agents they can edit; tenant visibility |
| `agents:disable` | agents | Kill switch on any agent |
| `agents:manage_all` | agents | Full control of all agents; second-person publish for high-risk agents |
| `memory:manage_agent` | memory | Review and edit agent- and team-scope memory |
| `tools:read` | tools | Browse tool servers and tools |
| `tools:create` | tools | Register tool servers and data connections (become owner) |
| `tools:review` | tools | Approve/reject tool server versions, set risk classes |
| `tools:disable` | tools | Kill switch on tools and servers |
| `knowledge:read` | knowledge | Browse collections visible to the user and search them |
| `knowledge:manage` | knowledge | Create collections and sources; manage documents and access |
| `skills:read` | skills | Browse skills |
| `skills:create` | skills | Create skills (become owner) |
| `skills:manage_all` | skills | Manage all skills |
| `policies:read` | policy | Read policies and simulate |
| `policies:manage` | policy | Create, version, activate, disable policies |
| `approvals:decide` | approvals | Decide approvals assigned to them (by policy approver rule) |
| `approvals:read_all` | approvals | See all approvals in the tenant |
| `approvals:grant_standing` | approvals | Create and revoke standing approvals |
| `routines:create` | routines | Create routines (run as themselves) |
| `routines:manage_all` | routines | Manage and transfer any routine |
| `sandboxes:manage` | sandboxes | Manage sandbox templates; terminate any sandbox |
| `channels:manage` | channels | Channel integrations and identities |
| `webhooks:manage` | events | Outbound webhooks |
| `usage:read` | usage | Usage, cost and observability overview |
| `quotas:manage` | usage | Quotas |
| `audit:read` | audit | Audit search and chain verification |
| `audit:export` | audit | Audit exports |
| `evals:run` | evals | Run eval suites |
| `evals:manage` | evals | Manage eval suites/cases; read feedback |

`platform:*` is not assignable inside a tenant; it is implied by the Keycloak realm role `platform_admin` and only valid on `/api/v1/platform/*` and `POST /api/v1/auth/switch-tenant`.

## 4. System roles

Seeded with `tenant_id NULL`, `is_system=true`, immutable. Every new user gets `member` (via the `everyone` team assignment created by `seed_tenant_defaults`).

| Role key | Intended for | Permissions |
|---|---|---|
| `member` | Every employee | `tenant:read`, `chat:use`, `agents:read`, `tools:read`, `knowledge:read`, `skills:read`, `connections:manage_own`, `api_keys:manage_own`, `routines:create`, `secrets:use`, `models:read`, `policies:read` |
| `builder` | Agent builders | member + `agents:create`, `agents:edit`, `agents:publish`, `skills:create`, `evals:run`, `evals:manage`, `memory:manage_agent`, `usage:read` |
| `tool_owner` | Tool server owners | member + `tools:create` |
| `knowledge_manager` | Content owners | member + `knowledge:manage` |
| `approver` | Business approvers | member + `approvals:decide`, `approvals:grant_standing` |
| `auditor` | Security/compliance | member + `audit:read`, `audit:export`, `approvals:read_all`, `usage:read`, `users:read`, `tools:read`, `policies:read` |
| `tenant_admin` | IT administrators | every permission in §3 |

`conversations:read_all` is included only in `tenant_admin`; auditors do not read content by default. `approvals:decide` alone does not make someone an approver of a specific call: the policy decision's approver rule (user, group, team role, resource owner, manager attribute) selects eligible approvers, who must also hold `approvals:decide`.

### RBAC matrix (summary by area)

| Area / action | member | builder | tool_owner | knowledge_manager | approver | auditor | tenant_admin |
|---|---|---|---|---|---|---|---|
| Chat with visible agents | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage own memory, files, connections, API keys | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create own routines | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Create/edit/publish agents | – | ✓ (own/team) | – | – | – | – | ✓ (all) |
| Disable any agent | – | – | – | – | – | – | ✓ |
| Register tool servers | – | – | ✓ | – | – | – | ✓ |
| Review tool versions / set risk | – | – | – | – | – | – | ✓ |
| Manage knowledge collections | – | – | – | ✓ | – | – | ✓ |
| Create skills | – | ✓ | – | – | – | – | ✓ |
| Decide approvals (when selected by policy) | – | – | – | – | ✓ | – | ✓ |
| Grant standing approvals | – | – | – | – | ✓ | – | ✓ |
| Author policies | – | – | – | – | – | – | ✓ |
| Read policies / simulate | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Usage & observability | – | ✓ | – | – | – | ✓ | ✓ |
| Quotas | – | – | – | – | – | – | ✓ |
| Audit read / export | – | – | – | – | – | ✓ | ✓ |
| Users, teams, roles, SSO, SCIM | – | – | – | – | – | read users | ✓ |
| Secrets, models, channels, webhooks, sandboxes | – | – | – | – | – | – | ✓ |
| Read any conversation | – | – | – | – | – | – | ✓ (audited) |
| Evals | – | ✓ | – | – | – | – | ✓ |

Tenants may create custom roles from the catalogue (e.g. `tool_reviewer` = member + `tools:review` + `tools:disable`) and team-scoped assignments (e.g. `builder` scoped to team "Finance").

## 5. Step-up authentication

Requires a session with `step_up_at` within `AR_STEP_UP_TTL_S` (600 s); API keys cannot perform these actions unless explicitly listed:

- Deciding approvals for `W3` tool calls when tenant setting `security.require_step_up_for_w3` is `true` (default) — web only; channels show "Open in web".
- `POST /api/v1/users/{user_id}:erase`, role assignment of `tenant_admin`, deleting identity providers.
- `POST /api/v1/tenant/support-access`, `POST /api/v1/tenant/run-callback-secret:rotate`.
- Creating or rotating tenant secrets (`POST /api/v1/secrets`, `POST /api/v1/secrets/{secret_id}:rotate`) — service accounts with `secrets:manage` exempt for automation.
- Activating policies (`POST /api/v1/policies/{policy_id}:activate`).
- Platform: tenant deletion (`POST /api/v1/platform/tenants/{tenant_id}:delete`).
- Support-access `content` level use by the operator.

## 6. Support access (SaaS)

- Platform admins have **no** standing access to tenant data. Platform pages show only tenant metadata (name, plan, status, usage totals).
- A tenant admin grants access (`POST /api/v1/tenant/support-access`, step-up) to a named operator for 1–72 h with level `metadata` (configuration, runs/steps metadata, audit, no message/file/tool-result content) or `content` (adds conversations and files).
- The operator enters the tenant via `POST /api/v1/auth/switch-tenant`; all requests carry `actor_type='platform_admin'` and `detail.support_grant_id` in audit; the UI shows a persistent banner to the operator and an "active support session" notice to tenant admins.
- Grants are revocable at any time (`POST /api/v1/tenant/support-access/{grant_id}:revoke`) and end at `expires_at`.
- Break-glass DB access (`ar_readonly`) is outside the product: it requires two operators, is time-boxed by the DB credential lease in OpenBao, and is logged; procedure in [runbooks](../07-ops/runbooks.md).

## 7. Session and transport security

- TLS 1.2+ at ingress (cert-manager); in-cluster mTLS optional via mesh; internal JWT regardless.
- Cookies: `ar_session` HttpOnly, Secure, SameSite=Lax, path `/`; `ar_csrf` readable by JS; CSRF header `X-CSRF-Token` required on non-GET session requests.
- Session store in Valkey with encrypted tokens (`AR_SESSION_ENCRYPTION_KEY`), sliding `AR_SESSION_TTL_S`, absolute `AR_SESSION_MAX_AGE_S`; session id rotated at login and step-up; revoked on logout, user suspension, IdP deprovisioning.
- Security headers: CSP (nonce-based scripts, `frame-ancestors 'none'` except widget routes), HSTS 1 year, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal.
- User-generated HTML is never rendered inline in the app origin ([spec 13](../03-specs/13-files-artifacts.md)).
- Outbound requests (webhooks, web.fetch, OpenAPI base URLs, model providers, OAuth endpoints) pass the shared SSRF guard (`ar_common.http.ssrf_guard`): resolve and pin IPs, deny private/link-local/metadata ranges unless explicitly allowed by `AR_WEBHOOK_ALLOW_PRIVATE`, `AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS`, `AR_MODEL_PROVIDER_DENY_CIDRS`.

## 8. Internal service authorisation

Each internal endpoint declares allowed callers (`iss`) — tables in [internal-apis](../05-contracts/internal-apis.md). Targets never accept tenant/user identity from the request body; they use the JWT acting context. Sandboxes and MCP servers receive scoped tokens only (sandbox token, `X-AR-Context`).

## 9. Permissions added after the M1 baseline

M1-T03 seeds only §3. The keys below are registered by the task that introduces them. `tenant_admin` includes a key once that task has shipped. Do not add these rows to the M1 seed.

Step-up, in addition to §5: creating or releasing a legal hold; uninstalling a pack with `dropSchema: true`; the final sign-off level when `security.require_step_up_for_signoff` is true.

Role extensions once the introducing task has shipped, not in the M1 matrix: `approver` gains `reviews:read` and `reviews:decide`; `auditor` gains `evidence:read`, `evidence:export`, `run_records:read`, `reviews:read`, `ai_governance:read`, `binders:export`.

### 9.1 Core

| Key | Task |
|---|---|
| `packs:manage` | M3-T09 |
| `reviews:read`, `reviews:decide`, `reviews:manage` | M5-T08 |
| `sod:manage` | M5-T09 |
| `evidence:read`, `evidence:capture`, `evidence:export` | M14-T08 |
| `holds:manage` | M14-T09 |
| `retention:manage` | M14-T09 |
| `ai_governance:read`, `ai_governance:manage` | M14-T10 |
| `guests:invite`, `guests:manage` | M14-T11 |
| `binders:export` | M14-T12 |
| `run_records:read`, `run_records:replay` | M13-T07 |

### 9.2 GRC pack

Registered when the pack is installed. Prefix `grc.`.

`grc.frameworks:read`, `grc.frameworks:manage`, `grc.controls:read`, `grc.controls:manage`, `grc.evidence:link`, `grc.tests:read`, `grc.tests:run`, `grc.findings:read`, `grc.findings:manage`, `grc.risks:read`, `grc.risks:manage`, `grc.vendors:read`, `grc.vendors:manage`, `grc.policies:read`, `grc.policies:manage`, `grc.obligations:read`, `grc.obligations:manage`, `grc.incidents:read`, `grc.incidents:manage`, `grc.campaigns:read`, `grc.campaigns:manage`, `grc.questionnaires:read`, `grc.questionnaires:manage`, `grc.audit_portal:manage`, `grc.reports:export`, `grc.entities:read`, `grc.entities:manage`, `grc.exceptions:manage`, `grc.ethics:manage`, `grc.inspections:manage`, `grc.privacy:manage`.
