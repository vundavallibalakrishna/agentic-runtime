# Spec 03: Secrets and delegated credentials (`ar_domain.secrets`)

Hosted in `api` (CRUD, OAuth connect flow) and used by `mcp-gateway`, `ingest-worker`, `model-gateway`, `channels` (via `api` internal endpoint), `mcp-sql`/`mcp-openapi` (via connector config). Owns tables `secret_refs`, `encrypted_secrets`, `credential_providers`, `credential_grants` ([schema §2](../04-data/schema.md#2-secrets-and-credentials-ar_domainsecrets)). Security: [secrets.md](../06-security/secrets.md).

## 1. Responsibilities

1. Store tenant secrets (API keys, DSNs, bot tokens, OAuth client secrets, webhook HMAC secrets) in a pluggable backend; the DB holds only references.
2. Manage credential providers (OAuth 2.0 / API key / token exchange) that end users connect to.
3. Run the per-user OAuth "connect" flow; store refresh tokens; mint short-lived access tokens on demand.
4. Store each user's **delegation token** (Keycloak offline token) used for RFC 8693 token exchange during background runs.
5. Guarantee secrets never reach models, sandboxes, logs, traces, or API responses.

## 2. `SecretStore` interface (`ar_domain.secrets.store`)

```python
class SecretStore(Protocol):
    async def put(self, tenant_id: UUID, ref_id: UUID, value: bytes) -> str: ...        # returns backend path
    async def get(self, tenant_id: UUID, path: str) -> bytes: ...
    async def delete(self, tenant_id: UUID, path: str) -> None: ...
    async def rotate(self, tenant_id: UUID, path: str, value: bytes) -> int: ...        # returns new version
```

Backends (`AR_SECRETS_BACKEND`):

| Backend | Implementation | When |
|---|---|---|
| `vault` | OpenBao/Vault KV v2 at mount `AR_VAULT_KV_MOUNT` (default `ar`), path `tenants/{tenant_id}/secrets/{secret_ref_id}`; auth via Kubernetes auth method (role `AR_VAULT_ROLE`) or token (`AR_VAULT_TOKEN`, dev only). Optional Transit key per tenant (`ar-tenant-{tenant_id}`) when `isolation_tier != 'shared'`. | Default for SaaS and production installs. |
| `db_encrypted` | Envelope encryption: random 256-bit DEK per secret, AES-256-GCM; DEK wrapped with KEK from `AR_DB_ENCRYPTION_KEYS` (JSON `{"k1": "<base64 32 bytes>"}`, active key `AR_DB_ENCRYPTION_ACTIVE_KEY`). Rows in `encrypted_secrets`. | Small single-tenant installs without Vault; local dev. |

Values are cached in-process for at most 60 s (`AR_SECRET_CACHE_TTL_S`), never in Valkey. Policy in Vault: each service role can read `ar/data/tenants/*`; only `api` can write.

## 3. Public API

#### GET /api/v1/secrets
Permission: `secrets:use` (names only, for pickers) or `secrets:manage` (full metadata). Item `SecretRef {id, name, kind, description, version, created_by, rotated_at, created_at, used_by: [{kind, id, name}]}`. Personal secrets (`owner_user_id` set) are never listed.

#### POST /api/v1/secrets
Permission: `secrets:manage`. Body `{name, kind, value: string (≤ 64 KiB), description?}`. Response `SecretRef` (no value). Audit `secret.created` (no value). Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)). Service accounts with `secrets:manage` are exempt.

#### GET /api/v1/secrets/{secret_id}
Permission: `secrets:manage`. Metadata only. There is **no** endpoint that returns a secret value.

#### PATCH /api/v1/secrets/{secret_id}
Permission: `secrets:manage`. `{name?, description?}`.

#### POST /api/v1/secrets/{secret_id}:rotate
Permission: `secrets:manage`. Body `{value}`. Increments `version`; consumers pick up the new value within the cache TTL. Audit `secret.rotated`. Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)). Service accounts with `secrets:manage` are exempt.

#### DELETE /api/v1/secrets/{secret_id}
Permission: `secrets:manage`. 409 `invalid_state` if referenced (FK RESTRICT) with the list of referencing objects.

#### GET /api/v1/credential-providers
Permission: `tools:read`. Item `CredentialProvider {id, slug, name, kind, authorize_url, token_url, client_id, default_scopes, token_exchange_audience, status}`.

#### POST /api/v1/credential-providers
Permission: `tools:create`. Body `{slug, name, kind, authorize_url?, token_url?, client_id?, client_secret?, default_scopes?, token_exchange_audience?, extra?}`. `client_secret` stored as a secret ref (`kind='oauth_client'`).

#### PATCH /api/v1/credential-providers/{provider_id}
Permission: `tools:create` (owner) or `tenant:manage`.

#### DELETE /api/v1/credential-providers/{provider_id}
Permission: `tenant:manage`. Revokes all grants.

#### GET /api/v1/connections
Any user (`connections:manage_own`). Lists the caller's grants joined with providers: `{provider: {id, slug, name, kind}, grant: {id, status, scopes, external_account_label, expires_at, last_used_at} | null, required_by_agents: [{id, name}]}`.

