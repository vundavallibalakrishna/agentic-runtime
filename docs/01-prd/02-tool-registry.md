# PRD 02 — Tools & connectors

Tool owners register MCP servers (remote, OpenAPI-derived, SQL, built-in), govern each tool (risk class, data classification, rate limits), and route every call through `mcp-gateway` with policy, credentials, and audit. Spec: [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 03](../03-specs/03-secrets-credentials.md), [mcp-integration](../05-contracts/mcp-integration.md), [connector-sdk](../05-contracts/connector-sdk.md). Plan: [M4](../09-plan/M04-tools-mcp.md).

### US-TOOL-01 · Register a remote MCP server (P0)
As a **tool owner**, I want to register an MCP server by URL so that agents can use its tools.
- `POST /api/v1/tool-servers` + `POST …/versions` with URL, transport (Streamable HTTP), `auth_mode` (`none`, `static_secret`, `user_oauth`, `token_exchange`, `internal_jwt`) creates a `draft` version; `:discover` lists tools with schemas and annotations.
- URLs resolving to private ranges are refused unless inside `AR_MCP_INTERNAL_HTTP_ALLOWED_CIDRS` (SSRF guard).
- Spec: spec 08 §2–3, §7; mcp-integration §4–5. Plan: M4-T01, M4-T03.

### US-TOOL-02 · Govern each tool (P0)
As a **tool owner**, I want to set risk class, data classification, timeout and rate limit per tool.
- Each discovered tool gets a proposed risk class (MCP annotations; OpenAPI: GET/HEAD → `R0`, POST/PUT/PATCH → `W2`, DELETE → `W3`; SQL: `R1`); the owner must confirm or change it (`R0`, `R1`, `W1`, `W2`, `W3`) before submitting; annotations alone are never trusted.
- Per-tool overrides (`require_approval_always`, `rate_limit_per_minute`, `timeout_s`) are stored on the version and immutable once approved.
- Spec: spec 08 §3, [spec 09 §1](../03-specs/09-policy-approvals.md). Plan: M4-T01.

### US-TOOL-03 · Review and approve tool server versions (P0)
As a **tool reviewer** (holder of `tools:review`), I want to approve new versions so that no unreviewed tool reaches agents.
- `:submit` → `pending_review`; `:approve` by a different user than the creator; `:reject` with notes. Approved manifests are immutable (DB trigger).
- Review queue shows full descriptions and schemas, diff to the previous approved version, and flags (long descriptions, instruction-like text).
- Spec: spec 08 §2. Plan: M4-T01, M4-T10.

### US-TOOL-04 · Detect manifest drift (P0)
As a **security officer**, I want changed upstream tools to be blocked until re-reviewed (rug-pull defence).
- Hourly drift check; on change the server goes to `pending_review` with a diff and the owner and reviewers are notified; calls fail with `tool_manifest_drift` until a version is re-approved.
- Spec: spec 08 §5 step 9, §8. Plan: M4-T09.

### US-TOOL-05 · Connect my account to a tool (P0)
As a **member**, I want to connect my own account (OAuth) so that agents act with my permissions.
- When a tool with `auth_mode=user_oauth` has no grant for me, the call fails with `tool_call.failed` (`error.code = credential_required`, `connect_url`), the chat shows a **Connect** button and the agent asks me to connect; after `POST /api/v1/connections/{provider_id}:start` and the OAuth callback I retry (or regenerate) and the call succeeds.
- I can see and revoke my connections (`DELETE /api/v1/connections/{grant_id}`); tokens are never shown to agents, sandboxes, logs or traces.
- Spec: spec 03 §3–5. Plan: M4-T02, M4-T10.

### US-TOOL-06 · Turn an OpenAPI description into tools (P0)
As a **tool owner**, I want to import an OpenAPI 3.x document of an internal API and expose selected operations as tools.
- Import creates a tool server served by `mcp-openapi`, one tool per selected operation (name from `operationId`), with request validation and response size limits.
- Spec: spec 08 §11. Plan: M4-T06.

### US-TOOL-07 · Query a database safely (P0)
As a **tool owner**, I want to expose a read-only SQL tool over a company database.
- `POST /api/v1/data-connections` (engine per [definition-schema §4](../05-contracts/definition-schema.md#4-dataconnection-kind-dataconnection), DSN in a secret, table/column allowlists, row limit, statement timeout); `:test` and `/schema` browse.
- Generated tools `{slug}.list_tables` (R0), `{slug}.describe_table` (R0), `{slug}.run_query` (R1); the SQL guard accepts exactly one read-only statement over allowlisted tables and rejects DDL/DML and dangerous functions.
- Identity modes `service`, `per_user_mapped` (database role from `users.attributes.db_role`) and `passthrough`.
- Spec: spec 08 §10, [definition-schema §4](../05-contracts/definition-schema.md#4-dataconnection-kind-dataconnection). Plan: M4-T07.

### US-TOOL-08 · Built-in tools (P0)
As a **builder**, I want common tools available without setup.
- Platform servers: files, conversations, web (fetch through egress allowlist), plan, `tools.search`, and later sandbox, browser, memory, knowledge, delivery and subagent tools as their milestones land.
- Spec: spec 08 §9. Plan: M4-T05 (and M6, M7, M8, M9, M10 tasks).

### US-TOOL-09 · Test a tool and inspect calls (P0)
As a **tool owner**, I want to try a tool and see recent calls so that I can debug.
- `POST /api/v1/tools/{tool_id}:test` executes through the full pipeline (policy applies; W2/W3 only in dry-run when the server supports it).
- `GET /api/v1/tool-calls` lists calls with status, latency, risk class, policy decision; arguments are shown only to owners and admins (others see `args_hash`).
- Spec: spec 08 §3. Plan: M4-T09.

### US-TOOL-10 · Build a custom connector (P1)
As a **platform engineer**, I want an SDK to write a new MCP connector with tenancy, auth and telemetry built in.
- `ar_connector_sdk` provides server scaffolding, internal JWT verification, user context, structured errors, test harness; a sample connector passes the conformance tests.
- Spec: connector-sdk. Plan: M4-T08.
