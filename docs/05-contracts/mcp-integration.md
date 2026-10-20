# MCP integration contract

How the platform consumes MCP servers and what a server must do to be registered. Spec revision: **MCP 2026-07-28** (stateless Streamable HTTP). SDK: official `mcp` Python package 2.3.0. Implementation lives in `mcp-gateway` ([spec 08](../03-specs/08-tool-registry-mcp.md)).

## 1. Roles

- **Host / client**: `mcp-gateway` is the only MCP client in the platform (the runtime never talks MCP directly). It also serves built-in tools in-process.
- **Servers**: (a) tenant-registered remote servers (`tool_servers.kind='remote_mcp'`), (b) platform connector runtimes `mcp-sql` and `mcp-openapi` (multi-tenant, configured per call via signed context), (c) `sandbox-agent` inside each sandbox (`kind='sandbox'`).

## 2. Transport requirements for registered servers

| Requirement | Detail |
|---|---|
| Transport | Streamable HTTP, single endpoint (e.g. `https://host/mcp`), `POST` JSON-RPC requests; responses as `application/json` or `text/event-stream` (for progress). stdio servers are **not** accepted (they may only run inside sandboxes). |
| Protocol version | Must support `2026-07-28`. Servers that only support `2025-11-25` are accepted in compatibility mode (gateway sends `initialize` once per call batch) until 2027-07-28; registration shows a warning. |
| Discovery | Must implement `server/discover` and `tools/list`. Lists must be deterministic in order (spec requirement) so manifests hash stably. |
| Stateless | No reliance on sessions. Any cross-call state must be an explicit handle in tool arguments. |
| TLS | `https` required for non-cluster endpoints; cluster-internal `http` allowed only for `*.svc.cluster.local` / allowlisted internal CIDRs (`AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS`). |
| Timeouts | Must respond within the tool's `timeout_s` (default 60 s, max 900 s). Long work should use the `io.modelcontextprotocol/tasks` extension (gateway polls `tasks/get` every 2 s up to `timeout_s`). |
| Result size | Results larger than `max_result_bytes` are accepted up to 20 MiB, offloaded to object storage, and a preview is given to the model. |
| Annotations | Should set `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`; used to propose risk classes. |
| Output | `content` items of type `text`, `image`, `resource_link`, `resource` (embedded) and optional `structuredContent` validated against `outputSchema` when declared. |

## 3. Headers the gateway sends on every call

| Header | Value |
|---|---|
| `Mcp-Method` / `Mcp-Name` | Per spec (e.g. `tools/call`, `create_issue`) |
| `Authorization` | Depends on `auth_mode` (§4) |
| `X-AR-Tenant` | tenant id |
| `X-AR-Request-Id` | tool call id |
| `X-AR-Idempotency-Key` | `tool_calls.idempotency_key` (servers with write tools **must** dedupe on it for 24 h) |
| `traceparent` / `tracestate` | W3C trace context |
| `X-AR-Context` | Only for platform connector runtimes and `internal_jwt` mode: a signed internal JWT (§4.5) |

`_meta` on each JSON-RPC request carries `io.modelcontextprotocol/protocolVersion`, `clientInfo = {name: "agentic-runtime-mcp-gateway", version}`, and `io.agentic-runtime/run = {run_id, agent_id}` (informational).

## 4. Authentication modes (`tool_server_versions.auth_mode`)

1. `none`: no `Authorization`. Allowed only for cluster-internal servers.
2. `static_secret`: `Authorization: Bearer <secret>` or custom header (`config.auth_header`), secret from `secret_ref_id`. Shared credential: the registry review must justify it; tools from such servers default to at least `R1`.
3. `user_oauth`: the end user's access token for `credential_provider_id`, obtained by refreshing the user's `credential_grants` refresh token (cached in Valkey ≤ token lifetime, encrypted). If the user has not connected the provider, the gateway returns tool error `credential_required` with `connect_url` → runtime emits a message part prompting the user (UI renders a "Connect" button to `/connections?provider=...`).
4. `token_exchange`: RFC 8693 exchange at Keycloak: `subject_token` = the user's Keycloak access token for the run (refreshed from the run's stored offline session, see [spec 03](../03-specs/03-secrets-credentials.md) §5), `audience` = `credential_providers.token_exchange_audience`. Result cached per (user, audience) until 60 s before expiry.
5. `internal_jwt`: the gateway signs a short-lived (60 s) EdDSA JWT with claims `{iss: "agentic-runtime", aud: <server slug>, sub: user_id, tenant_id, email, groups[], agent_id, run_id, tool_call_id, scope: [required_scopes]}`. Company-internal MCP servers verify it with the platform JWKS at `GET /internal/v1/.well-known/jwks.json` (also exposed publicly at `/api/v1/.well-known/jwks.json` for servers outside the cluster). This is the recommended mode for internal APIs that trust the platform as an identity broker.

Credentials are **never** placed in tool arguments, model context, sandbox environment, logs or traces.

## 5. Discovery and registration flow

