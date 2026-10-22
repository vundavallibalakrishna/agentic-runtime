# API catalogue

Every public HTTP endpoint, generated from the `#### METHOD /path` headings of the specs in [03-specs](../03-specs/) (the spec section is normative). Conventions (auth, errors, pagination, idempotency, ETags): [api-conventions](api-conventions.md). Internal service-to-service endpoints: [internal-apis](internal-apis.md). Stream events: [stream-events](stream-events.md).

After implementation, CI job `docs` runs `scripts/check_api_catalogue.py`, which fails if `openapi.json` and this catalogue differ (method + path).

Pack routes are indexed from [10-grc-pack/api.md](../10-grc-pack/api.md). The original core rows were not regenerated. New endpoints are appended at the end.

Total: **552** endpoints.

Permission column: the permission key named first in the spec text (additional object-level rules in the spec); other entries name the authentication mechanism, or `object-level` when access depends on ownership/visibility of the resource (owner, viewer, editor, eligible approver) as defined in the spec section.

## Spec 01: `api` service (public API, BFF, cross-cutting HTTP concerns)

Spec: [01-api-bff.md](../03-specs/01-api-bff.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/auth/login`](../03-specs/01-api-bff.md#get-apiv1authlogin) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| GET | [`/api/v1/auth/callback`](../03-specs/01-api-bff.md#get-apiv1authcallback) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| POST | [`/api/v1/auth/logout`](../03-specs/01-api-bff.md#post-apiv1authlogout) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| GET | [`/api/v1/auth/session`](../03-specs/01-api-bff.md#get-apiv1authsession) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| POST | [`/api/v1/auth/switch-tenant`](../03-specs/01-api-bff.md#post-apiv1authswitch-tenant) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| POST | [`/api/v1/auth/step-up`](../03-specs/01-api-bff.md#post-apiv1authstep-up) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| GET | [`/api/v1/.well-known/jwks.json`](../03-specs/01-api-bff.md#get-apiv1well-knownjwksjson) | public / session (see spec) | 3. Authentication endpoints (BFF) |
| GET | [`/healthz`](../03-specs/01-api-bff.md#get-healthz) | none (cluster-internal) | 6. Health and meta endpoints |
| GET | [`/readyz`](../03-specs/01-api-bff.md#get-readyz) | none (cluster-internal) | 6. Health and meta endpoints |
| GET | [`/metrics`](../03-specs/01-api-bff.md#get-metrics) | none (cluster-internal) | 6. Health and meta endpoints |
| GET | [`/api/v1/meta`](../03-specs/01-api-bff.md#get-apiv1meta) | any signed-in principal | 6. Health and meta endpoints |
| GET | [`/api/v1/openapi.json`](../03-specs/01-api-bff.md#get-apiv1openapijson) | object-level (see spec) | 6. Health and meta endpoints |
| GET | [`/api/v1/schemas/{kind}`](../03-specs/01-api-bff.md#get-apiv1schemaskind) | any signed-in principal | 6. Health and meta endpoints |

## Spec 02: Identity and tenancy (`ar_domain.identity`)

Spec: [02-identity-tenancy.md](../03-specs/02-identity-tenancy.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/tenant`](../03-specs/02-identity-tenancy.md#get-apiv1tenant) | `tenant:read` | 3. Public API |
| PATCH | [`/api/v1/tenant`](../03-specs/02-identity-tenancy.md#patch-apiv1tenant) | `tenant:manage` | 3. Public API |
| GET | [`/api/v1/tenant/domains`](../03-specs/02-identity-tenancy.md#get-apiv1tenantdomains) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/tenant/domains`](../03-specs/02-identity-tenancy.md#post-apiv1tenantdomains) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/tenant/domains/{domain_id}:verify`](../03-specs/02-identity-tenancy.md#post-apiv1tenantdomainsdomain_idverify) | `tenant:manage` | 3. Public API |
| DELETE | [`/api/v1/tenant/domains/{domain_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1tenantdomainsdomain_id) | `tenant:manage` | 3. Public API |
| GET | [`/api/v1/identity-providers`](../03-specs/02-identity-tenancy.md#get-apiv1identity-providers) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/identity-providers`](../03-specs/02-identity-tenancy.md#post-apiv1identity-providers) | `tenant:manage` | 3. Public API |
| PATCH | [`/api/v1/identity-providers/{idp_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1identity-providersidp_id) | `tenant:manage` | 3. Public API |
| DELETE | [`/api/v1/identity-providers/{idp_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1identity-providersidp_id) | `tenant:manage` | 3. Public API |
| GET | [`/api/v1/me`](../03-specs/02-identity-tenancy.md#get-apiv1me) | any signed-in principal | 3. Public API |
| PATCH | [`/api/v1/me`](../03-specs/02-identity-tenancy.md#patch-apiv1me) | any signed-in principal | 3. Public API |
| GET | [`/api/v1/me/export`](../03-specs/02-identity-tenancy.md#get-apiv1meexport) | any signed-in principal | 3. Public API |
| GET | [`/api/v1/users`](../03-specs/02-identity-tenancy.md#get-apiv1users) | `users:read` | 3. Public API |
| GET | [`/api/v1/users/{user_id}`](../03-specs/02-identity-tenancy.md#get-apiv1usersuser_id) | `users:read` | 3. Public API |
| PATCH | [`/api/v1/users/{user_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1usersuser_id) | `users:manage` | 3. Public API |
| POST | [`/api/v1/users/{user_id}:erase`](../03-specs/02-identity-tenancy.md#post-apiv1usersuser_iderase) | `users:manage` | 3. Public API |
| GET | [`/api/v1/invitations`](../03-specs/02-identity-tenancy.md#get-apiv1invitations) | `users:manage` | 3. Public API |
| POST | [`/api/v1/invitations`](../03-specs/02-identity-tenancy.md#post-apiv1invitations) | `users:manage` | 3. Public API |
| DELETE | [`/api/v1/invitations/{invitation_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1invitationsinvitation_id) | `users:manage` | 3. Public API |
| POST | [`/api/v1/invitations/{token}:accept`](../03-specs/02-identity-tenancy.md#post-apiv1invitationstokenaccept) | `users:manage` | 3. Public API |
| GET | [`/api/v1/groups`](../03-specs/02-identity-tenancy.md#get-apiv1groups) | `users:read` | 3. Public API |
| POST | [`/api/v1/groups`](../03-specs/02-identity-tenancy.md#post-apiv1groups) | `users:manage` | 3. Public API |
| DELETE | [`/api/v1/groups/{group_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1groupsgroup_id) | `users:manage` | 3. Public API |
| GET | [`/api/v1/groups/{group_id}/members`](../03-specs/02-identity-tenancy.md#get-apiv1groupsgroup_idmembers) | `users:read` | 3. Public API |
| PUT | [`/api/v1/groups/{group_id}/members/{user_id}`](../03-specs/02-identity-tenancy.md#put-apiv1groupsgroup_idmembersuser_id) | `users:manage` | 3. Public API |
| DELETE | [`/api/v1/groups/{group_id}/members/{user_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1groupsgroup_idmembersuser_id) | `users:manage` | 3. Public API |
| GET | [`/api/v1/teams`](../03-specs/02-identity-tenancy.md#get-apiv1teams) | `users:read` | 3. Public API |
| POST | [`/api/v1/teams`](../03-specs/02-identity-tenancy.md#post-apiv1teams) | `teams:manage` | 3. Public API |
| GET | [`/api/v1/teams/{team_id}`](../03-specs/02-identity-tenancy.md#get-apiv1teamsteam_id) | `users:read` | 3. Public API |
| PATCH | [`/api/v1/teams/{team_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1teamsteam_id) | `teams:manage` | 3. Public API |
| DELETE | [`/api/v1/teams/{team_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1teamsteam_id) | `teams:manage` | 3. Public API |
| POST | [`/api/v1/teams/{team_id}/members`](../03-specs/02-identity-tenancy.md#post-apiv1teamsteam_idmembers) | `teams:manage` | 3. Public API |
| DELETE | [`/api/v1/teams/{team_id}/members/{user_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1teamsteam_idmembersuser_id) | `teams:manage` | 3. Public API |
| GET | [`/api/v1/permissions`](../03-specs/02-identity-tenancy.md#get-apiv1permissions) | any signed-in principal | 3. Public API |
| GET | [`/api/v1/roles`](../03-specs/02-identity-tenancy.md#get-apiv1roles) | `users:read` | 3. Public API |
| POST | [`/api/v1/roles`](../03-specs/02-identity-tenancy.md#post-apiv1roles) | `roles:manage` | 3. Public API |
| PATCH | [`/api/v1/roles/{role_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1rolesrole_id) | `roles:manage` | 3. Public API |
| DELETE | [`/api/v1/roles/{role_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1rolesrole_id) | `roles:manage` | 3. Public API |
| GET | [`/api/v1/role-assignments`](../03-specs/02-identity-tenancy.md#get-apiv1role-assignments) | `users:read` | 3. Public API |
| POST | [`/api/v1/role-assignments`](../03-specs/02-identity-tenancy.md#post-apiv1role-assignments) | `roles:manage` | 3. Public API |
| DELETE | [`/api/v1/role-assignments/{assignment_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1role-assignmentsassignment_id) | `roles:manage` | 3. Public API |
| GET | [`/api/v1/service-accounts`](../03-specs/02-identity-tenancy.md#get-apiv1service-accounts) | `service_accounts:manage` | 3. Public API |
| POST | [`/api/v1/service-accounts`](../03-specs/02-identity-tenancy.md#post-apiv1service-accounts) | `service_accounts:manage` | 3. Public API |
| PATCH | [`/api/v1/service-accounts/{service_account_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1service-accountsservice_account_id) | `service_accounts:manage` | 3. Public API |
| DELETE | [`/api/v1/service-accounts/{service_account_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1service-accountsservice_account_id) | `service_accounts:manage` | 3. Public API |
| GET | [`/api/v1/api-keys`](../03-specs/02-identity-tenancy.md#get-apiv1api-keys) | `api_keys:manage_own` | 3. Public API |
| POST | [`/api/v1/api-keys`](../03-specs/02-identity-tenancy.md#post-apiv1api-keys) | `api_keys:manage_own` | 3. Public API |
| DELETE | [`/api/v1/api-keys/{api_key_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1api-keysapi_key_id) | `api_keys:manage_own` | 3. Public API |
| GET | [`/api/v1/scim-tokens`](../03-specs/02-identity-tenancy.md#get-apiv1scim-tokens) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/scim-tokens`](../03-specs/02-identity-tenancy.md#post-apiv1scim-tokens) | `tenant:manage` | 3. Public API |
| DELETE | [`/api/v1/scim-tokens/{scim_token_id}`](../03-specs/02-identity-tenancy.md#delete-apiv1scim-tokensscim_token_id) | `tenant:manage` | 3. Public API |
| GET | [`/scim/v2/ServiceProviderConfig`](../03-specs/02-identity-tenancy.md#get-scimv2serviceproviderconfig) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/Schemas`](../03-specs/02-identity-tenancy.md#get-scimv2schemas) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/ResourceTypes`](../03-specs/02-identity-tenancy.md#get-scimv2resourcetypes) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/Users`](../03-specs/02-identity-tenancy.md#get-scimv2users) | SCIM bearer token | 3. Public API |
| POST | [`/scim/v2/Users`](../03-specs/02-identity-tenancy.md#post-scimv2users) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/Users/{scim_user_id}`](../03-specs/02-identity-tenancy.md#get-scimv2usersscim_user_id) | SCIM bearer token | 3. Public API |
| PUT | [`/scim/v2/Users/{scim_user_id}`](../03-specs/02-identity-tenancy.md#put-scimv2usersscim_user_id) | SCIM bearer token | 3. Public API |
| PATCH | [`/scim/v2/Users/{scim_user_id}`](../03-specs/02-identity-tenancy.md#patch-scimv2usersscim_user_id) | SCIM bearer token | 3. Public API |
| DELETE | [`/scim/v2/Users/{scim_user_id}`](../03-specs/02-identity-tenancy.md#delete-scimv2usersscim_user_id) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/Groups`](../03-specs/02-identity-tenancy.md#get-scimv2groups) | SCIM bearer token | 3. Public API |
| POST | [`/scim/v2/Groups`](../03-specs/02-identity-tenancy.md#post-scimv2groups) | SCIM bearer token | 3. Public API |
| GET | [`/scim/v2/Groups/{scim_group_id}`](../03-specs/02-identity-tenancy.md#get-scimv2groupsscim_group_id) | SCIM bearer token | 3. Public API |
| PUT | [`/scim/v2/Groups/{scim_group_id}`](../03-specs/02-identity-tenancy.md#put-scimv2groupsscim_group_id) | SCIM bearer token | 3. Public API |
| PATCH | [`/scim/v2/Groups/{scim_group_id}`](../03-specs/02-identity-tenancy.md#patch-scimv2groupsscim_group_id) | SCIM bearer token | 3. Public API |
| DELETE | [`/scim/v2/Groups/{scim_group_id}`](../03-specs/02-identity-tenancy.md#delete-scimv2groupsscim_group_id) | SCIM bearer token | 3. Public API |
| GET | [`/api/v1/platform/tenants`](../03-specs/02-identity-tenancy.md#get-apiv1platformtenants) | platform admin (SaaS) | 3. Public API |
| POST | [`/api/v1/platform/tenants`](../03-specs/02-identity-tenancy.md#post-apiv1platformtenants) | platform admin (SaaS) | 3. Public API |
| GET | [`/api/v1/platform/tenants/{tenant_id}`](../03-specs/02-identity-tenancy.md#get-apiv1platformtenantstenant_id) | platform admin (SaaS) | 3. Public API |
| PATCH | [`/api/v1/platform/tenants/{tenant_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1platformtenantstenant_id) | platform admin (SaaS) | 3. Public API |
| POST | [`/api/v1/platform/tenants/{tenant_id}:suspend`](../03-specs/02-identity-tenancy.md#post-apiv1platformtenantstenant_idsuspend) | platform admin (SaaS) | 3. Public API |
| POST | [`/api/v1/platform/tenants/{tenant_id}:resume`](../03-specs/02-identity-tenancy.md#post-apiv1platformtenantstenant_idresume) | platform admin (SaaS) | 3. Public API |
| POST | [`/api/v1/platform/tenants/{tenant_id}:delete`](../03-specs/02-identity-tenancy.md#post-apiv1platformtenantstenant_iddelete) | platform admin (SaaS) | 3. Public API |
| GET | [`/api/v1/platform/plans`](../03-specs/02-identity-tenancy.md#get-apiv1platformplans) | platform admin (SaaS) | 3. Public API |
| POST | [`/api/v1/platform/plans`](../03-specs/02-identity-tenancy.md#post-apiv1platformplans) | platform admin (SaaS) | 3. Public API |
| PATCH | [`/api/v1/platform/plans/{plan_id}`](../03-specs/02-identity-tenancy.md#patch-apiv1platformplansplan_id) | platform admin (SaaS) | 3. Public API |
| GET | [`/api/v1/tenant/support-access`](../03-specs/02-identity-tenancy.md#get-apiv1tenantsupport-access) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/tenant/support-access`](../03-specs/02-identity-tenancy.md#post-apiv1tenantsupport-access) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/tenant/support-access/{grant_id}:revoke`](../03-specs/02-identity-tenancy.md#post-apiv1tenantsupport-accessgrant_idrevoke) | `tenant:manage` | 3. Public API |
| POST | [`/api/v1/signup`](../03-specs/02-identity-tenancy.md#post-apiv1signup) | `tenant:manage` | 3. Public API |

## Spec 03: Secrets and delegated credentials (`ar_domain.secrets`)

Spec: [03-secrets-credentials.md](../03-specs/03-secrets-credentials.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/secrets`](../03-specs/03-secrets-credentials.md#get-apiv1secrets) | `secrets:use` | 3. Public API |
| POST | [`/api/v1/secrets`](../03-specs/03-secrets-credentials.md#post-apiv1secrets) | `secrets:manage` | 3. Public API |
| GET | [`/api/v1/secrets/{secret_id}`](../03-specs/03-secrets-credentials.md#get-apiv1secretssecret_id) | `secrets:manage` | 3. Public API |
| PATCH | [`/api/v1/secrets/{secret_id}`](../03-specs/03-secrets-credentials.md#patch-apiv1secretssecret_id) | `secrets:manage` | 3. Public API |
| POST | [`/api/v1/secrets/{secret_id}:rotate`](../03-specs/03-secrets-credentials.md#post-apiv1secretssecret_idrotate) | `secrets:manage` | 3. Public API |
| DELETE | [`/api/v1/secrets/{secret_id}`](../03-specs/03-secrets-credentials.md#delete-apiv1secretssecret_id) | `secrets:manage` | 3. Public API |
| GET | [`/api/v1/credential-providers`](../03-specs/03-secrets-credentials.md#get-apiv1credential-providers) | `tools:read` | 3. Public API |
| POST | [`/api/v1/credential-providers`](../03-specs/03-secrets-credentials.md#post-apiv1credential-providers) | `tools:create` | 3. Public API |
| PATCH | [`/api/v1/credential-providers/{provider_id}`](../03-specs/03-secrets-credentials.md#patch-apiv1credential-providersprovider_id) | `tools:create` | 3. Public API |
| DELETE | [`/api/v1/credential-providers/{provider_id}`](../03-specs/03-secrets-credentials.md#delete-apiv1credential-providersprovider_id) | `tenant:manage` | 3. Public API |
| GET | [`/api/v1/connections`](../03-specs/03-secrets-credentials.md#get-apiv1connections) | `connections:manage_own` | 3. Public API |
| POST | [`/api/v1/connections/{provider_id}:start`](../03-specs/03-secrets-credentials.md#post-apiv1connectionsprovider_idstart) | `connections:manage_own` | 3. Public API |
| GET | [`/api/v1/connections/oauth/callback`](../03-specs/03-secrets-credentials.md#get-apiv1connectionsoauthcallback) | `connections:manage_own` | 3. Public API |
| DELETE | [`/api/v1/connections/{grant_id}`](../03-specs/03-secrets-credentials.md#delete-apiv1connectionsgrant_id) | `connections:manage_own` | 3. Public API |

## Spec 04: Model gateway (`model-gateway`) and model registry (`ar_domain.models`)

Spec: [04-model-gateway.md](../03-specs/04-model-gateway.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/model-providers`](../03-specs/04-model-gateway.md#get-apiv1model-providers) | `models:read` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/model-providers`](../03-specs/04-model-gateway.md#post-apiv1model-providers) | `models:read` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/model-providers/{provider_id}`](../03-specs/04-model-gateway.md#patch-apiv1model-providersprovider_id) | `models:read` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/model-providers/{provider_id}`](../03-specs/04-model-gateway.md#delete-apiv1model-providersprovider_id) | `models:read` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/model-providers/{provider_id}:test`](../03-specs/04-model-gateway.md#post-apiv1model-providersprovider_idtest) | `models:read` | 4. Registry API (served by `api`) |
| GET | [`/api/v1/models`](../03-specs/04-model-gateway.md#get-apiv1models) | `models:read` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/models`](../03-specs/04-model-gateway.md#post-apiv1models) | `models:read` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/models/{model_id}`](../03-specs/04-model-gateway.md#patch-apiv1modelsmodel_id) | `models:read` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/models/{model_id}`](../03-specs/04-model-gateway.md#delete-apiv1modelsmodel_id) | `models:read` | 4. Registry API (served by `api`) |
| GET | [`/api/v1/model-aliases`](../03-specs/04-model-gateway.md#get-apiv1model-aliases) | `models:read` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/model-aliases`](../03-specs/04-model-gateway.md#post-apiv1model-aliases) | `models:read` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/model-aliases/{alias_id}`](../03-specs/04-model-gateway.md#patch-apiv1model-aliasesalias_id) | `models:read` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/model-aliases/{alias_id}`](../03-specs/04-model-gateway.md#delete-apiv1model-aliasesalias_id) | `models:read` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/model-aliases/{alias_id}:test`](../03-specs/04-model-gateway.md#post-apiv1model-aliasesalias_idtest) | `models:manage` | 4. Registry API (served by `api`) |
| GET | [`/api/v1/platform/model-providers`](../03-specs/04-model-gateway.md#get-apiv1platformmodel-providers) | `models:manage` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/platform/model-providers`](../03-specs/04-model-gateway.md#post-apiv1platformmodel-providers) | `models:manage` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/platform/model-providers/{provider_id}`](../03-specs/04-model-gateway.md#patch-apiv1platformmodel-providersprovider_id) | `models:manage` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/platform/model-providers/{provider_id}`](../03-specs/04-model-gateway.md#delete-apiv1platformmodel-providersprovider_id) | `models:manage` | 4. Registry API (served by `api`) |
| GET | [`/api/v1/platform/models`](../03-specs/04-model-gateway.md#get-apiv1platformmodels) | `models:manage` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/platform/models`](../03-specs/04-model-gateway.md#post-apiv1platformmodels) | `models:manage` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/platform/models/{model_id}`](../03-specs/04-model-gateway.md#patch-apiv1platformmodelsmodel_id) | `models:manage` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/platform/models/{model_id}`](../03-specs/04-model-gateway.md#delete-apiv1platformmodelsmodel_id) | `models:manage` | 4. Registry API (served by `api`) |
| GET | [`/api/v1/platform/model-aliases`](../03-specs/04-model-gateway.md#get-apiv1platformmodel-aliases) | `models:manage` | 4. Registry API (served by `api`) |
| POST | [`/api/v1/platform/model-aliases`](../03-specs/04-model-gateway.md#post-apiv1platformmodel-aliases) | `models:manage` | 4. Registry API (served by `api`) |
| PATCH | [`/api/v1/platform/model-aliases/{alias_id}`](../03-specs/04-model-gateway.md#patch-apiv1platformmodel-aliasesalias_id) | `models:manage` | 4. Registry API (served by `api`) |
| DELETE | [`/api/v1/platform/model-aliases/{alias_id}`](../03-specs/04-model-gateway.md#delete-apiv1platformmodel-aliasesalias_id) | `models:manage` | 4. Registry API (served by `api`) |

## Spec 05: Agent registry and definitions (`ar_domain.agents`)

Spec: [05-agent-registry.md](../03-specs/05-agent-registry.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/agents`](../03-specs/05-agent-registry.md#get-apiv1agents) | `agents:read` | 3. Public API |
| POST | [`/api/v1/agents`](../03-specs/05-agent-registry.md#post-apiv1agents) | `agents:create` | 3. Public API |
| GET | [`/api/v1/agents/{agent_id}`](../03-specs/05-agent-registry.md#get-apiv1agentsagent_id) | `agents:read` | 3. Public API |
| PATCH | [`/api/v1/agents/{agent_id}`](../03-specs/05-agent-registry.md#patch-apiv1agentsagent_id) | `agents:edit` | 3. Public API |
| DELETE | [`/api/v1/agents/{agent_id}`](../03-specs/05-agent-registry.md#delete-apiv1agentsagent_id) | `agents:read` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:archive`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idarchive) | `agents:read` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:unarchive`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idunarchive) | `agents:read` | 3. Public API |
| GET | [`/api/v1/agents/{agent_id}/versions`](../03-specs/05-agent-registry.md#get-apiv1agentsagent_idversions) | `agents:read` | 3. Public API |
| GET | [`/api/v1/agents/{agent_id}/versions/{version_ref}`](../03-specs/05-agent-registry.md#get-apiv1agentsagent_idversionsversion_ref) | `agents:read` | 3. Public API |
| PUT | [`/api/v1/agents/{agent_id}/versions/draft`](../03-specs/05-agent-registry.md#put-apiv1agentsagent_idversionsdraft) | `agents:edit` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:validate`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idvalidate) | `agents:edit` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:publish`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idpublish) | `agents:publish` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:rollback`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idrollback) | `agents:publish` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:duplicate`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idduplicate) | `agents:create` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:disable`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_iddisable) | `agents:disable` | 3. Public API |
| POST | [`/api/v1/agents/{agent_id}:enable`](../03-specs/05-agent-registry.md#post-apiv1agentsagent_idenable) | `agents:disable` | 3. Public API |
| GET | [`/api/v1/agents/{agent_id}/where-used`](../03-specs/05-agent-registry.md#get-apiv1agentsagent_idwhere-used) | `agents:edit` | 3. Public API |
| POST | [`/api/v1/agents:draft-from-description`](../03-specs/05-agent-registry.md#post-apiv1agentsdraft-from-description) | `agents:create` | 3. Public API |
| PUT | [`/api/v1/me/agent-favourites`](../03-specs/05-agent-registry.md#put-apiv1meagent-favourites) | `agents:read` | 3. Public API |
| POST | [`/api/v1/bundles:import`](../03-specs/05-agent-registry.md#post-apiv1bundlesimport) | `agents:create` | 3. Public API |
| GET | [`/api/v1/bundles:export`](../03-specs/05-agent-registry.md#get-apiv1bundlesexport) | `agents:read` | 3. Public API |

## Spec 06: Conversations, messages and runs API (`ar_domain.conversations`, `ar_domain.runs`)

Spec: [06-conversations-runs.md](../03-specs/06-conversations-runs.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/conversations`](../03-specs/06-conversations-runs.md#get-apiv1conversations) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations`](../03-specs/06-conversations-runs.md#post-apiv1conversations) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/conversations/{conversation_id}`](../03-specs/06-conversations-runs.md#get-apiv1conversationsconversation_id) | `chat:use` | 3. Message posting and run start |
| PATCH | [`/api/v1/conversations/{conversation_id}`](../03-specs/06-conversations-runs.md#patch-apiv1conversationsconversation_id) | `tenant:manage` | 3. Message posting and run start |
| DELETE | [`/api/v1/conversations/{conversation_id}`](../03-specs/06-conversations-runs.md#delete-apiv1conversationsconversation_id) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/conversations/{conversation_id}/messages`](../03-specs/06-conversations-runs.md#get-apiv1conversationsconversation_idmessages) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations/{conversation_id}/messages`](../03-specs/06-conversations-runs.md#post-apiv1conversationsconversation_idmessages) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations/{conversation_id}/messages/{message_id}:regenerate`](../03-specs/06-conversations-runs.md#post-apiv1conversationsconversation_idmessagesmessage_idregenerate) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations/{conversation_id}/messages/{message_id}:edit`](../03-specs/06-conversations-runs.md#post-apiv1conversationsconversation_idmessagesmessage_idedit) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations/{conversation_id}/messages/{message_id}:activate`](../03-specs/06-conversations-runs.md#post-apiv1conversationsconversation_idmessagesmessage_idactivate) | `chat:use` | 3. Message posting and run start |
| PUT | [`/api/v1/messages/{message_id}/feedback`](../03-specs/06-conversations-runs.md#put-apiv1messagesmessage_idfeedback) | `chat:use` | 3. Message posting and run start |
| DELETE | [`/api/v1/messages/{message_id}/feedback`](../03-specs/06-conversations-runs.md#delete-apiv1messagesmessage_idfeedback) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/conversations/{conversation_id}/events`](../03-specs/06-conversations-runs.md#get-apiv1conversationsconversation_idevents) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/conversations/{conversation_id}/shares`](../03-specs/06-conversations-runs.md#get-apiv1conversationsconversation_idshares) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/conversations/{conversation_id}/shares`](../03-specs/06-conversations-runs.md#post-apiv1conversationsconversation_idshares) | `chat:use` | 3. Message posting and run start |
| DELETE | [`/api/v1/conversations/{conversation_id}/shares/{principal_type}/{principal_id}`](../03-specs/06-conversations-runs.md#delete-apiv1conversationsconversation_idsharesprincipal_typeprincipal_id) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/conversations/{conversation_id}/export`](../03-specs/06-conversations-runs.md#get-apiv1conversationsconversation_idexport) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/runs`](../03-specs/06-conversations-runs.md#post-apiv1runs) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/runs`](../03-specs/06-conversations-runs.md#get-apiv1runs) | `conversations:read_all` | 3. Message posting and run start |
| GET | [`/api/v1/runs/{run_id}`](../03-specs/06-conversations-runs.md#get-apiv1runsrun_id) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/runs/{run_id}/steps`](../03-specs/06-conversations-runs.md#get-apiv1runsrun_idsteps) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/runs/{run_id}/tool-calls`](../03-specs/06-conversations-runs.md#get-apiv1runsrun_idtool-calls) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/runs/{run_id}/children`](../03-specs/06-conversations-runs.md#get-apiv1runsrun_idchildren) | `chat:use` | 3. Message posting and run start |
| GET | [`/api/v1/runs/{run_id}/events`](../03-specs/06-conversations-runs.md#get-apiv1runsrun_idevents) | `chat:use` | 3. Message posting and run start |
| POST | [`/api/v1/runs/{run_id}:cancel`](../03-specs/06-conversations-runs.md#post-apiv1runsrun_idcancel) | `agents:manage_all` | 3. Message posting and run start |
| POST | [`/api/v1/runs/{run_id}:input`](../03-specs/06-conversations-runs.md#post-apiv1runsrun_idinput) | `chat:use` | 3. Message posting and run start |

## Spec 08: Tool registry, data connections and MCP host (`ar_domain.tools`, `mcp-gateway`)

Spec: [08-tool-registry-mcp.md](../03-specs/08-tool-registry-mcp.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/tool-servers`](../03-specs/08-tool-registry-mcp.md#get-apiv1tool-servers) | `tools:read` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-servers) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tool-servers/{server_id}`](../03-specs/08-tool-registry-mcp.md#get-apiv1tool-serversserver_id) | `tools:read` | 3. Public API (served by `api`) |
| PATCH | [`/api/v1/tool-servers/{server_id}`](../03-specs/08-tool-registry-mcp.md#patch-apiv1tool-serversserver_id) | `tools:create` | 3. Public API (served by `api`) |
| DELETE | [`/api/v1/tool-servers/{server_id}`](../03-specs/08-tool-registry-mcp.md#delete-apiv1tool-serversserver_id) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tool-servers/{server_id}/versions`](../03-specs/08-tool-registry-mcp.md#get-apiv1tool-serversserver_idversions) | `tools:read` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}/versions`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idversions) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tool-servers/{server_id}/versions/{version_id}`](../03-specs/08-tool-registry-mcp.md#get-apiv1tool-serversserver_idversionsversion_id) | `tools:read` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}/versions/{version_id}:discover`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idversionsversion_iddiscover) | `tools:create` | 3. Public API (served by `api`) |
| PATCH | [`/api/v1/tool-servers/{server_id}/versions/{version_id}/tools/{tool_version_id}`](../03-specs/08-tool-registry-mcp.md#patch-apiv1tool-serversserver_idversionsversion_idtoolstool_version_id) | `tools:create` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}/versions/{version_id}:submit`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idversionsversion_idsubmit) | `tools:create` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}/versions/{version_id}:approve`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idversionsversion_idapprove) | `tools:review` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}/versions/{version_id}:reject`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idversionsversion_idreject) | `tools:review` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}:deprecate`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_iddeprecate) | `tools:create` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}:disable`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_iddisable) | `tools:disable` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tool-servers/{server_id}:enable`](../03-specs/08-tool-registry-mcp.md#post-apiv1tool-serversserver_idenable) | `tools:disable` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tools`](../03-specs/08-tool-registry-mcp.md#get-apiv1tools) | `tools:read` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tools/{tool_id}`](../03-specs/08-tool-registry-mcp.md#get-apiv1toolstool_id) | `tools:read` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tools/{tool_id}:disable`](../03-specs/08-tool-registry-mcp.md#post-apiv1toolstool_iddisable) | `tools:disable` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tools/{tool_id}:enable`](../03-specs/08-tool-registry-mcp.md#post-apiv1toolstool_idenable) | `tools:disable` | 3. Public API (served by `api`) |
| POST | [`/api/v1/tools/{tool_id}:test`](../03-specs/08-tool-registry-mcp.md#post-apiv1toolstool_idtest) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/tool-calls`](../03-specs/08-tool-registry-mcp.md#get-apiv1tool-calls) | `audit:read` | 3. Public API (served by `api`) |
| GET | [`/api/v1/data-connections`](../03-specs/08-tool-registry-mcp.md#get-apiv1data-connections) | `tools:read` | 3. Public API (served by `api`) |
| POST | [`/api/v1/data-connections`](../03-specs/08-tool-registry-mcp.md#post-apiv1data-connections) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/data-connections/{connection_id}`](../03-specs/08-tool-registry-mcp.md#get-apiv1data-connectionsconnection_id) | `tools:read` | 3. Public API (served by `api`) |
| PATCH | [`/api/v1/data-connections/{connection_id}`](../03-specs/08-tool-registry-mcp.md#patch-apiv1data-connectionsconnection_id) | `tools:create` | 3. Public API (served by `api`) |
| DELETE | [`/api/v1/data-connections/{connection_id}`](../03-specs/08-tool-registry-mcp.md#delete-apiv1data-connectionsconnection_id) | `tools:create` | 3. Public API (served by `api`) |
| POST | [`/api/v1/data-connections/{connection_id}:test`](../03-specs/08-tool-registry-mcp.md#post-apiv1data-connectionsconnection_idtest) | `tools:create` | 3. Public API (served by `api`) |
| GET | [`/api/v1/data-connections/{connection_id}/schema`](../03-specs/08-tool-registry-mcp.md#get-apiv1data-connectionsconnection_idschema) | `tools:read` | 3. Public API (served by `api`) |

## Spec 09: Policy and approvals (`ar_domain.policy`, `ar_domain.approvals`, `opa`)

Spec: [09-policy-approvals.md](../03-specs/09-policy-approvals.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/policies`](../03-specs/09-policy-approvals.md#get-apiv1policies) | `policies:read` | 4. Policy API |
| POST | [`/api/v1/policies`](../03-specs/09-policy-approvals.md#post-apiv1policies) | `policies:manage` | 4. Policy API |
| GET | [`/api/v1/policies/{policy_id}`](../03-specs/09-policy-approvals.md#get-apiv1policiespolicy_id) | `policies:read` | 4. Policy API |
| PATCH | [`/api/v1/policies/{policy_id}`](../03-specs/09-policy-approvals.md#patch-apiv1policiespolicy_id) | `policies:manage` | 4. Policy API |
| DELETE | [`/api/v1/policies/{policy_id}`](../03-specs/09-policy-approvals.md#delete-apiv1policiespolicy_id) | `policies:manage` | 4. Policy API |
| GET | [`/api/v1/policies/{policy_id}/versions`](../03-specs/09-policy-approvals.md#get-apiv1policiespolicy_idversions) | `policies:read` | 4. Policy API |
| POST | [`/api/v1/policies/{policy_id}/versions`](../03-specs/09-policy-approvals.md#post-apiv1policiespolicy_idversions) | `policies:manage` | 4. Policy API |
| POST | [`/api/v1/policies/{policy_id}:activate`](../03-specs/09-policy-approvals.md#post-apiv1policiespolicy_idactivate) | `policies:manage` | 4. Policy API |
| POST | [`/api/v1/policies/{policy_id}:disable`](../03-specs/09-policy-approvals.md#post-apiv1policiespolicy_iddisable) | `policies:manage` | 4. Policy API |
| POST | [`/api/v1/policies:simulate`](../03-specs/09-policy-approvals.md#post-apiv1policiessimulate) | `policies:read` | 4. Policy API |
| GET | [`/api/v1/approvals`](../03-specs/09-policy-approvals.md#get-apiv1approvals) | `approvals:decide` | 5. Approvals API |
| GET | [`/api/v1/approvals/{approval_id}`](../03-specs/09-policy-approvals.md#get-apiv1approvalsapproval_id) | `approvals:decide` | 5. Approvals API |
| POST | [`/api/v1/approvals/{approval_id}:decide`](../03-specs/09-policy-approvals.md#post-apiv1approvalsapproval_iddecide) | `approvals:decide` | 5. Approvals API |
| POST | [`/api/v1/approvals/{approval_id}:cancel`](../03-specs/09-policy-approvals.md#post-apiv1approvalsapproval_idcancel) | `chat:use` | 5. Approvals API |
| GET | [`/api/v1/standing-approvals`](../03-specs/09-policy-approvals.md#get-apiv1standing-approvals) | `approvals:grant_standing` | 5. Approvals API |
| POST | [`/api/v1/standing-approvals`](../03-specs/09-policy-approvals.md#post-apiv1standing-approvals) | `approvals:grant_standing` | 5. Approvals API |
| POST | [`/api/v1/standing-approvals/{standing_approval_id}:revoke`](../03-specs/09-policy-approvals.md#post-apiv1standing-approvalsstanding_approval_idrevoke) | `approvals:grant_standing` | 5. Approvals API |

## Spec 10: Knowledge (`ar_domain.knowledge`, `ingest-worker`)

Spec: [10-knowledge.md](../03-specs/10-knowledge.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/knowledge/collections`](../03-specs/10-knowledge.md#get-apiv1knowledgecollections) | `knowledge:read` | 3. Public API |
| POST | [`/api/v1/knowledge/collections`](../03-specs/10-knowledge.md#post-apiv1knowledgecollections) | `knowledge:manage` | 3. Public API |
| GET | [`/api/v1/knowledge/collections/{collection_id}`](../03-specs/10-knowledge.md#get-apiv1knowledgecollectionscollection_id) | object-level (see spec) | 3. Public API |
| PATCH | [`/api/v1/knowledge/collections/{collection_id}`](../03-specs/10-knowledge.md#patch-apiv1knowledgecollectionscollection_id) | object-level (see spec) | 3. Public API |
| DELETE | [`/api/v1/knowledge/collections/{collection_id}`](../03-specs/10-knowledge.md#delete-apiv1knowledgecollectionscollection_id) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/collections/{collection_id}:reindex`](../03-specs/10-knowledge.md#post-apiv1knowledgecollectionscollection_idreindex) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/collections/{collection_id}/sources`](../03-specs/10-knowledge.md#get-apiv1knowledgecollectionscollection_idsources) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/collections/{collection_id}/sources`](../03-specs/10-knowledge.md#post-apiv1knowledgecollectionscollection_idsources) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/sources/{source_id}`](../03-specs/10-knowledge.md#get-apiv1knowledgesourcessource_id) | object-level (see spec) | 3. Public API |
| PATCH | [`/api/v1/knowledge/sources/{source_id}`](../03-specs/10-knowledge.md#patch-apiv1knowledgesourcessource_id) | object-level (see spec) | 3. Public API |
| DELETE | [`/api/v1/knowledge/sources/{source_id}`](../03-specs/10-knowledge.md#delete-apiv1knowledgesourcessource_id) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/sources/{source_id}:test`](../03-specs/10-knowledge.md#post-apiv1knowledgesourcessource_idtest) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/sources/{source_id}:sync`](../03-specs/10-knowledge.md#post-apiv1knowledgesourcessource_idsync) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/sources/{source_id}:pause`](../03-specs/10-knowledge.md#post-apiv1knowledgesourcessource_idpause) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/sources/{source_id}:resume`](../03-specs/10-knowledge.md#post-apiv1knowledgesourcessource_idresume) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/collections/{collection_id}/documents`](../03-specs/10-knowledge.md#get-apiv1knowledgecollectionscollection_iddocuments) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/collections/{collection_id}/documents`](../03-specs/10-knowledge.md#post-apiv1knowledgecollectionscollection_iddocuments) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/documents/{document_id}`](../03-specs/10-knowledge.md#get-apiv1knowledgedocumentsdocument_id) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/documents/{document_id}/chunks`](../03-specs/10-knowledge.md#get-apiv1knowledgedocumentsdocument_idchunks) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/documents/{document_id}:reingest`](../03-specs/10-knowledge.md#post-apiv1knowledgedocumentsdocument_idreingest) | object-level (see spec) | 3. Public API |
| DELETE | [`/api/v1/knowledge/documents/{document_id}`](../03-specs/10-knowledge.md#delete-apiv1knowledgedocumentsdocument_id) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/collections/{collection_id}/jobs`](../03-specs/10-knowledge.md#get-apiv1knowledgecollectionscollection_idjobs) | object-level (see spec) | 3. Public API |
| GET | [`/api/v1/knowledge/jobs/{job_id}`](../03-specs/10-knowledge.md#get-apiv1knowledgejobsjob_id) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/jobs/{job_id}:cancel`](../03-specs/10-knowledge.md#post-apiv1knowledgejobsjob_idcancel) | object-level (see spec) | 3. Public API |
| POST | [`/api/v1/knowledge/search`](../03-specs/10-knowledge.md#post-apiv1knowledgesearch) | `knowledge:read` | 3. Public API |

## Spec 11: Memory (`ar_domain.memory`)

Spec: [11-memory.md](../03-specs/11-memory.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/memory`](../03-specs/11-memory.md#get-apiv1memory) | any signed-in principal | 5. Public API |
| PATCH | [`/api/v1/memory/settings`](../03-specs/11-memory.md#patch-apiv1memorysettings) | any signed-in principal | 5. Public API |
| POST | [`/api/v1/memory`](../03-specs/11-memory.md#post-apiv1memory) | any signed-in principal | 5. Public API |
| PATCH | [`/api/v1/memory/{fact_id}`](../03-specs/11-memory.md#patch-apiv1memoryfact_id) | any signed-in principal | 5. Public API |
| DELETE | [`/api/v1/memory/{fact_id}`](../03-specs/11-memory.md#delete-apiv1memoryfact_id) | any signed-in principal | 5. Public API |
| DELETE | [`/api/v1/memory`](../03-specs/11-memory.md#delete-apiv1memory) | any signed-in principal | 5. Public API |
| GET | [`/api/v1/agents/{agent_id}/memory`](../03-specs/11-memory.md#get-apiv1agentsagent_idmemory) | `memory:manage_agent` | 5. Public API |
| POST | [`/api/v1/agents/{agent_id}/memory`](../03-specs/11-memory.md#post-apiv1agentsagent_idmemory) | object-level (see spec) | 5. Public API |
| POST | [`/api/v1/agents/{agent_id}/memory/{fact_id}:approve`](../03-specs/11-memory.md#post-apiv1agentsagent_idmemoryfact_idapprove) | object-level (see spec) | 5. Public API |
| POST | [`/api/v1/agents/{agent_id}/memory/{fact_id}:reject`](../03-specs/11-memory.md#post-apiv1agentsagent_idmemoryfact_idreject) | object-level (see spec) | 5. Public API |
| PATCH | [`/api/v1/agents/{agent_id}/memory/{fact_id}`](../03-specs/11-memory.md#patch-apiv1agentsagent_idmemoryfact_id) | object-level (see spec) | 5. Public API |
| DELETE | [`/api/v1/agents/{agent_id}/memory/{fact_id}`](../03-specs/11-memory.md#delete-apiv1agentsagent_idmemoryfact_id) | object-level (see spec) | 5. Public API |
| GET | [`/api/v1/teams/{team_id}/memory`](../03-specs/11-memory.md#get-apiv1teamsteam_idmemory) | object-level (see spec) | 5. Public API |
| POST | [`/api/v1/teams/{team_id}/memory`](../03-specs/11-memory.md#post-apiv1teamsteam_idmemory) | object-level (see spec) | 5. Public API |
| DELETE | [`/api/v1/teams/{team_id}/memory/{fact_id}`](../03-specs/11-memory.md#delete-apiv1teamsteam_idmemoryfact_id) | object-level (see spec) | 5. Public API |

## Spec 12: Sandboxes, computer and browser (`sandbox-manager`, `sandbox-agent`)

Spec: [12-sandbox-manager.md](../03-specs/12-sandbox-manager.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/sandbox-templates`](../03-specs/12-sandbox-manager.md#get-apiv1sandbox-templates) | `sandboxes:manage` | 6. Public API (served by `api`) |
| POST | [`/api/v1/sandbox-templates`](../03-specs/12-sandbox-manager.md#post-apiv1sandbox-templates) | `sandboxes:manage` | 6. Public API (served by `api`) |
| PATCH | [`/api/v1/sandbox-templates/{template_id}`](../03-specs/12-sandbox-manager.md#patch-apiv1sandbox-templatestemplate_id) | `sandboxes:manage` | 6. Public API (served by `api`) |
| DELETE | [`/api/v1/sandbox-templates/{template_id}`](../03-specs/12-sandbox-manager.md#delete-apiv1sandbox-templatestemplate_id) | `sandboxes:manage` | 6. Public API (served by `api`) |
| GET | [`/api/v1/sandboxes`](../03-specs/12-sandbox-manager.md#get-apiv1sandboxes) | `sandboxes:manage` | 6. Public API (served by `api`) |
| GET | [`/api/v1/sandboxes/{sandbox_id}`](../03-specs/12-sandbox-manager.md#get-apiv1sandboxessandbox_id) | `chat:use` | 6. Public API (served by `api`) |
| POST | [`/api/v1/sandboxes/{sandbox_id}:terminate`](../03-specs/12-sandbox-manager.md#post-apiv1sandboxessandbox_idterminate) | `chat:use` | 6. Public API (served by `api`) |
| GET | [`/api/v1/conversations/{conversation_id}/sandbox`](../03-specs/12-sandbox-manager.md#get-apiv1conversationsconversation_idsandbox) | `chat:use` | 6. Public API (served by `api`) |
| GET | [`/api/v1/sandboxes/{sandbox_id}/files`](../03-specs/12-sandbox-manager.md#get-apiv1sandboxessandbox_idfiles) | `chat:use` | 6. Public API (served by `api`) |
| GET | [`/api/v1/sandboxes/{sandbox_id}/files/content`](../03-specs/12-sandbox-manager.md#get-apiv1sandboxessandbox_idfilescontent) | `chat:use` | 6. Public API (served by `api`) |
| POST | [`/api/v1/sandboxes/{sandbox_id}/files:export`](../03-specs/12-sandbox-manager.md#post-apiv1sandboxessandbox_idfilesexport) | `chat:use` | 6. Public API (served by `api`) |

## Spec 13: Files and artifacts (`ar_domain.files`)

Spec: [13-files-artifacts.md](../03-specs/13-files-artifacts.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| POST | [`/api/v1/files`](../03-specs/13-files-artifacts.md#post-apiv1files) | `chat:use` | 4. Public API |
| POST | [`/api/v1/files/{file_id}:complete`](../03-specs/13-files-artifacts.md#post-apiv1filesfile_idcomplete) | object-level (see spec) | 4. Public API |
| POST | [`/api/v1/files:upload`](../03-specs/13-files-artifacts.md#post-apiv1filesupload) | object-level (see spec) | 4. Public API |
| GET | [`/api/v1/files`](../03-specs/13-files-artifacts.md#get-apiv1files) | object-level (see spec) | 4. Public API |
| GET | [`/api/v1/files/{file_id}`](../03-specs/13-files-artifacts.md#get-apiv1filesfile_id) | object-level (see spec) | 4. Public API |
| GET | [`/api/v1/files/{file_id}/content`](../03-specs/13-files-artifacts.md#get-apiv1filesfile_idcontent) | object-level (see spec) | 4. Public API |
| GET | [`/api/v1/files/{file_id}/thumbnail`](../03-specs/13-files-artifacts.md#get-apiv1filesfile_idthumbnail) | object-level (see spec) | 4. Public API |
| DELETE | [`/api/v1/files/{file_id}`](../03-specs/13-files-artifacts.md#delete-apiv1filesfile_id) | object-level (see spec) | 4. Public API |

## Spec 14: Skills (`ar_domain.skills`)

Spec: [14-skills.md](../03-specs/14-skills.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/skills`](../03-specs/14-skills.md#get-apiv1skills) | `skills:read` | 3. Public API |
| POST | [`/api/v1/skills`](../03-specs/14-skills.md#post-apiv1skills) | `skills:create` | 3. Public API |
| GET | [`/api/v1/skills/{skill_id}`](../03-specs/14-skills.md#get-apiv1skillsskill_id) | `skills:read` | 3. Public API |
| PATCH | [`/api/v1/skills/{skill_id}`](../03-specs/14-skills.md#patch-apiv1skillsskill_id) | `skills:read` | 3. Public API |
| POST | [`/api/v1/skills/{skill_id}:publish`](../03-specs/14-skills.md#post-apiv1skillsskill_idpublish) | `skills:read` | 3. Public API |
| POST | [`/api/v1/skills/{skill_id}:archive`](../03-specs/14-skills.md#post-apiv1skillsskill_idarchive) | `skills:read` | 3. Public API |
| GET | [`/api/v1/skills/{skill_id}/versions`](../03-specs/14-skills.md#get-apiv1skillsskill_idversions) | `skills:read` | 3. Public API |
| GET | [`/api/v1/skills/{skill_id}/versions/{version}`](../03-specs/14-skills.md#get-apiv1skillsskill_idversionsversion) | `skills:read` | 3. Public API |
| GET | [`/api/v1/skills/{skill_id}/where-used`](../03-specs/14-skills.md#get-apiv1skillsskill_idwhere-used) | `skills:read` | 3. Public API |
| POST | [`/api/v1/skills/{skill_id}:republish-dependants`](../03-specs/14-skills.md#post-apiv1skillsskill_idrepublish-dependants) | `skills:read` | 3. Public API |

## Spec 15: Routines and triggers (`ar_domain.routines`)

Spec: [15-routines-triggers.md](../03-specs/15-routines-triggers.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/routines`](../03-specs/15-routines-triggers.md#get-apiv1routines) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines`](../03-specs/15-routines-triggers.md#post-apiv1routines) | `routines:create` | 5. Public API |
| GET | [`/api/v1/routines/{routine_id}`](../03-specs/15-routines-triggers.md#get-apiv1routinesroutine_id) | `routines:create` | 5. Public API |
| PATCH | [`/api/v1/routines/{routine_id}`](../03-specs/15-routines-triggers.md#patch-apiv1routinesroutine_id) | `routines:create` | 5. Public API |
| DELETE | [`/api/v1/routines/{routine_id}`](../03-specs/15-routines-triggers.md#delete-apiv1routinesroutine_id) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines/{routine_id}:run`](../03-specs/15-routines-triggers.md#post-apiv1routinesroutine_idrun) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines/{routine_id}:pause`](../03-specs/15-routines-triggers.md#post-apiv1routinesroutine_idpause) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines/{routine_id}:resume`](../03-specs/15-routines-triggers.md#post-apiv1routinesroutine_idresume) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines/{routine_id}:transfer`](../03-specs/15-routines-triggers.md#post-apiv1routinesroutine_idtransfer) | `routines:manage_all` | 5. Public API |
| POST | [`/api/v1/routines/{routine_id}:rotate-webhook-secret`](../03-specs/15-routines-triggers.md#post-apiv1routinesroutine_idrotate-webhook-secret) | `routines:create` | 5. Public API |
| GET | [`/api/v1/routines/{routine_id}/events`](../03-specs/15-routines-triggers.md#get-apiv1routinesroutine_idevents) | `routines:create` | 5. Public API |
| POST | [`/api/v1/routines:preview-schedule`](../03-specs/15-routines-triggers.md#post-apiv1routinespreview-schedule) | `routines:create` | 5. Public API |
| POST | [`/api/v1/hooks/routines/{token}`](../03-specs/15-routines-triggers.md#post-apiv1hooksroutinestoken) | public | 5. Public API |

## Spec 16: Channels (`channels`, `ar_domain.channels`)

Spec: [16-channels.md](../03-specs/16-channels.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| POST | [`/channels/slack/events`](../03-specs/16-channels.md#post-channelsslackevents) | provider request signature | 2. Public endpoints on `channels` (ingress path prefix `/channels`) |
| POST | [`/channels/slack/interactions`](../03-specs/16-channels.md#post-channelsslackinteractions) | provider request signature | 2. Public endpoints on `channels` (ingress path prefix `/channels`) |
| POST | [`/channels/slack/commands`](../03-specs/16-channels.md#post-channelsslackcommands) | provider request signature | 2. Public endpoints on `channels` (ingress path prefix `/channels`) |
| POST | [`/channels/teams/messages`](../03-specs/16-channels.md#post-channelsteamsmessages) | provider request signature | 2. Public endpoints on `channels` (ingress path prefix `/channels`) |
| GET | [`/api/v1/channel-integrations`](../03-specs/16-channels.md#get-apiv1channel-integrations) | `channels:manage` | 5. Integration management API (served by `api`) |
| POST | [`/api/v1/channel-integrations`](../03-specs/16-channels.md#post-apiv1channel-integrations) | `channels:manage` | 5. Integration management API (served by `api`) |
| GET | [`/api/v1/channel-integrations/{integration_id}`](../03-specs/16-channels.md#get-apiv1channel-integrationsintegration_id) | `channels:manage` | 5. Integration management API (served by `api`) |
| PATCH | [`/api/v1/channel-integrations/{integration_id}`](../03-specs/16-channels.md#patch-apiv1channel-integrationsintegration_id) | `channels:manage` | 5. Integration management API (served by `api`) |
| DELETE | [`/api/v1/channel-integrations/{integration_id}`](../03-specs/16-channels.md#delete-apiv1channel-integrationsintegration_id) | `channels:manage` | 5. Integration management API (served by `api`) |
| POST | [`/api/v1/channel-integrations/{integration_id}:test`](../03-specs/16-channels.md#post-apiv1channel-integrationsintegration_idtest) | `channels:manage` | 5. Integration management API (served by `api`) |
| GET | [`/api/v1/channel-integrations/{integration_id}/manifest`](../03-specs/16-channels.md#get-apiv1channel-integrationsintegration_idmanifest) | `users:read` | 5. Integration management API (served by `api`) |
| GET | [`/api/v1/channel-integrations/{integration_id}/identities`](../03-specs/16-channels.md#get-apiv1channel-integrationsintegration_ididentities) | `channels:manage` | 5. Integration management API (served by `api`) |
| DELETE | [`/api/v1/channel-integrations/{integration_id}/identities/{identity_id}`](../03-specs/16-channels.md#delete-apiv1channel-integrationsintegration_ididentitiesidentity_id) | `channels:manage` | 5. Integration management API (served by `api`) |
| GET | [`/api/v1/me/channel-identities`](../03-specs/16-channels.md#get-apiv1mechannel-identities) | `channels:manage` | 5. Integration management API (served by `api`) |
| POST | [`/api/v1/me/channel-identities:link`](../03-specs/16-channels.md#post-apiv1mechannel-identitieslink) | `channels:manage` | 5. Integration management API (served by `api`) |
| DELETE | [`/api/v1/me/channel-identities/{identity_id}`](../03-specs/16-channels.md#delete-apiv1mechannel-identitiesidentity_id) | `channels:manage` | 5. Integration management API (served by `api`) |
| POST | [`/api/v1/openai/chat/completions`](../03-specs/16-channels.md#post-apiv1openaichatcompletions) | object-level (see spec) | 6. API channel |
| GET | [`/api/v1/openai/models`](../03-specs/16-channels.md#get-apiv1openaimodels) | object-level (see spec) | 6. API channel |
| POST | [`/api/v1/widget/sessions`](../03-specs/16-channels.md#post-apiv1widgetsessions) | host-signed widget JWT | 7. Web widget (feature `widget`) |

## Spec 17: Audit, usage metering, quotas and retention (`ar_domain.audit`, `ar_domain.usage`)

Spec: [17-audit-usage-metering.md](../03-specs/17-audit-usage-metering.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/audit-events`](../03-specs/17-audit-usage-metering.md#get-apiv1audit-events) | `audit:read` | 1. Audit |
| GET | [`/api/v1/audit-events/{event_id}`](../03-specs/17-audit-usage-metering.md#get-apiv1audit-eventsevent_id) | `audit:read` | 1. Audit |
| POST | [`/api/v1/audit-events:verify`](../03-specs/17-audit-usage-metering.md#post-apiv1audit-eventsverify) | `audit:read` | 1. Audit |
| POST | [`/api/v1/audit-exports`](../03-specs/17-audit-usage-metering.md#post-apiv1audit-exports) | `audit:export` | 1. Audit |
| GET | [`/api/v1/audit-exports/{export_id}`](../03-specs/17-audit-usage-metering.md#get-apiv1audit-exportsexport_id) | `audit:read` | 1. Audit |
| GET | [`/api/v1/usage/summary`](../03-specs/17-audit-usage-metering.md#get-apiv1usagesummary) | `usage:read` | 2. Usage metering |
| GET | [`/api/v1/usage/export`](../03-specs/17-audit-usage-metering.md#get-apiv1usageexport) | `usage:read` | 2. Usage metering |
| GET | [`/api/v1/me/usage`](../03-specs/17-audit-usage-metering.md#get-apiv1meusage) | any signed-in principal | 2. Usage metering |
| GET | [`/api/v1/quotas`](../03-specs/17-audit-usage-metering.md#get-apiv1quotas) | `usage:read` | 2. Usage metering |
| POST | [`/api/v1/quotas`](../03-specs/17-audit-usage-metering.md#post-apiv1quotas) | `quotas:manage` | 2. Usage metering |
| PATCH | [`/api/v1/quotas/{quota_id}`](../03-specs/17-audit-usage-metering.md#patch-apiv1quotasquota_id) | object-level (see spec) | 2. Usage metering |
| DELETE | [`/api/v1/quotas/{quota_id}`](../03-specs/17-audit-usage-metering.md#delete-apiv1quotasquota_id) | object-level (see spec) | 2. Usage metering |
| GET | [`/api/v1/platform/usage`](../03-specs/17-audit-usage-metering.md#get-apiv1platformusage) | platform admin (SaaS) | 2. Usage metering |
| GET | [`/api/v1/platform/usage/export`](../03-specs/17-audit-usage-metering.md#get-apiv1platformusageexport) | platform admin (SaaS) | 2. Usage metering |

## Spec 18: Observability and evaluation (`ar_common.telemetry`, `ar_domain.evals`)

Spec: [18-observability-eval.md](../03-specs/18-observability-eval.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/observability/overview`](../03-specs/18-observability-eval.md#get-apiv1observabilityoverview) | `usage:read` | 3. In-product observability API |
| GET | [`/api/v1/platform/health`](../03-specs/18-observability-eval.md#get-apiv1platformhealth) | platform admin (SaaS) | 3. In-product observability API |
| GET | [`/api/v1/eval-suites`](../03-specs/18-observability-eval.md#get-apiv1eval-suites) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-suites`](../03-specs/18-observability-eval.md#post-apiv1eval-suites) | `evals:manage` | 4. Evaluation |
| GET | [`/api/v1/eval-suites/{suite_id}`](../03-specs/18-observability-eval.md#get-apiv1eval-suitessuite_id) | `evals:manage` | 4. Evaluation |
| PATCH | [`/api/v1/eval-suites/{suite_id}`](../03-specs/18-observability-eval.md#patch-apiv1eval-suitessuite_id) | `evals:manage` | 4. Evaluation |
| DELETE | [`/api/v1/eval-suites/{suite_id}`](../03-specs/18-observability-eval.md#delete-apiv1eval-suitessuite_id) | `evals:manage` | 4. Evaluation |
| GET | [`/api/v1/eval-suites/{suite_id}/cases`](../03-specs/18-observability-eval.md#get-apiv1eval-suitessuite_idcases) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-suites/{suite_id}/cases`](../03-specs/18-observability-eval.md#post-apiv1eval-suitessuite_idcases) | `evals:manage` | 4. Evaluation |
| PATCH | [`/api/v1/eval-suites/{suite_id}/cases/{case_id}`](../03-specs/18-observability-eval.md#patch-apiv1eval-suitessuite_idcasescase_id) | `evals:manage` | 4. Evaluation |
| DELETE | [`/api/v1/eval-suites/{suite_id}/cases/{case_id}`](../03-specs/18-observability-eval.md#delete-apiv1eval-suitessuite_idcasescase_id) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-suites/{suite_id}/cases:import`](../03-specs/18-observability-eval.md#post-apiv1eval-suitessuite_idcasesimport) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-suites/{suite_id}/cases:from-conversation`](../03-specs/18-observability-eval.md#post-apiv1eval-suitessuite_idcasesfrom-conversation) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-suites/{suite_id}:run`](../03-specs/18-observability-eval.md#post-apiv1eval-suitessuite_idrun) | `evals:run` | 4. Evaluation |
| GET | [`/api/v1/eval-runs`](../03-specs/18-observability-eval.md#get-apiv1eval-runs) | `evals:manage` | 4. Evaluation |
| GET | [`/api/v1/eval-runs/{eval_run_id}`](../03-specs/18-observability-eval.md#get-apiv1eval-runseval_run_id) | `evals:manage` | 4. Evaluation |
| GET | [`/api/v1/eval-runs/{eval_run_id}/results`](../03-specs/18-observability-eval.md#get-apiv1eval-runseval_run_idresults) | `evals:manage` | 4. Evaluation |
| POST | [`/api/v1/eval-runs/{eval_run_id}:cancel`](../03-specs/18-observability-eval.md#post-apiv1eval-runseval_run_idcancel) | `evals:manage` | 4. Evaluation |
| GET | [`/api/v1/feedback`](../03-specs/18-observability-eval.md#get-apiv1feedback) | `evals:manage` | 4. Evaluation |

## Spec 20: Domain events, notifications and outbound webhooks (`ar_domain.events`)

Spec: [20-notifications-events.md](../03-specs/20-notifications-events.md)

| Method | Path | Permission | Section |
|---|---|---|---|
| GET | [`/api/v1/notifications`](../03-specs/20-notifications-events.md#get-apiv1notifications) | object-level (see spec) | 2. Notifications |
| POST | [`/api/v1/notifications/{notification_id}:read`](../03-specs/20-notifications-events.md#post-apiv1notificationsnotification_idread) | object-level (see spec) | 2. Notifications |
| POST | [`/api/v1/notifications:read-all`](../03-specs/20-notifications-events.md#post-apiv1notificationsread-all) | object-level (see spec) | 2. Notifications |
| GET | [`/api/v1/notifications/events`](../03-specs/20-notifications-events.md#get-apiv1notificationsevents) | object-level (see spec) | 2. Notifications |
| GET | [`/api/v1/webhooks`](../03-specs/20-notifications-events.md#get-apiv1webhooks) | `webhooks:manage` | 3. Outbound webhooks |
| POST | [`/api/v1/webhooks`](../03-specs/20-notifications-events.md#post-apiv1webhooks) | `webhooks:manage` | 3. Outbound webhooks |
| GET | [`/api/v1/webhooks/{webhook_id}`](../03-specs/20-notifications-events.md#get-apiv1webhookswebhook_id) | `webhooks:manage` | 3. Outbound webhooks |
| PATCH | [`/api/v1/webhooks/{webhook_id}`](../03-specs/20-notifications-events.md#patch-apiv1webhookswebhook_id) | `webhooks:manage` | 3. Outbound webhooks |
| DELETE | [`/api/v1/webhooks/{webhook_id}`](../03-specs/20-notifications-events.md#delete-apiv1webhookswebhook_id) | `webhooks:manage` | 3. Outbound webhooks |
| POST | [`/api/v1/webhooks/{webhook_id}:rotate-secret`](../03-specs/20-notifications-events.md#post-apiv1webhookswebhook_idrotate-secret) | `webhooks:manage` | 3. Outbound webhooks |
| POST | [`/api/v1/webhooks/{webhook_id}:test`](../03-specs/20-notifications-events.md#post-apiv1webhookswebhook_idtest) | `webhooks:manage` | 3. Outbound webhooks |
| GET | [`/api/v1/webhooks/{webhook_id}/deliveries`](../03-specs/20-notifications-events.md#get-apiv1webhookswebhook_iddeliveries) | `webhooks:manage` | 3. Outbound webhooks |
| POST | [`/api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}:redeliver`](../03-specs/20-notifications-events.md#post-apiv1webhookswebhook_iddeliveriesdelivery_idredeliver) | `webhooks:manage` | 3. Outbound webhooks |
| POST | [`/api/v1/tenant/run-callback-secret:rotate`](../03-specs/20-notifications-events.md#post-apiv1tenantrun-callback-secretrotate) | `tenant:manage` | 3. Outbound webhooks |

## Records, grounding, reviews and the GRC pack
Indexed from the `####` headings added with the records specs and the GRC pack. The rows above are unchanged.

### Spec 05 content packs and builder

Spec: [03-specs/05-agent-registry.md](../03-specs/05-agent-registry.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/content-packs`](../03-specs/05-agent-registry.md#get-apiv1content-packs) | `agents:read` |
| POST | [`/api/v1/content-packs:install`](../03-specs/05-agent-registry.md#post-apiv1content-packsinstall) | `packs:manage` |
| GET | [`/api/v1/content-packs/{pack_id}`](../03-specs/05-agent-registry.md#get-apiv1content-packspack_id) | `agents:read` |
| POST | [`/api/v1/content-packs/{pack_id}:upgrade`](../03-specs/05-agent-registry.md#post-apiv1content-packspack_idupgrade) | `packs:manage` |
| POST | [`/api/v1/content-packs/{pack_id}:uninstall`](../03-specs/05-agent-registry.md#post-apiv1content-packspack_iduninstall) | `packs:manage` |
| POST | [`/api/v1/builder/sessions`](../03-specs/05-agent-registry.md#post-apiv1buildersessions) | `agents:create` |
| GET | [`/api/v1/builder/sessions/{session_id}`](../03-specs/05-agent-registry.md#get-apiv1buildersessionssession_id) | `agents:create` |
| POST | [`/api/v1/builder/sessions/{session_id}/messages`](../03-specs/05-agent-registry.md#post-apiv1buildersessionssession_idmessages) | `agents:create` |
| POST | [`/api/v1/builder/sessions/{session_id}:apply`](../03-specs/05-agent-registry.md#post-apiv1buildersessionssession_idapply) | `agents:create` |

### Spec 07 grounding

Spec: [03-specs/07-agent-runtime.md](../03-specs/07-agent-runtime.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/conversations/{conversation_id}/messages/{message_id}/grounding`](../03-specs/07-agent-runtime.md#get-apiv1conversationsconversation_idmessagesmessage_idgrounding) | see spec |

### Spec 09 reviews and segregation of duties

Spec: [03-specs/09-policy-approvals.md](../03-specs/09-policy-approvals.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/review-queues`](../03-specs/09-policy-approvals.md#get-apiv1review-queues) | `reviews:read` |
| POST | [`/api/v1/review-queues`](../03-specs/09-policy-approvals.md#post-apiv1review-queues) | `reviews:manage` |
| GET | [`/api/v1/review-queues/{queue_id}`](../03-specs/09-policy-approvals.md#get-apiv1review-queuesqueue_id) | `reviews:read` |
| PATCH | [`/api/v1/review-queues/{queue_id}`](../03-specs/09-policy-approvals.md#patch-apiv1review-queuesqueue_id) | `reviews:manage` |
| DELETE | [`/api/v1/review-queues/{queue_id}`](../03-specs/09-policy-approvals.md#delete-apiv1review-queuesqueue_id) | `reviews:manage` |
| GET | [`/api/v1/review-items`](../03-specs/09-policy-approvals.md#get-apiv1review-items) | object-level (see spec) |
| POST | [`/api/v1/review-items`](../03-specs/09-policy-approvals.md#post-apiv1review-items) | Any principal who can read the subject |
| GET | [`/api/v1/review-items/{review_item_id}`](../03-specs/09-policy-approvals.md#get-apiv1review-itemsreview_item_id) | object-level (see spec) |
| POST | [`/api/v1/review-items/{review_item_id}:decide`](../03-specs/09-policy-approvals.md#post-apiv1review-itemsreview_item_iddecide) | see spec |
| POST | [`/api/v1/review-items:bulk-decide`](../03-specs/09-policy-approvals.md#post-apiv1review-itemsbulk-decide) | see spec |
| GET | [`/api/v1/sod-constraints`](../03-specs/09-policy-approvals.md#get-apiv1sod-constraints) | `policies:read` |
| POST | [`/api/v1/sod-constraints`](../03-specs/09-policy-approvals.md#post-apiv1sod-constraints) | `sod:manage` |
| GET | [`/api/v1/sod-constraints/{constraint_id}`](../03-specs/09-policy-approvals.md#get-apiv1sod-constraintsconstraint_id) | `policies:read` |
| PATCH | [`/api/v1/sod-constraints/{constraint_id}`](../03-specs/09-policy-approvals.md#patch-apiv1sod-constraintsconstraint_id) | `sod:manage` |
| DELETE | [`/api/v1/sod-constraints/{constraint_id}`](../03-specs/09-policy-approvals.md#delete-apiv1sod-constraintsconstraint_id) | `sod:manage` |
| POST | [`/api/v1/sod-constraints:check`](../03-specs/09-policy-approvals.md#post-apiv1sod-constraintscheck) | `policies:read` |

### Spec 18 run records

Spec: [03-specs/18-observability-eval.md](../03-specs/18-observability-eval.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/run-records`](../03-specs/18-observability-eval.md#get-apiv1run-records) | `run_records:read` |
| GET | [`/api/v1/run-records/{run_record_id}`](../03-specs/18-observability-eval.md#get-apiv1run-recordsrun_record_id) | `run_records:read` |
| POST | [`/api/v1/run-records/{run_record_id}:replay`](../03-specs/18-observability-eval.md#post-apiv1run-recordsrun_record_idreplay) | `run_records:replay` |
| GET | [`/api/v1/run-records/{run_record_id}/replays/{replay_id}`](../03-specs/18-observability-eval.md#get-apiv1run-recordsrun_record_idreplaysreplay_id) | `run_records:read` |

### Spec 21 records and guests

Spec: [03-specs/21-records-governance.md](../03-specs/21-records-governance.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/evidence`](../03-specs/21-records-governance.md#get-apiv1evidence) | `evidence:read` |
| POST | [`/api/v1/evidence`](../03-specs/21-records-governance.md#post-apiv1evidence) | `evidence:capture` |
| GET | [`/api/v1/evidence/{evidence_item_id}`](../03-specs/21-records-governance.md#get-apiv1evidenceevidence_item_id) | `evidence:read` |
| GET | [`/api/v1/evidence/{evidence_item_id}/content`](../03-specs/21-records-governance.md#get-apiv1evidenceevidence_item_idcontent) | `evidence:export` |
| POST | [`/api/v1/evidence/{evidence_item_id}:verify`](../03-specs/21-records-governance.md#post-apiv1evidenceevidence_item_idverify) | `evidence:read` |
| GET | [`/api/v1/evidence/{evidence_item_id}/custody`](../03-specs/21-records-governance.md#get-apiv1evidenceevidence_item_idcustody) | `evidence:read` |
| GET | [`/api/v1/legal-holds`](../03-specs/21-records-governance.md#get-apiv1legal-holds) | `holds:manage` |
| POST | [`/api/v1/legal-holds`](../03-specs/21-records-governance.md#post-apiv1legal-holds) | `holds:manage` |
| GET | [`/api/v1/legal-holds/{hold_id}`](../03-specs/21-records-governance.md#get-apiv1legal-holdshold_id) | `holds:manage` |
| POST | [`/api/v1/legal-holds/{hold_id}:release`](../03-specs/21-records-governance.md#post-apiv1legal-holdshold_idrelease) | `holds:manage` |
| GET | [`/api/v1/retention-schedules`](../03-specs/21-records-governance.md#get-apiv1retention-schedules) | `retention:manage` |
| PUT | [`/api/v1/retention-schedules/{record_class}`](../03-specs/21-records-governance.md#put-apiv1retention-schedulesrecord_class) | `retention:manage` |
| GET | [`/api/v1/disposition-certificates`](../03-specs/21-records-governance.md#get-apiv1disposition-certificates) | `audit:read` |
| GET | [`/api/v1/disposition-certificates/{certificate_id}`](../03-specs/21-records-governance.md#get-apiv1disposition-certificatescertificate_id) | `audit:read` |
| GET | [`/api/v1/agent-cards`](../03-specs/21-records-governance.md#get-apiv1agent-cards) | `ai_governance:read` |
| GET | [`/api/v1/agents/{agent_id}/cards`](../03-specs/21-records-governance.md#get-apiv1agentsagent_idcards) | `ai_governance:read` |
| GET | [`/api/v1/agents/{agent_id}/cards/{version}`](../03-specs/21-records-governance.md#get-apiv1agentsagent_idcardsversion) | see spec |
| PATCH | [`/api/v1/agents/{agent_id}/cards/{version}`](../03-specs/21-records-governance.md#patch-apiv1agentsagent_idcardsversion) | `ai_governance:manage` |
| GET | [`/api/v1/ai-incidents`](../03-specs/21-records-governance.md#get-apiv1ai-incidents) | `ai_governance:read` |
| POST | [`/api/v1/ai-incidents`](../03-specs/21-records-governance.md#post-apiv1ai-incidents) | `ai_governance:manage` |
| PATCH | [`/api/v1/ai-incidents/{incident_id}`](../03-specs/21-records-governance.md#patch-apiv1ai-incidentsincident_id) | `ai_governance:manage` |
| GET | [`/api/v1/ai-governance/oversight`](../03-specs/21-records-governance.md#get-apiv1ai-governanceoversight) | `ai_governance:read` |
| POST | [`/api/v1/ai-governance:export`](../03-specs/21-records-governance.md#post-apiv1ai-governanceexport) | `ai_governance:read` |
| GET | [`/api/v1/guests`](../03-specs/21-records-governance.md#get-apiv1guests) | `guests:manage` |
| POST | [`/api/v1/guests`](../03-specs/21-records-governance.md#post-apiv1guests) | `guests:invite` |
| GET | [`/api/v1/guests/{guest_id}`](../03-specs/21-records-governance.md#get-apiv1guestsguest_id) | `guests:manage` |
| POST | [`/api/v1/guests/{guest_id}:revoke`](../03-specs/21-records-governance.md#post-apiv1guestsguest_idrevoke) | `guests:manage` |
| POST | [`/api/v1/guests/{guest_id}/grants`](../03-specs/21-records-governance.md#post-apiv1guestsguest_idgrants) | `guests:manage` |
| DELETE | [`/api/v1/guests/{guest_id}/grants/{grant_id}`](../03-specs/21-records-governance.md#delete-apiv1guestsguest_idgrantsgrant_id) | `guests:manage` |
| POST | [`/api/v1/auth/guest/request-link`](../03-specs/21-records-governance.md#post-apiv1authguestrequest-link) | see spec |
| POST | [`/api/v1/auth/guest/session`](../03-specs/21-records-governance.md#post-apiv1authguestsession) | see spec |
| POST | [`/api/v1/auth/guest/totp/enroll`](../03-specs/21-records-governance.md#post-apiv1authguesttotpenroll) | see spec |
| GET | [`/api/v1/binders`](../03-specs/21-records-governance.md#get-apiv1binders) | `binders:export` |
| POST | [`/api/v1/binders`](../03-specs/21-records-governance.md#post-apiv1binders) | `binders:export` |
| GET | [`/api/v1/binders/{binder_id}`](../03-specs/21-records-governance.md#get-apiv1bindersbinder_id) | see spec |
| POST | [`/api/v1/binders/{binder_id}:build`](../03-specs/21-records-governance.md#post-apiv1bindersbinder_idbuild) | `binders:export` |
| GET | [`/api/v1/binders/{binder_id}/download`](../03-specs/21-records-governance.md#get-apiv1bindersbinder_iddownload) | see spec |
| GET | [`/api/v1/tenant/packs`](../03-specs/21-records-governance.md#get-apiv1tenantpacks) | Any signed-in principal |
| POST | [`/api/v1/tenant/packs/{pack_id}:enable`](../03-specs/21-records-governance.md#post-apiv1tenantpackspack_idenable) | `packs:manage` |
| POST | [`/api/v1/tenant/packs/{pack_id}:disable`](../03-specs/21-records-governance.md#post-apiv1tenantpackspack_iddisable) | `packs:manage` |

### GRC pack

Spec: [10-grc-pack/api.md](../10-grc-pack/api.md)

| Method | Path | Permission |
|---|---|---|
| GET | [`/api/v1/ext/grc/frameworks`](../10-grc-pack/api.md#get-apiv1extgrcframeworks) | `grc.frameworks:read` |
| POST | [`/api/v1/ext/grc/frameworks`](../10-grc-pack/api.md#post-apiv1extgrcframeworks) | `grc.frameworks:manage` |
| GET | [`/api/v1/ext/grc/frameworks/{framework_id}`](../10-grc-pack/api.md#get-apiv1extgrcframeworksframework_id) | `grc.frameworks:read` |
| PATCH | [`/api/v1/ext/grc/frameworks/{framework_id}`](../10-grc-pack/api.md#patch-apiv1extgrcframeworksframework_id) | `grc.frameworks:manage` |
| POST | [`/api/v1/ext/grc/frameworks:import-oscal`](../10-grc-pack/api.md#post-apiv1extgrcframeworksimport-oscal) | `grc.frameworks:manage` |
| GET | [`/api/v1/ext/grc/frameworks/{framework_id}:export-oscal`](../10-grc-pack/api.md#get-apiv1extgrcframeworksframework_idexport-oscal) | `grc.frameworks:read` |
| POST | [`/api/v1/ext/grc/frameworks/{framework_id}:import-licensed-text`](../10-grc-pack/api.md#post-apiv1extgrcframeworksframework_idimport-licensed-text) | `grc.frameworks:manage` |
| GET | [`/api/v1/ext/grc/frameworks/{framework_id}/requirements`](../10-grc-pack/api.md#get-apiv1extgrcframeworksframework_idrequirements) | `grc.frameworks:read` |
| GET | [`/api/v1/ext/grc/requirements/{requirement_id}`](../10-grc-pack/api.md#get-apiv1extgrcrequirementsrequirement_id) | `grc.frameworks:read` |
| GET | [`/api/v1/ext/grc/controls`](../10-grc-pack/api.md#get-apiv1extgrccontrols) | `grc.controls:read` |
| POST | [`/api/v1/ext/grc/controls`](../10-grc-pack/api.md#post-apiv1extgrccontrols) | `grc.controls:manage` |
| GET | [`/api/v1/ext/grc/controls/{control_id}`](../10-grc-pack/api.md#get-apiv1extgrccontrolscontrol_id) | `grc.controls:read` |
| PATCH | [`/api/v1/ext/grc/controls/{control_id}`](../10-grc-pack/api.md#patch-apiv1extgrccontrolscontrol_id) | `grc.controls:manage` |
| GET | [`/api/v1/ext/grc/control-mappings`](../10-grc-pack/api.md#get-apiv1extgrccontrol-mappings) | `grc.controls:read` |
| POST | [`/api/v1/ext/grc/control-mappings`](../10-grc-pack/api.md#post-apiv1extgrccontrol-mappings) | `grc.controls:manage` |
| POST | [`/api/v1/ext/grc/control-mappings/{mapping_id}:confirm`](../10-grc-pack/api.md#post-apiv1extgrccontrol-mappingsmapping_idconfirm) | `grc.controls:manage` |
| POST | [`/api/v1/ext/grc/control-mappings/{mapping_id}:reject`](../10-grc-pack/api.md#post-apiv1extgrccontrol-mappingsmapping_idreject) | `grc.controls:manage` |
| POST | [`/api/v1/ext/grc/control-mappings:suggest`](../10-grc-pack/api.md#post-apiv1extgrccontrol-mappingssuggest) | `grc.controls:read` |
| GET | [`/api/v1/ext/grc/evidence-links`](../10-grc-pack/api.md#get-apiv1extgrcevidence-links) | `grc.controls:read` |
| POST | [`/api/v1/ext/grc/evidence-links`](../10-grc-pack/api.md#post-apiv1extgrcevidence-links) | `grc.evidence:link` |
| DELETE | [`/api/v1/ext/grc/evidence-links/{link_id}`](../10-grc-pack/api.md#delete-apiv1extgrcevidence-linkslink_id) | `grc.evidence:link` |
| GET | [`/api/v1/ext/grc/control-tests`](../10-grc-pack/api.md#get-apiv1extgrccontrol-tests) | `grc.tests:read` |
| POST | [`/api/v1/ext/grc/control-tests`](../10-grc-pack/api.md#post-apiv1extgrccontrol-tests) | `grc.controls:manage` |
| PATCH | [`/api/v1/ext/grc/control-tests/{test_id}`](../10-grc-pack/api.md#patch-apiv1extgrccontrol-teststest_id) | `grc.controls:manage` |
| POST | [`/api/v1/ext/grc/control-tests/{test_id}:run`](../10-grc-pack/api.md#post-apiv1extgrccontrol-teststest_idrun) | `grc.tests:run` |
| GET | [`/api/v1/ext/grc/test-results`](../10-grc-pack/api.md#get-apiv1extgrctest-results) | `grc.tests:read` |
| GET | [`/api/v1/ext/grc/findings`](../10-grc-pack/api.md#get-apiv1extgrcfindings) | `grc.findings:read` |
| POST | [`/api/v1/ext/grc/findings`](../10-grc-pack/api.md#post-apiv1extgrcfindings) | `grc.findings:manage` |
| GET | [`/api/v1/ext/grc/findings/{finding_id}`](../10-grc-pack/api.md#get-apiv1extgrcfindingsfinding_id) | `grc.findings:read` |
| PATCH | [`/api/v1/ext/grc/findings/{finding_id}`](../10-grc-pack/api.md#patch-apiv1extgrcfindingsfinding_id) | `grc.findings:manage` |
| POST | [`/api/v1/ext/grc/findings/{finding_id}:close`](../10-grc-pack/api.md#post-apiv1extgrcfindingsfinding_idclose) | `grc.findings:manage` |
| GET | [`/api/v1/ext/grc/issues`](../10-grc-pack/api.md#get-apiv1extgrcissues) | `grc.findings:read` |
| POST | [`/api/v1/ext/grc/issues`](../10-grc-pack/api.md#post-apiv1extgrcissues) | `grc.findings:manage` |
| PATCH | [`/api/v1/ext/grc/issues/{issue_id}`](../10-grc-pack/api.md#patch-apiv1extgrcissuesissue_id) | `grc.findings:manage` |
| GET | [`/api/v1/ext/grc/assets`](../10-grc-pack/api.md#get-apiv1extgrcassets) | `grc.risks:read` |
| POST | [`/api/v1/ext/grc/assets`](../10-grc-pack/api.md#post-apiv1extgrcassets) | `grc.risks:manage` |
| GET | [`/api/v1/ext/grc/risks`](../10-grc-pack/api.md#get-apiv1extgrcrisks) | `grc.risks:read` |
| POST | [`/api/v1/ext/grc/risks`](../10-grc-pack/api.md#post-apiv1extgrcrisks) | `grc.risks:manage` |
| GET | [`/api/v1/ext/grc/risks/{risk_id}`](../10-grc-pack/api.md#get-apiv1extgrcrisksrisk_id) | `grc.risks:read` |
| PATCH | [`/api/v1/ext/grc/risks/{risk_id}`](../10-grc-pack/api.md#patch-apiv1extgrcrisksrisk_id) | `grc.risks:manage` |
| POST | [`/api/v1/ext/grc/risks/{risk_id}:accept`](../10-grc-pack/api.md#post-apiv1extgrcrisksrisk_idaccept) | `grc.risks:manage` |
| GET | [`/api/v1/ext/grc/risks/{risk_id}/treatments`](../10-grc-pack/api.md#get-apiv1extgrcrisksrisk_idtreatments) | `grc.risks:read` |
| POST | [`/api/v1/ext/grc/risks/{risk_id}/treatments`](../10-grc-pack/api.md#post-apiv1extgrcrisksrisk_idtreatments) | `grc.risks:manage` |
| GET | [`/api/v1/ext/grc/vendors`](../10-grc-pack/api.md#get-apiv1extgrcvendors) | `grc.vendors:read` |
| POST | [`/api/v1/ext/grc/vendors`](../10-grc-pack/api.md#post-apiv1extgrcvendors) | `grc.vendors:manage` |
| GET | [`/api/v1/ext/grc/vendors/{vendor_id}`](../10-grc-pack/api.md#get-apiv1extgrcvendorsvendor_id) | `grc.vendors:read` |
| PATCH | [`/api/v1/ext/grc/vendors/{vendor_id}`](../10-grc-pack/api.md#patch-apiv1extgrcvendorsvendor_id) | `grc.vendors:manage` |
| GET | [`/api/v1/ext/grc/vendors/{vendor_id}/assessments`](../10-grc-pack/api.md#get-apiv1extgrcvendorsvendor_idassessments) | `grc.vendors:read` |
| POST | [`/api/v1/ext/grc/vendors/{vendor_id}/assessments`](../10-grc-pack/api.md#post-apiv1extgrcvendorsvendor_idassessments) | `grc.vendors:manage` |
| POST | [`/api/v1/ext/grc/vendor-assessments/{assessment_id}:score`](../10-grc-pack/api.md#post-apiv1extgrcvendor-assessmentsassessment_idscore) | `grc.vendors:manage` |
| GET | [`/api/v1/ext/grc/policies`](../10-grc-pack/api.md#get-apiv1extgrcpolicies) | `grc.policies:read` |
| POST | [`/api/v1/ext/grc/policies`](../10-grc-pack/api.md#post-apiv1extgrcpolicies) | `grc.policies:manage` |
| GET | [`/api/v1/ext/grc/policies/{policy_id}`](../10-grc-pack/api.md#get-apiv1extgrcpoliciespolicy_id) | `grc.policies:read` |
| POST | [`/api/v1/ext/grc/policies/{policy_id}/versions`](../10-grc-pack/api.md#post-apiv1extgrcpoliciespolicy_idversions) | `grc.policies:manage` |
| POST | [`/api/v1/ext/grc/policies/{policy_id}:submit-review`](../10-grc-pack/api.md#post-apiv1extgrcpoliciespolicy_idsubmit-review) | `grc.policies:manage` |
| POST | [`/api/v1/ext/grc/policy-versions/{version_id}:publish`](../10-grc-pack/api.md#post-apiv1extgrcpolicy-versionsversion_idpublish) | `grc.policies:manage` |
| GET | [`/api/v1/ext/grc/obligations`](../10-grc-pack/api.md#get-apiv1extgrcobligations) | `grc.obligations:read` |
| POST | [`/api/v1/ext/grc/obligations`](../10-grc-pack/api.md#post-apiv1extgrcobligations) | `grc.obligations:manage` |
| PATCH | [`/api/v1/ext/grc/obligations/{obligation_id}`](../10-grc-pack/api.md#patch-apiv1extgrcobligationsobligation_id) | `grc.obligations:manage` |
| GET | [`/api/v1/ext/grc/regulatory-changes`](../10-grc-pack/api.md#get-apiv1extgrcregulatory-changes) | `grc.obligations:read` |
| POST | [`/api/v1/ext/grc/regulatory-changes/{change_id}:triage`](../10-grc-pack/api.md#post-apiv1extgrcregulatory-changeschange_idtriage) | `grc.obligations:manage` |
| GET | [`/api/v1/ext/grc/regulator-feeds`](../10-grc-pack/api.md#get-apiv1extgrcregulator-feeds) | `grc.obligations:read` |
| POST | [`/api/v1/ext/grc/regulator-feeds`](../10-grc-pack/api.md#post-apiv1extgrcregulator-feeds) | `grc.obligations:manage` |
| GET | [`/api/v1/ext/grc/incidents`](../10-grc-pack/api.md#get-apiv1extgrcincidents) | `grc.incidents:read` |
| POST | [`/api/v1/ext/grc/incidents`](../10-grc-pack/api.md#post-apiv1extgrcincidents) | `grc.incidents:manage` |
| GET | [`/api/v1/ext/grc/incidents/{incident_id}`](../10-grc-pack/api.md#get-apiv1extgrcincidentsincident_id) | `grc.incidents:read` |
| PATCH | [`/api/v1/ext/grc/incidents/{incident_id}`](../10-grc-pack/api.md#patch-apiv1extgrcincidentsincident_id) | `grc.incidents:manage` |
| POST | [`/api/v1/ext/grc/incidents/{incident_id}:start-clock`](../10-grc-pack/api.md#post-apiv1extgrcincidentsincident_idstart-clock) | `grc.incidents:manage` |
| POST | [`/api/v1/ext/grc/incidents/{incident_id}:file-notification`](../10-grc-pack/api.md#post-apiv1extgrcincidentsincident_idfile-notification) | `grc.incidents:manage` |
| GET | [`/api/v1/ext/grc/campaigns`](../10-grc-pack/api.md#get-apiv1extgrccampaigns) | `grc.campaigns:read` |
| POST | [`/api/v1/ext/grc/campaigns`](../10-grc-pack/api.md#post-apiv1extgrccampaigns) | `grc.campaigns:manage` |
| GET | [`/api/v1/ext/grc/campaigns/{campaign_id}`](../10-grc-pack/api.md#get-apiv1extgrccampaignscampaign_id) | `grc.campaigns:read` |
| POST | [`/api/v1/ext/grc/campaigns/{campaign_id}:start`](../10-grc-pack/api.md#post-apiv1extgrccampaignscampaign_idstart) | `grc.campaigns:manage` |
| POST | [`/api/v1/ext/grc/campaigns/{campaign_id}:close`](../10-grc-pack/api.md#post-apiv1extgrccampaignscampaign_idclose) | `grc.campaigns:manage` |
| GET | [`/api/v1/ext/grc/campaign-items`](../10-grc-pack/api.md#get-apiv1extgrccampaign-items) | `grc.campaigns:read` |
| POST | [`/api/v1/ext/grc/campaign-items/{item_id}:decide`](../10-grc-pack/api.md#post-apiv1extgrccampaign-itemsitem_iddecide) | `object-level (see spec)` |
| GET | [`/api/v1/ext/grc/answer-library`](../10-grc-pack/api.md#get-apiv1extgrcanswer-library) | `grc.questionnaires:read` |
| POST | [`/api/v1/ext/grc/answer-library`](../10-grc-pack/api.md#post-apiv1extgrcanswer-library) | `grc.questionnaires:manage` |
| PATCH | [`/api/v1/ext/grc/answer-library/{answer_id}`](../10-grc-pack/api.md#patch-apiv1extgrcanswer-libraryanswer_id) | `grc.questionnaires:manage` |
| POST | [`/api/v1/ext/grc/questionnaires:draft`](../10-grc-pack/api.md#post-apiv1extgrcquestionnairesdraft) | `grc.questionnaires:manage` |
| POST | [`/api/v1/ext/grc/questionnaires/{job_id}:export`](../10-grc-pack/api.md#post-apiv1extgrcquestionnairesjob_idexport) | `grc.questionnaires:manage` |
| GET | [`/api/v1/ext/grc/pbc-requests`](../10-grc-pack/api.md#get-apiv1extgrcpbc-requests) | `grc.audit_portal:manage` |
| POST | [`/api/v1/ext/grc/pbc-requests`](../10-grc-pack/api.md#post-apiv1extgrcpbc-requests) | `grc.audit_portal:manage` |
| PATCH | [`/api/v1/ext/grc/pbc-requests/{request_id}`](../10-grc-pack/api.md#patch-apiv1extgrcpbc-requestsrequest_id) | `grc.audit_portal:manage` |
| POST | [`/api/v1/ext/grc/pbc-lists:import`](../10-grc-pack/api.md#post-apiv1extgrcpbc-listsimport) | `grc.audit_portal:manage` |
| GET | [`/api/v1/ext/grc/entitlements`](../10-grc-pack/api.md#get-apiv1extgrcentitlements) | `grc.campaigns:read` |
| POST | [`/api/v1/ext/grc/entitlements:ingest`](../10-grc-pack/api.md#post-apiv1extgrcentitlementsingest) | `grc.campaigns:manage` |
| GET | [`/api/v1/ext/grc/sod-rules`](../10-grc-pack/api.md#get-apiv1extgrcsod-rules) | `grc.campaigns:read` |
| POST | [`/api/v1/ext/grc/sod-rules`](../10-grc-pack/api.md#post-apiv1extgrcsod-rules) | `grc.campaigns:manage` |
| PATCH | [`/api/v1/ext/grc/sod-rules/{rule_id}`](../10-grc-pack/api.md#patch-apiv1extgrcsod-rulesrule_id) | `grc.campaigns:manage` |
| DELETE | [`/api/v1/ext/grc/sod-rules/{rule_id}`](../10-grc-pack/api.md#delete-apiv1extgrcsod-rulesrule_id) | `grc.campaigns:manage` |
| GET | [`/api/v1/ext/grc/report-templates`](../10-grc-pack/api.md#get-apiv1extgrcreport-templates) | `grc.reports:export` |
| POST | [`/api/v1/ext/grc/reports:render`](../10-grc-pack/api.md#post-apiv1extgrcreportsrender) | `grc.reports:export` |
| GET | [`/api/v1/ext/grc/entities`](../10-grc-pack/api.md#get-apiv1extgrcentities) | `grc.entities:read` |
| POST | [`/api/v1/ext/grc/entities`](../10-grc-pack/api.md#post-apiv1extgrcentities) | `grc.entities:manage` |
| GET | [`/api/v1/ext/grc/entities/{entity_id}/posture`](../10-grc-pack/api.md#get-apiv1extgrcentitiesentity_idposture) | `grc.entities:read` |
| GET | [`/api/v1/ext/grc/exceptions`](../10-grc-pack/api.md#get-apiv1extgrcexceptions) | `grc.controls:read` |
| POST | [`/api/v1/ext/grc/exceptions`](../10-grc-pack/api.md#post-apiv1extgrcexceptions) | `grc.exceptions:manage` |
| GET | [`/api/v1/ext/grc/ethics-cases`](../10-grc-pack/api.md#get-apiv1extgrcethics-cases) | `grc.ethics:manage` |
| POST | [`/api/v1/ext/grc/ethics-cases`](../10-grc-pack/api.md#post-apiv1extgrcethics-cases) | `grc.ethics:manage` |
| GET | [`/api/v1/ext/grc/inspections`](../10-grc-pack/api.md#get-apiv1extgrcinspections) | `grc.inspections:manage` |
| POST | [`/api/v1/ext/grc/inspections`](../10-grc-pack/api.md#post-apiv1extgrcinspections) | `grc.inspections:manage` |
| GET | [`/api/v1/ext/grc/dsar-requests`](../10-grc-pack/api.md#get-apiv1extgrcdsar-requests) | `grc.privacy:manage` |
| POST | [`/api/v1/ext/grc/dsar-requests`](../10-grc-pack/api.md#post-apiv1extgrcdsar-requests) | `grc.privacy:manage` |
| GET | [`/api/v1/ext/grc/consent-records`](../10-grc-pack/api.md#get-apiv1extgrcconsent-records) | `grc.privacy:manage` |
| POST | [`/api/v1/ext/grc/consent-records`](../10-grc-pack/api.md#post-apiv1extgrcconsent-records) | `grc.privacy:manage` |
| GET | [`/api/v1/ext/grc/resilience-tests`](../10-grc-pack/api.md#get-apiv1extgrcresilience-tests) | `grc.controls:read` |
| POST | [`/api/v1/ext/grc/resilience-tests`](../10-grc-pack/api.md#post-apiv1extgrcresilience-tests) | `grc.controls:manage` |
| POST | [`/api/v1/ext/grc/assets`](../10-grc-pack/api.md#post-apiv1extgrcassets) | `grc.risks:manage` |
