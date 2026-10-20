# Internal service APIs

Service-to-service HTTP APIs that are **not** exposed by the public ingress. NetworkPolicies allow only the callers listed. Every request carries an **internal service token** (below) and W3C `traceparent`.

## 1. Internal service authentication

- Each deployable has an Ed25519 key pair; private key mounted from the secrets backend (`AR_INTERNAL_JWT_PRIVATE_KEY`), public keys distributed as a JWKS (`AR_INTERNAL_JWT_JWKS`, also served by `api` at `/internal/v1/.well-known/jwks.json`).
- Caller sends `Authorization: Bearer <jwt>` with claims: `iss` = calling service name (e.g. `runtime-worker`), `aud` = target service name, `iat`, `exp` (≤ 60 s), `jti`, and the **acting context**: `tenant_id`, `user_id` (on-behalf-of, nullable for system calls), `run_id?`, `agent_id?`, `scopes` (service-level, e.g. `models:invoke`).
- Targets verify signature, `aud`, `exp`, and that `iss` is in their allowed-caller list. `ar_common.internal_auth` implements both sides.
- **Service scopes** are distinct from user permission keys ([authn-authz](../06-security/authn-authz.md)). Format `<area>:<operation>`; v1 defines exactly: `models:invoke`, `models:embed` (model-gateway), `tools:call`, `tools:list` (mcp-gateway), `sandboxes:manage` (sandbox-manager, all §4 endpoints), `api:internal` (§6), `channels:deliver` (§8). The caller's token carries the scopes listed for its `iss` in the target's allowed-caller table (`ar_common.internal_auth.ALLOWED_CALLERS`, a static dict in code); a missing scope → `403 forbidden`. Internal endpoint names such as `sandboxes:ensure` are custom-method paths, not scopes.

## 2. `model-gateway` (OpenAI-compatible, base `http://model-gateway:8001`)

Allowed callers: `runtime-worker`, `system-worker`, `ingest-worker`, `mcp-gateway`, `api`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/chat/completions` | OpenAI Chat Completions (stream and non-stream). `model` = alias (e.g. `reasoning`). Extra headers: `X-AR-Run-Id`, `X-AR-Purpose` (`agent_step`, `title`, `compaction`, `memory_extraction`, `memory_recall`, `judge`, `classifier`, `builder_assist`, `ingest_context`, `ingest_embed`, `test`). |
| POST | `/v1/embeddings` | `model` = alias (`embed`), `input` string or array (≤ 256 items), optional `dimensions`. |
| POST | `/v1/rerank` | `{model: "rerank", query, documents: [str], top_n}` → `{results: [{index, relevance_score}]}` (TEI-compatible). |
| GET | `/v1/models` | Aliases visible to the tenant in the token. |
| GET | `/healthz`, `/readyz`, `/metrics` | Health and metrics. |

Full behaviour: [spec 04](../03-specs/04-model-gateway.md).

## 3. `mcp-gateway` (base `http://mcp-gateway:8002`)

Allowed callers: `runtime-worker`, `api` (discovery, test calls), `system-worker` (drift checks, routine delivery tools).

| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/v1/catalog:resolve` | Input: `{agent_version_id, user_id, query?: string}` → model-facing tool list (names, descriptions, schemas) after entitlement filtering and optional tool search. |
| POST | `/internal/v1/tool-calls:execute` | Input: `ExecuteToolCallRequest` → `ExecuteToolCallResult`. |
| POST | `/internal/v1/discover` | Input: `{tool_server_version_id}` → manifest + created tool versions. |
| POST | `/internal/v1/tool-calls:test` | Builder "test tool" with explicit arguments (always runs policy; W2/W3 refused in test mode unless `dry_run` supported). |
| GET | `/healthz`, `/readyz`, `/metrics` | |

`ExecuteToolCallRequest`:

```json
{
  "tool_call_id": "uuid", "run_id": "uuid", "agent_id": "uuid", "agent_version_id": "uuid",
  "user_id": "uuid", "conversation_id": "uuid|null", "trigger": "chat",
  "tool_version_id": "uuid", "qualified_name": "jira.create_issue",
  "arguments": { }, "args_hash": "hex", "idempotency_key": "run:call",
  "approval_id": "uuid|null", "timeout_s": 60, "sandbox_scope_key": "conv:...|null",
  "result_max_tokens": 4000,
  "input_responses": [ {"request_id": "...", "action": "accept|decline|cancel", "content": { }} ],
  "dry_run": false
}
```

`ExecuteToolCallResult`:

```json
{
  "status": "succeeded|failed|denied|requires_approval|credential_required|input_required",
  "content_for_model": "string (already wrapped & truncated)",
  "result_preview": "string ≤ 2 KiB",
  "result_file_id": "uuid|null", "files": [ {"file_id":"...","name":"...","mime_type":"..."} ],
  "structured": { }, "is_error": false,
  "error": {"code":"...","message":"..."},
  "policy": {"decision":"allow","reasons":[]},
  "connect_url": null,
  "input_request": {"request_id": "...", "message": "...", "requested_schema": { }} ,
  "approval": {"approval_id": "uuid", "expires_at": "ts", "preview": { }, "approver_rule": { }},
  "latency_ms": 812, "usage": {"tool_calls": 1, "sandbox_cpu_seconds": 0}
}
```

When `status="requires_approval"`, `mcp-gateway` has already created the `approvals` row (and its notification fan-out via outbox) and returns it in `approval`; the runtime waits and then re-sends the same request with `approval_id`. The gateway re-evaluates policy, verifies the approval is `approved`, unconsumed, unexpired and that `args_hash` matches, marks it consumed (`consumed_at`) in the same transaction as the `tool_calls` status change, then executes. `input_request` is set only for `input_required`; `connect_url` only for `credential_required`.

`error.code` values (stable; the runtime maps them to model-readable messages): `validation_failed` (arguments violate the input schema), `tool_disabled` (tool, server or agent kill switch), `tool_manifest_drift`, `policy_denied` (status `denied`), `approval_invalid` (approval not approved, already consumed, expired, or `args_hash` mismatch), `approval_rejected`, `credential_required`, `rate_limited`, `quota_exceeded`, `sandbox_unavailable`, `upstream_error`, `upstream_timeout`, `result_too_large` (offload failed), `internal_error`.

## 4. `sandbox-manager` (base `http://sandbox-manager:8003`)

Allowed callers: `mcp-gateway`, `api`, `system-worker` (and `squid` for `/internal/v1/egress/check` only).

| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/v1/sandboxes:ensure` | `{tenant_id, scope, scope_key, template_id, conversation_id?, agent_id?, user_id?}` → `{sandbox_id, status, endpoint_url, token}` (blocks ≤ 30 s until `ready`; resumes suspended). |
| GET | `/internal/v1/sandboxes/{sandbox_id}` | Status. |
| POST | `/internal/v1/sandboxes/{sandbox_id}:suspend` | Snapshot workspace and stop compute. |
| POST | `/internal/v1/sandboxes/{sandbox_id}:terminate` | Destroy (keeps snapshot per retention). |
| POST | `/internal/v1/sandboxes/{sandbox_id}:touch` | Update `last_active_at`. |
| POST | `/internal/v1/sandboxes:reap` | Suspend idle / terminate expired (called by `SandboxReaperWorkflow`). |
| GET | `/internal/v1/sandboxes/{sandbox_id}/files?path=` | List workspace files (for the UI computer panel, proxied by `api`). |
| GET | `/internal/v1/sandboxes/{sandbox_id}/files/content?path=` | Stream a workspace file (≤ 100 MiB). |
| POST | `/internal/v1/sandboxes/{sandbox_id}/files:export` | Store a workspace file as an artifact (`files.kind='artifact'`) → `{file_id}` |
| GET | `/internal/v1/egress/check?sandbox_id=&host=&token=` | Squid external ACL helper: 200 allow / 403 deny (caller: `squid`) |
| GET | `/healthz`, `/readyz`, `/metrics` | |

## 5. `sandbox-agent` (inside the sandbox, `http://<sandbox-ip>:8080`)

