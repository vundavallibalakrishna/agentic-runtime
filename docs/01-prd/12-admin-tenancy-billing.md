# PRD 12 — Admin, tenancy & billing

Tenant admins run their company's workspace: identity, roles, secrets, models, usage, quotas, audit, retention and data-principal rights. Platform operators provision tenants and plans (SaaS). Spec: [spec 02](../03-specs/02-identity-tenancy.md), [spec 03](../03-specs/03-secrets-credentials.md), [spec 04](../03-specs/04-model-gateway.md), [spec 17](../03-specs/17-audit-usage-metering.md), [authn-authz](../06-security/authn-authz.md), [data-protection](../06-security/data-protection.md). Plan: [M1](../09-plan/M01-foundation.md), [M2](../09-plan/M02-first-chat.md), [M12](../09-plan/M12-usage-quotas.md), [M14](../09-plan/M14-security-compliance.md).

### US-ADM-01 · Provision a tenant (P0)
As a **platform operator**, I want to create a tenant with a plan and first admin (SaaS), or have the single tenant bootstrapped at install (single-tenant).
- SaaS: `POST /api/v1/platform/tenants` runs `TenantProvisioningWorkflow` (Keycloak organization, tenant row, defaults, owner invitation); optional self-signup when `AR_SAAS_SELF_SIGNUP=true`.
- Single-tenant: the bootstrap Job creates the tenant from `AR_BOOTSTRAP_TENANT_SLUG`/`_NAME` and invites `AR_BOOTSTRAP_ADMIN_EMAIL` on plan `self_hosted`.
- Spec: spec 02 §3.10, §4; [deployment-modes](../00-overview/deployment-modes.md). Plan: M1-T13, M15-T06.

### US-ADM-02 · Enterprise SSO (P0)
As a **tenant admin**, I want employees to sign in with our corporate IdP (OIDC or SAML).
- `POST /api/v1/identity-providers` configures a brokered IdP in Keycloak with attribute and group mappers; verified email domains (`/tenant/domains` + `:verify` DNS TXT) route users to the IdP at login; step-up required.
- Spec: spec 02 §3.1–3.2, [spec 01](../03-specs/01-api-bff.md). Plan: M1-T08, M1-T12.

### US-ADM-03 · Provision users and groups automatically (P0)
As a **tenant admin**, I want SCIM 2.0 provisioning so that joiners and leavers are handled by our IdP.
- SCIM token (`POST /api/v1/scim-tokens`, shown once); `/scim/v2/Users` and `/scim/v2/Groups` per RFC 7643/7644; `active=false` or DELETE deprovisions the user with the suspension cascade (sessions, API keys, connections revoked) and disables the Keycloak user.
- Spec: spec 02 §3.8–3.9. Plan: M1-T12.

### US-ADM-04 · Invite users without SCIM (P0)
As a **tenant admin**, I want to invite people by email.
- Invitations with roles, expiry and revocation; accepting signs the user in via the tenant's login method.
- Spec: spec 02 §3.4. Plan: M1-T10.

### US-ADM-05 · Roles and permissions (P0)
As a **tenant admin**, I want to assign system roles or custom roles at tenant or team scope.
- System roles `member`, `builder`, `tool_owner`, `knowledge_manager`, `approver`, `auditor`, `tenant_admin` with the RBAC matrix of authn-authz §4; custom roles from the permission catalogue; assignments to users, groups, teams or service accounts; effective permissions shown per user.
- Spec: spec 02 §3.7, authn-authz §3–4. Plan: M1-T03, M1-T11.

### US-ADM-06 · Teams (P0)
As a **tenant admin**, I want teams with leads so that agents, collections and memory can be team-owned.
- Teams CRUD, members with role `lead`/`member`; team-scoped role assignments; team visibility used across agents, collections, skills.
- Spec: spec 02 §3.6. Plan: M1-T10.

