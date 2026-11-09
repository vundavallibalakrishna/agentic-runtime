# Integrating over the API — getting started

This is the developer guide for calling the platform from another system. There are two
surfaces, each with its own credential:

| Surface | Base path | Credential | Use it to |
|---|---|---|---|
| **Management API** | `/api/v1` | a **service-account key + secret** (`ak_<prefix>.sk_<secret>`) | manage tenants, agents, knowledge, usage — everything the web app does |
| **Agent API** | `/v1` | an **agent key** (`ara_<prefix><secret>`) | call a published agent (chat, MCP, A2A) from another product |

Pick the management API for machine-to-machine automation that acts as a service account; pick
the agent API to expose one published agent to an external caller or tool. The machine-readable
contracts are the root [`openapi.json`](../../openapi.json) (management) and
[`/v1/openapi.json`](openapi.json) (agent API). Full conventions:
[api-conventions.md](../05-contracts/api-conventions.md).

## 1. Service-account integration (`/api/v1`)

### Create a service account and a key + secret

A tenant admin creates a service account (Settings → Service accounts, or
`POST /api/v1/service-accounts`), then mints a key:

```bash
curl -s https://runtime.example/api/v1/api-keys \
  -H "Authorization: Bearer <admin session or key>" \
  -H "Content-Type: application/json" \
  -d '{"name":"ci-bot","serviceAccountId":"<sa-id>","scopes":["agents:read","chat:use"]}'
```

The response returns the credential **once**:

```json
{ "id": "...", "name": "ci-bot", "prefix": "ab12cd34ef56", "keyFormat": "split",
  "scopes": ["agents:read","chat:use"], "key": "ak_ab12cd34ef56.sk_<secret>" }
```

Store `key` securely — later reads return everything **except** the secret. The key id
(`ak_<prefix>`) is safe to log; the `sk_` secret is not.

### Authenticate

Send the whole credential as a bearer token:

```bash
curl -s https://runtime.example/api/v1/agents \
  -H "Authorization: Bearer ak_ab12cd34ef56.sk_<secret>"
```

The caller resolves to a **service-account principal** in the key's tenant. Its permissions are
the service account's role grants **intersected with the key's `scopes`** — a key can only ever
be a subset of what its service account may do. A request for anything outside that set is
`403 forbidden`.

### Rotate and revoke

- **Rotate** issues a new secret, keeps the key id, and invalidates the old secret immediately:
  the response carries the new `key` once. Rotate on a schedule and on suspected exposure.
- **Revoke** disables the key; later calls are `401 unauthenticated`.

(Legacy single-token `ark_...` keys created before the split format keep working.)

## 2. Agent integration (`/v1`)

See [README.md](README.md) for the full REST / MCP / A2A walkthrough. In short: create an agent
key on the agent's **Expose** tab, then either hold a conversation, or use the **one-shot run**
for a single stateless call:

```bash
# One-shot: creates an ephemeral conversation, runs once, returns the reply + usage.
curl -s https://runtime.example/v1/agents/<slug>:run \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"text":"...","stream":false}'
```

The reply includes `usage` with `tokensIn`, `tokensOut` and `costMicros`. A retry with the same
`Idempotency-Key` returns the same run. For a multi-turn conversation, create one and post
messages instead:

```bash
curl -s https://runtime.example/v1/agents/<slug>/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"text":"...","stream":true}'
```

## 3. The contract every caller relies on

These apply to both surfaces (details in [api-conventions.md](../05-contracts/api-conventions.md)):

- **Errors** are RFC 9457 Problem Details (`application/problem+json`) with a stable `code`
  field clients switch on (`unauthenticated`, `forbidden`, `not_found`, `validation_failed`,
  `rate_limited`, `quota_exceeded`, `conflict`, …). See the
  [error code table](../05-contracts/api-conventions.md#5-errors-rfc-9457-problem-details).
- **Idempotency**: every `POST` that starts work accepts `Idempotency-Key`; a replay with the
  same key and body returns the stored response with `Idempotent-Replayed: true`; the same key
  with a different body is `409 idempotency_key_reused`.
- **Pagination** is cursor-based: `limit` (1–200) and `cursor`, with a
  `{ items, nextCursor, hasMore }` envelope.
- **Rate limits**: every response carries `RateLimit-Limit`, `RateLimit-Remaining` and
  `RateLimit-Reset`. A `429 rate_limited` includes `Retry-After`; a `429 quota_exceeded` means a
  block-action quota is exhausted, with `{ quotaId, metric, period, limit, used, resetsAt }`.
  Back off and retry after the stated window.
- **Versioning**: the base path is versioned (`/api/v1`, `/v1`). Additive changes (new fields,
  new endpoints, new *open* enum values) happen in place — **clients must ignore unknown response
  fields**. A breaking change ships under a new major path; deprecations are announced before
  removal.
- **Usage & cost**: run responses carry a usage summary (tokens in/out, model/tool calls and
  `costMicros`); per-tenant and per-key usage is available from the usage API for chargeback.

## 4. Checklist

1. Create a service account (management) or expose an agent (agent API).
2. Mint a key; capture the secret shown once.
3. Send `Authorization: Bearer <key>`; handle `401`/`403` and refresh on rotation.
4. Send `Idempotency-Key` on writes; honour `RateLimit-*` and `429 Retry-After`.
5. Ignore unknown response fields; switch on the error `code`, never the HTTP phrase.