Allowed caller: `mcp-gateway` and `sandbox-manager` only (NetworkPolicy + per-sandbox bearer token).

| Method | Path | Purpose |
|---|---|---|
| POST | `/mcp` | MCP server exposing `sandbox.*` and `browser.*` tools ([spec 12](../03-specs/12-sandbox-manager.md) §7). |
| GET | `/files?path=` / `/files/content?path=` | File listing / download for manager proxying. |
| PUT | `/files/content?path=` | Write a file (used to copy attachments and skill assets in). |
| GET | `/healthz` | Liveness. |

## 6. `api` internal endpoints (base `http://api:8000/internal/v1`)

| Method | Path | Caller | Purpose |
|---|---|---|---|
| GET | `/internal/v1/.well-known/jwks.json` | all, MCP servers | Platform JWKS (internal + `internal_jwt` tool auth) |
| GET | `/internal/v1/opa/bundles/ar.tar.gz` | `opa` | Policy bundle (Rego + data), ETag support |
| POST | `/internal/v1/channels/inbound` | `channels` | Deliver a normalised inbound channel message (`ChannelInboundMessage`) → creates/continues a conversation and starts a run; returns `{conversation_id, run_id}` |
| POST | `/internal/v1/channels/approval-decisions` | `channels` | Approve/reject from Slack/Teams buttons (`{approval_id, external_user_id, integration_id, decision, args_hash}`) |
| POST | `/internal/v1/channels/events` | `channels` | Channel events for routines (`channel_event` trigger) |
| GET | `/internal/v1/channels/integrations` | `channels` | Active integrations + decrypted bot credentials for the channels process (mTLS + token; response never logged) |

## 7. `mcp-sql` and `mcp-openapi` connector runtimes

They are MCP servers (`POST /mcp`). They are multi-tenant: every call must include `X-AR-Context` (internal JWT, `aud` = `mcp-sql` / `mcp-openapi`) with an extra claim `connector` = `{tool_server_version_id, config_hash}`; the runtime fetches the connector config from `api` `GET /internal/v1/connectors/{tool_server_version_id}/config` (cached 60 s, returns data connection DSN reference resolved to credentials for the configured identity mode). This keeps credentials out of the gateway request body.

| Method | Path | Caller | Purpose |
|---|---|---|---|
| GET | `/internal/v1/connectors/{tool_server_version_id}/config` | `mcp-sql`, `mcp-openapi` | Connector config incl. resolved credentials (short-lived) |
| POST | `/internal/v1/connections:test` (on `mcp-sql`) | `api` | Test a data connection: connectivity, read-only enforcement, allowlisted objects |

## 8. `channels` internal endpoints (base `http://channels:8004`)

Allowed callers: `mcp-gateway` (delivery tools, channel replies), `system-worker` (notification fan-out), `api` (integration tests/health of integrations). Full behaviour: [spec 16](../03-specs/16-channels.md).

| Method | Path | Purpose |
|---|---|---|
| POST | `/internal/v1/outbound` | Send a message to Slack/Teams/email: `{integration_id, target: {channel?, thread_ts?, conversation_ref?, to?, cc?, subject?}, text_markdown, file_ids?, blocks?}` → `{external_message_id}` |
| POST | `/internal/v1/notify` | Direct message to a platform user via their linked channel identity: `{user_id, kind, title, body_markdown, actions?: [{id, label, style, value}]}` → `{delivered: [channel]}` |
| POST | `/internal/v1/integrations/{integration_id}:test` | Verify credentials and connectivity |
| GET | `/internal/v1/files/{download_ref}` | Signed download proxy for inbound channel attachments (fetches from Slack/Teams with the bot token); caller `api` |
| POST | `/internal/v1/integrations:reload` | Reload integrations from `api` (also triggered by Valkey `ar:invalidate:channel_integration:*`) |
| GET | `/healthz`, `/readyz`, `/metrics` | |