#### POST /api/v1/connections/{provider_id}:start
Permission: `connections:manage_own`. For `oauth2`: body `{scopes?, return_to}` → creates state `ar:oauth:{state}` (TTL 10 min: user, provider, PKCE verifier, return_to) → `{authorize_url}`. For `api_key`: body `{api_key, label?}` → stored immediately as a personal secret (`owner_user_id` = caller) + grant → `201 Connection`.

#### GET /api/v1/connections/oauth/callback
Session auth. Query `code`, `state`. Exchanges the code at `token_url` (client secret from store), stores the refresh token (or access token if no refresh) as personal secret `kind='oauth_refresh_token'`, upserts `credential_grants` (status `active`, `expires_at` from response when no refresh token), redirects to `return_to` with `?connected={slug}`. Audit `connection.created`.

#### DELETE /api/v1/connections/{grant_id}
Owner only. Revokes at provider if `extra.revocation_url` set, deletes secret and grant. Audit `connection.revoked`.

## 4. Access-token minting (`ar_domain.secrets.tokens`)

`async def access_token_for(ctx, user_id, provider_id) -> AccessToken` used by `mcp-gateway`:
1. Cache: Valkey `ar:tok:{tenant}:{user}:{provider}` holds the access token **encrypted with `AR_TOKEN_CACHE_KEY`** (AES-GCM) until `expires_at - 60 s`.
2. Miss → load refresh token from store → refresh grant at `token_url` → on rotation store the new refresh token (`rotate`) → cache → update `last_used_at`.
3. `invalid_grant` → grant `status='expired'` → raise `CredentialRequired(provider)` (the user must reconnect; notification `system` sent once per day).

## 5. Delegation tokens (Keycloak offline tokens) and token exchange

- At BFF login, the offline refresh token (scope `offline_access`) is stored as the user's personal secret named `__delegation__` (`kind='oauth_refresh_token'`, `owner_user_id=user`). Replaced on each login.
- `token_exchange` auth mode: `mcp-gateway` obtains a fresh user access token by refreshing the delegation token at Keycloak, then performs RFC 8693 exchange (`grant_type=urn:ietf:params:oauth:grant-type:token-exchange`, client `ar-token-exchange`, `audience=<provider.token_exchange_audience>`, `requested_token_type=access_token`). Cached like §4.
- Routines run with the owner's delegation token. If missing/revoked (user deprovisioned, logged out everywhere, or offline session expired after `AR_OFFLINE_SESSION_MAX_DAYS`, default 60), the routine run fails with `delegation_expired` and the routine is paused with reason `owner_reauth_required`; the owner is notified to log in again.

## 6. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AR_SECRETS_BACKEND` | `db_encrypted` (local) / `vault` (prod) | Backend selection |
| `AR_VAULT_ADDR` | `http://localhost:8200` | OpenBao/Vault address |
| `AR_VAULT_KV_MOUNT` | `ar` | KV v2 mount |
| `AR_VAULT_AUTH` | `kubernetes` | `kubernetes` or `token` |
| `AR_VAULT_ROLE` | `ar-{service}` | Kubernetes auth role |
| `AR_VAULT_TOKEN` | (dev) | Token auth |
| `AR_DB_ENCRYPTION_KEYS` | (secret) | KEKs for `db_encrypted` |
| `AR_DB_ENCRYPTION_ACTIVE_KEY` | `k1` | Active KEK id |
| `AR_TOKEN_CACHE_KEY` | (secret) | Encrypts cached access tokens in Valkey |
| `AR_SECRET_CACHE_TTL_S` | `60` | In-process cache |
| `AR_OFFLINE_SESSION_MAX_DAYS` | `60` | Must match Keycloak realm offline session max |

## 7. Failure modes

| Failure | Behaviour |
|---|---|
| Vault sealed/unreachable | Secret reads raise `SecretBackendUnavailable` → tool call fails with retriable `upstream_error`; `/readyz` of `mcp-gateway` degrades (still ready, alerts fire). |
| KEK missing for an old secret | Hard error at read, alert `ar_secret_decrypt_failures_total`. Rotation script `scripts/rewrap_secrets.py` re-wraps DEKs to the active key. |
| Provider token endpoint down | Tool error `credential_unavailable` (retriable). |

## 8. Metrics

`ar_secret_reads_total{backend,result}`, `ar_token_refresh_total{provider,result}`, `ar_token_exchange_total{audience,result}`, `ar_secret_decrypt_failures_total`.

## 9. Test plan

- Unit: AES-GCM envelope round-trip, tamper detection, key rotation re-wrap; redaction of secret values from exceptions (`SecretStr` everywhere).
- Integration: OpenBao dev container: put/get/rotate/delete; OAuth connect flow against a mock OAuth server (`respx`): callback stores grant, refresh rotates token, `invalid_grant` → `expired`.
- Security tests: grep-style test that no API response model contains fields named `value|secret|token|password` except the one-time key/token creation responses; log capture test confirms secrets passed through `SecretStr` never appear in structlog output.