1. Tool owner creates a server version (`POST /api/v1/tool-servers/{server_id}/versions`).
2. `mcp-gateway` `POST /internal/v1/discover` calls `server/discover` then `tools/list` (with auth mode credentials of the requesting owner where needed), stores `manifest` + `manifest_hash`, and creates `tools` / `tool_versions` rows with descriptions, schemas, annotations and proposed risk classes.
3. Validation: every `inputSchema` must be a valid JSON Schema 2020-12 object schema with `type: object`; tool names must match `^[a-z][a-z0-9_]{0,47}$` after normalisation (lowercase, `-`→`_`); descriptions ≤ 4,000 chars; total tools per server ≤ 200.
4. Review (`tools:review` permission): reviewer confirms risk classes, data classification, preview templates, and approves the version. Only approved versions are bindable.
5. Drift detection: `system-worker` re-runs discovery hourly for approved versions; if `manifest_hash` changes (descriptions, schemas or tool set), the version is marked `review_status='pending'`, the server owner and reviewers are notified (`tool_review_requested`), and **the previous approved manifest remains in force**: the gateway rejects any call whose upstream tool schema/description hash differs from the approved `tool_versions` row (`tool_manifest_drift` error). This defends against tool poisoning (T5).

## 6. Calling convention (gateway → server)

```json
{"jsonrpc":"2.0","id":"<tool_call_id>","method":"tools/call",
 "params":{"name":"create_issue","arguments":{"project":"OPS","summary":"..."},
           "_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",
                    "io.modelcontextprotocol/clientInfo":{"name":"agentic-runtime-mcp-gateway","version":"1.0.0"},
                    "progressToken":"<tool_call_id>"}}}
```

- `InputRequiredResult` (MRTR) responses: the gateway supports `elicitation` only by converting it into a run pause with `waiting_input` (the question is shown to the user; the answer is passed back on retry). `sampling` requests are **rejected** (servers may not use the platform's models via MCP in v1).
- `isError: true` results are returned to the model as tool errors (not retried).
- Transport errors / 5xx / timeouts: retried by the runtime only if the tool is `idempotent=true` or the server honours `X-AR-Idempotency-Key` (declared via `config.honours_idempotency_key: true`), max 3 attempts with exponential backoff (1 s, 4 s, 16 s).

## 7. Result handling (gateway → runtime)

1. Concatenate text content; images become files (`files.kind='tool_result'`) referenced by `file` parts; `resource_link` items are listed as links (not fetched).
2. Redact secrets (regex set: private keys, bearer tokens, AWS-style keys, passwords in URLs) and, if the tool's `data_classification` ≥ `confidential` or agent `safety.pii_masking`, PII via Presidio.
3. Neutralise control sequences: strip zero-width and bidi control characters, HTML comments, ANSI escapes.
4. Truncate to `tool_result_max_tokens` (agent context setting) with a `[truncated: N more bytes; full result: file <id>, use files.read with offset]` trailer; full result stored as a file.
5. Wrap as untrusted data for the model (format in [prompt-injection.md](../06-security/prompt-injection.md) §3).

## 8. Built-in tool servers (platform, `tenant_id IS NULL`)

| Server slug | kind | Tools (qualified) | Risk |
|---|---|---|---|
| `knowledge` | builtin | `knowledge.search`, `knowledge.get_document`, `knowledge.list_collections` | R0/R1 by collection classification |
| `memory` | builtin | `memory.search`, `memory.save`, `memory.forget` | R0, W1, W1 |
| `files` | builtin | `files.list`, `files.read`, `files.attach_to_sandbox` | R0, R0, W1 |
| `skills` | builtin | `skills.load` | R0 |
| `conversations` | builtin | `conversations.search_history` | R1 |
| `web` | builtin | `web.fetch` (GET a URL through the egress proxy; tenant allowlist applies) | R0 (open-world) |
| `agents` | builtin (control) | `agents.delegate` | W1 |
| `plan` | builtin (control) | `plan.update` | W1 |
| `delivery` | builtin (system) | `delivery.slack_post`, `delivery.teams_post`, `delivery.email_send`, `delivery.webhook_post` (never offered to models; invoked by the runtime's routine delivery phase, [spec 15 §4](../03-specs/15-routines-triggers.md#4-delivery-phase-in-agentrunworkflow-for-triggerroutine)) | W2 |
| `tools` | builtin (control) | `tools.search` (only offered when tool search is active; loads matching tools into the run's tool set) | R0 |
| `sandbox` | sandbox | `sandbox.exec`, `sandbox.read_file`, `sandbox.write_file`, `sandbox.list_files`, `sandbox.export_file` | W1 (workspace-scoped) |
| `browser` | sandbox | `browser.navigate`, `browser.snapshot`, `browser.click`, `browser.type`, `browser.press`, `browser.scroll`, `browser.screenshot`, `browser.submit_form` | R0 except `browser.type` W1 and `browser.submit_form` W2 |

Control tools (`agents.delegate`, `plan.update`, `tools.search`) are executed by `runtime-worker` itself (they change workflow state), but still pass through policy evaluation (`ar_domain.policy.service.evaluate`, the same function `mcp-gateway` uses) and are recorded in `tool_calls`. Full schemas of built-in tools: [spec 08](../03-specs/08-tool-registry-mcp.md) §9.

## 9. Model-facing tool names

OpenAI-style function names cannot contain dots. The runtime exposes each tool as `{server_slug}__{tool_name}` (double underscore), e.g. `jira__create_issue`, and maps back. Names longer than 64 chars are rejected at registration.