### US-ADM-07 · Service accounts and API keys (P0)
As a **tenant admin**, I want service accounts with scoped API keys for integrations.
- Service accounts receive roles; API keys (for a service account or for myself) are shown once (`ark_…`), stored hashed, optionally narrowed by `scopes`, expire after `expires_in_days` (default 90, max 365) and can be revoked; `allow_on_behalf_of` lets a service account run as a named user (audited).
- Spec: spec 02 §3.8. Plan: M1-T11.

### US-ADM-08 · Manage secrets and credential providers (P0)
As a **tenant admin**, I want secrets stored safely and OAuth providers configured for user connections.
- `POST /api/v1/secrets` (write-only values; step-up on create and rotate), `:rotate`, references shown with where-used; credential providers for user OAuth; values never readable through the API.
- Spec: spec 03, [secrets](../06-security/secrets.md). Plan: M1-T07, M4-T02.

### US-ADM-09 · Register company models (P0)
As a **tenant admin** (or platform operator), I want to register our OpenAI-compatible model endpoints and map aliases.
- Platform providers/models/aliases (`reasoning`, `fast`, `vision`, `embed`, `rerank`) for all tenants; tenant-specific providers when plan feature `tenant_model_providers` is on; aliases with fallbacks and traffic split; `:test` checks connectivity.
- Spec: spec 04. Plan: M2-T01, M2-T03, M2-T13.

### US-ADM-10 · Usage visibility and cost attribution (P0)
As a **tenant admin**, I want usage and cost by user, team, agent, model and day.
- `GET /api/v1/usage/summary` with group-by and filters; CSV export; users see their own usage (`GET /api/v1/me/usage`); amounts in micro-units of the tenant currency (`tenants.billing_currency`; platform models priced in `AR_BILLING_CURRENCY`).
- Spec: spec 17 §2. Plan: M2-T02, M12-T03, M12-T04.

### US-ADM-11 · Quotas and plan limits (P0)
As a **tenant admin**, I want quotas on tokens and cost per tenant, team, user or agent with warn and block actions.
- Quotas with period and action (`warn` at threshold → `quota.warning`; `block` → 429 `quota_exceeded`); plan limits (`max_agents`, `max_concurrent_runs`, …) return 409 `plan_limit_reached`; features not in plan return 403 `forbidden` with detail `feature_not_in_plan:<feature>`.
- Spec: spec 17 §2.2, spec 02 (PlanLimits). Plan: M12-T01, M12-T02.

### US-ADM-12 · Audit log (P0)
As an **auditor**, I want a tamper-evident audit log I can search, verify and export.
- `GET /api/v1/audit-events` with filters (actor, action, target, time); `POST /api/v1/audit-events:verify` checks the hash chain; exports as JSONL/CSV; optional SIEM streaming via webhook; actions per [audit §3](../06-security/audit.md#3-catalogue).
- Spec: spec 17 §1. Plan: M1-T05, M1-T11, M14-T03.

### US-ADM-13 · Retention and data-principal rights (P0)
As a **data protection officer**, I want retention settings, user data export and erasure to meet DPDP obligations.
- Tenant retention settings applied by `RetentionSweepWorkflow`; `GET /api/v1/me/export` for users; `POST /api/v1/users/{user_id}:erase` (step-up) runs `ErasureWorkflow`; privacy notice with versioned acceptance and grievance contact.
- Spec: [data-protection](../06-security/data-protection.md), spec 02 §4, spec 17 §3. Plan: M14-T02.

### US-ADM-14 · Support access with tenant consent (P1, SaaS only)
As a **tenant admin**, I want to grant the operator's support team time-boxed access, and see what they did.
- `POST /api/v1/tenant/support-access` with level (`metadata` or `content`) and expiry; revocable; operator sessions show a banner and are audited (`platform.session_opened`, `conversation.read_privileged`); without a grant operators cannot read tenant content.
- Spec: spec 02 §3.11, [authn-authz §6](../06-security/authn-authz.md#6-support-access-saas). Plan: M1-T13, M14-T06.
