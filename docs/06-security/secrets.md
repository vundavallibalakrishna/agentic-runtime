# Secrets and key management

Implementation: [spec 03](../03-specs/03-secrets-credentials.md), [ADR-0012](../02-architecture/adr/ADR-0012-secrets-backend.md). This file defines what counts as a secret, where each lives, and how keys rotate.

## 1. Inventory

| Secret | Store | Owner/scope | Rotation |
|---|---|---|---|
| Tenant secrets (API keys for tools, DB DSN passwords, IdP client secrets, channel bot tokens, webhook signing secrets) | `SecretStore` (`vault` or `db_encrypted`) via `secret_refs` | tenant | `POST /api/v1/secrets/{secret_id}:rotate`; consumers pick up within `AR_SECRET_CACHE_TTL_S` |
| User OAuth refresh tokens | `SecretStore`, `credential_grants.secret_ref_id` (personal) | user | refresh rotation on use; deleted on disconnect/erasure |
| Delegation token `__delegation__` (Keycloak offline token) | `SecretStore` personal secret | user | replaced at each login; expires after `AR_OFFLINE_SESSION_MAX_DAYS` |
| Run callback secret `__run_callback_secret__` | `SecretStore` tenant secret | tenant | `POST /api/v1/tenant/run-callback-secret:rotate` (24 h overlap) |
| Routine webhook secrets | `SecretStore` | routine | `POST /api/v1/routines/{routine_id}:rotate-webhook-secret` |
| Outbound webhook secrets | `SecretStore` | webhook | `POST /api/v1/webhooks/{webhook_id}:rotate-secret` (24 h overlap) |
| API keys (`ark_…`), SCIM tokens | Only SHA-256 hash in DB | principal | revoke + create |
| Access-token cache | Valkey, AES-GCM with `AR_TOKEN_CACHE_KEY` | user/provider | key rotation invalidates the cache (tokens re-minted) |
| Session tokens | Valkey, encrypted with `AR_SESSION_ENCRYPTION_KEY` | session | key rotation logs users out (planned window) or uses dual-key decrypt (`AR_SESSION_ENCRYPTION_KEY_PREVIOUS`) |
| Internal JWT signing keys | Kubernetes Secret mounted to each service (`AR_INTERNAL_JWT_PRIVATE_KEY`); JWKS `AR_INTERNAL_JWT_JWKS` | platform | quarterly; two keys published during overlap (kid-based) |
| KEKs for `db_encrypted` | Kubernetes Secret (`AR_DB_ENCRYPTION_KEYS`, active `AR_DB_ENCRYPTION_ACTIVE_KEY`) | platform | add new key, set active, run re-wrap job (`python -m ar_domain.secrets.rotation rewrap`), remove old key |
| Cursor HMAC key | `AR_CURSOR_SECRET` | platform | rotation invalidates outstanding cursors (clients restart pagination) |
| OPA bundle token | `AR_OPA_BUNDLE_TOKEN` | platform | rotate with OPA config |
| Infrastructure credentials (Postgres roles, S3 keys, Qdrant API key (optional adapter), Keycloak admin client secret) | Kubernetes Secrets or OpenBao dynamic secrets (recommended for Postgres via database secrets engine) | platform | per operator policy; dynamic leases preferred |

## 2. Rules (never skip)

1. Secret values never appear in logs, traces, metrics, audit `detail`, API responses (except the one-time display at creation of API keys/secrets the user typed), error messages, or model prompts.
2. Definitions reference secrets by name (fields `secret:` / `dsn_secret:`, [definition-schema](../05-contracts/definition-schema.md)); the platform resolves them only in the process that needs the value (`mcp-gateway`, `ingest-worker`, `channels` via `api`, connector runtimes via config endpoint) at call time.
3. In-process caches ≤ 60 s; never cache secret values in Valkey (only encrypted access tokens).
4. Vault policies are per service: read `ar/data/tenants/*`; only `api` writes. In `dedicated_db` tier, per-tenant Transit keys wrap tenant secrets.
5. Model prompts and tool outputs are scanned for credential patterns before logging/persistence (gitleaks rule set embedded in `ar_common.logging` scrubber for logs; tool-result redaction for common token formats).
6. Personal secrets (`owner_user_id`) are only resolvable for runs of that user.
7. Bundles never include secret values; import creates placeholders that must be filled.

## 3. Logging scrubber

`ar_common.logging` drops or masks keys matching `(?i)(password|secret|token|authorization|api[_-]?key|cookie|dsn|private[_-]?key)` and values matching known token formats (JWT, `ark_…`, Slack `xox*`, AWS keys, PEM blocks). Unit tests cover each pattern.

## 4. Incident: suspected secret leak

Runbook `rb-09`-style steps are in [runbooks](../07-ops/runbooks.md#rb-14-secret-leak): rotate the secret, revoke grants, search audit for usage, notify affected tenant admins, record in incident log.
