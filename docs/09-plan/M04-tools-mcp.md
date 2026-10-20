# M4 — Tools & MCP

Goal: agents act. Tool owners register MCP servers, OpenAPI APIs and SQL databases; reviewers approve versions; users connect their accounts; the runtime calls tools only through `mcp-gateway`, which validates, injects credentials, processes results and audits every call.

Exit criteria: an agent with a remote MCP ticketing server (test server in `ar_connector_sdk` examples) creates a ticket (W1) with the user's OAuth token; an agent answers a question by querying a Postgres table through `mcp-sql`; every call appears in `GET /api/v1/tool-calls` and in the audit trail. Until M5, W2/W3 tools are denied by the interim risk default.

---

### M4-T01 · Revision 0011 `tools` and tool registry API
- **Depends on:** M3-T02
- **Areas:** `ar_domain/tools/**`, migration 0011, `ar_api/routers/{tool_servers.py,tools.py}`
- **Spec:** [spec 08 §2–3](../03-specs/08-tool-registry-mcp.md#2-lifecycle), [schema §6](../04-data/schema.md#6-tools-ar_domaintools), [mcp-integration §5](../05-contracts/mcp-integration.md#5-discovery-and-registration-flow)
- **Do:** Tables of schema §6 with the `tool_versions_immutable` trigger; lifecycle (draft → in_review → approved/rejected; deprecated; disabled); endpoints `GET/POST /api/v1/tool-servers`, `GET/PATCH/DELETE /api/v1/tool-servers/{server_id}`, versions `GET/POST /api/v1/tool-servers/{server_id}/versions`, `GET /api/v1/tool-servers/{server_id}/versions/{version_id}`, `PATCH /api/v1/tool-servers/{server_id}/versions/{version_id}/tools/{tool_version_id}` (risk class override, description edits, enable), `:submit`, `:approve` (reviewer ≠ submitter unless `security.allow_self_review`), `:reject`, server `:deprecate`, `:disable`, `:enable`; `GET /api/v1/tools`, `GET /api/v1/tools/{tool_id}`, `POST /api/v1/tools/{tool_id}:disable`, `:enable`. Seed platform built-in servers (spec 08 §9, mcp-integration §8). Register resolvers `tool` and `tool_server` for agent validation.
- **Done when:** an approved version's tools are immutable except embeddings; agents can bind approved tools only.
- **Tests:** integration per endpoint; trigger tests; self-review rule; resolver tests.

### M4-T02 · Credential providers, connections and token minting
- **Depends on:** M4-T01, M1-T07
- **Areas:** `ar_domain/secrets/{credentials.py,tokens.py,oauth.py}`, `ar_api/routers/{credential_providers.py,connections.py}`
- **Spec:** [spec 03 §3–5](../03-specs/03-secrets-credentials.md#3-public-api)
- **Do:** `GET/POST /api/v1/credential-providers`, `PATCH/DELETE /api/v1/credential-providers/{provider_id}`; `GET /api/v1/connections`, `POST /api/v1/connections/{provider_id}:start` (PKCE, state in Valkey), `GET /api/v1/connections/oauth/callback`, `DELETE /api/v1/connections/{grant_id}`; `access_token_for` with encrypted Valkey cache and refresh rotation; delegation-token refresh + RFC 8693 exchange; `CredentialRequired` → `tool_call.failed` with `connect_url` and a `credential_required` notification.
- **Done when:** OAuth flow works end-to-end against Keycloak acting as a test OAuth provider; refresh-token rotation persisted.
- **Tests:** integration with Keycloak; `invalid_grant` path; cache encryption (Valkey value is not plaintext).

### M4-T03 · `mcp-gateway` core execution pipeline
- **Depends on:** M4-T02
- **Areas:** `services/mcp_gateway/src/ar_mcp_gateway/{routes.py,catalog.py,pipeline.py,mcp_client.py,auth_modes.py,results.py,wrapping.py,discovery.py,builtins/__init__.py}`
- **Spec:** [spec 08 §4–7, §12–13](../03-specs/08-tool-registry-mcp.md#5-execution-pipeline-post-internalv1tool-callsexecute), [mcp-integration](../05-contracts/mcp-integration.md), [internal-apis §3](../05-contracts/internal-apis.md#3-mcp-gateway-base-httpmcp-gateway8002), [ADR-0006](../02-architecture/adr/ADR-0006-mcp-tool-protocol.md)
- **Do:** `POST /internal/v1/catalog:resolve`, `POST /internal/v1/tool-calls:execute`, `POST /internal/v1/tool-calls:test`, `POST /internal/v1/discover`; MCP Streamable HTTP client (spec 2026-07-28, headers of mcp-integration §3, auth modes §4); pipeline steps of spec 08 §5 with the policy step implemented as an interface `PolicyDecider` whose interim implementation returns the risk default (R0/R1/W1 allow, W2/W3 `denied` with `error.code=policy_denied` and message "approvals are not enabled yet") — replaced in M5-T03; JSON Schema validation; `args_hash`; result processing (redaction hook, size limits, offload to `files(kind='tool_result')`, untrusted wrapping per prompt-injection §3); `tool_calls` rows; audit; usage `tool_calls` metric; `/internal/v1/connectors/{tool_server_version_id}/config` on `api`.
- **Done when:** calls to a test MCP server succeed with each auth mode; schema-invalid arguments return a model-readable error without calling the server.
- **Tests:** integration with the SDK example server; unit tests per pipeline step; property test: wrapping cannot be escaped by content containing the closing marker.

### M4-T04 · Runtime tool calling
- **Depends on:** M4-T03, M3-T03
- **Areas:** `ar_runtime/activities/{execute_tool_call.py,model_step.py}`, `ar_runtime/workflows/agent_run.py`, `ar_api/routers/runs.py`
- **Spec:** [spec 07 §2](../03-specs/07-agent-runtime.md#2-workflow-agentrunworkflow), [stream-events](../05-contracts/stream-events.md)
- **Do:** Tool list from `catalog:resolve` (cached `ar:run:{run_id}:tools`); parallel tool calls (bounded by definition), `execute_tool_call` activity with heartbeats and retry policy (non-retryable for validation/policy errors), `tool_call.started/completed/failed` events, `tool_use`/`tool_result` content parts, consecutive error limit `AR_CONSECUTIVE_TOOL_ERROR_LIMIT`, max tool calls budget; enable `GET /api/v1/runs/{run_id}/tool-calls`.
- **Done when:** a scripted fake-llm run with two parallel tool calls and one failure completes with correct events and persisted parts.
- **Tests:** Temporal tests (parallel, retry, error limit, cancel during tool call); replay determinism test updated.

### M4-T05 · Built-in servers: files, conversations, web, plan, tools.search
- **Depends on:** M4-T04, M2-T07
- **Areas:** `ar_mcp_gateway/builtins/{files.py,conversations.py,web.py}`, `ar_runtime/control/{plan.py,tool_search.py}`, `ar_domain/tools/embeddings.py`
- **Spec:** [spec 08 §9](../03-specs/08-tool-registry-mcp.md#9-built-in-tool-schemas-platform-servers-executed-in-process-by-mcp-gateway-unless-noted), [spec 07 §6, §8](../03-specs/07-agent-runtime.md#6-planning-planupdate)
- **Do:** `files.list`, `files.read` (`files.attach_to_sandbox` lands in M6-T06), `conversations.search_history`, `web.fetch` via Squid egress proxy (allowlist + tenant feature `web_fetch`); control tools `plan__update` (`apply_plan_update`, `plan.updated` event) and `tools__search` (`search_tools` activity; pgvector tool embeddings computed on approval with alias `embed`, `dimensions=1024`).
- **Done when:** tool search activates automatically for agents with > 30 tools; plan updates render as events.
- **Tests:** unit + integration per tool; tool-search relevance test with 50 synthetic tools.

### M4-T06 · `mcp-openapi` connector
- **Depends on:** M4-T03
- **Areas:** `connectors/mcp_openapi/**`, `ar_domain/tools/openapi_import.py`
- **Spec:** [spec 08 §11](../03-specs/08-tool-registry-mcp.md#11-mcp-openapi-connector-runtime-connectorsmcp_openapi-port-8011)
- **Do:** Multi-tenant MCP server; config from `api`; OpenAPI 3.0/3.1 parsing (file `kind='openapi_spec'`), operation selection at version creation, schema merge, upstream auth modes, egress through proxy, HTTP-method → default risk class (GET R0, POST/PUT/PATCH W1, DELETE W2, overridable).
- **Done when:** the Petstore 3.1 document yields tools callable through the gateway.
- **Tests:** integration against a local stub API (respx/uvicorn); schema merge unit tests.

### M4-T07 · `mcp-sql` connector and data connections API
- **Depends on:** M4-T03
- **Areas:** `connectors/mcp_sql/**`, `ar_api/routers/data_connections.py`
- **Spec:** [spec 08 §3, §10](../03-specs/08-tool-registry-mcp.md#10-mcp-sql-connector-runtime-connectorsmcp_sql-port-8010)
- **Do:** `GET/POST /api/v1/data-connections`, `GET/PATCH/DELETE /api/v1/data-connections/{connection_id}`, `POST /api/v1/data-connections/{connection_id}:test`, `GET /api/v1/data-connections/{connection_id}/schema`; `mcp-sql` tools `{slug}.list_tables`, `{slug}.describe_table`, `{slug}.run_query`; `ar_mcp_sql.guard` (sqlglot single-SELECT, allowlist, row/byte limits, statement timeout, read-only transaction); identity modes; `POST /internal/v1/connections:test`.
- **Done when:** guard rejects DDL/DML/multi-statements/functions with side effects; queries outside the allowlist fail.
- **Tests:** hypothesis + corpus tests for the guard (≥ 200 malicious samples in `connectors/mcp_sql/tests/corpus/`); integration with Postgres container.

### M4-T08 · `ar_connector_sdk`
- **Depends on:** M4-T03
- **Areas:** `libs/ar_connector_sdk/**`, `libs/ar_connector_sdk/examples/{ticketing_server,hello_connector}/`
- **Spec:** [connector-sdk](../05-contracts/connector-sdk.md)
- **Do:** Tool server helper (context header verification against platform JWKS, user identity accessors, annotations helpers), knowledge connector helper (interface used in M7-T04), conformance checks runner, example ticketing MCP server used by e2e tests, docs in package README.
- **Done when:** conformance runner passes for the examples and fails for a deliberately broken server.
- **Tests:** unit + conformance tests.

### M4-T09 · Tool test console, tool-call log, drift checks
- **Depends on:** M4-T04
- **Areas:** `ar_api/routers/{tools.py,tool_calls.py}`, `ar_system/workflows/tool_drift_check.py`
- **Spec:** [spec 08 §3, §8](../03-specs/08-tool-registry-mcp.md#8-tooldriftcheckworkflow-system-worker-ar-system)
- **Do:** `POST /api/v1/tools/{tool_id}:test` (synthetic test run, policy applies, W2/W3 only with dry-run support), `GET /api/v1/tool-calls` (filters, redacted args for non-owners); `ToolDriftCheckWorkflow` (schedule `AR_TOOL_DRIFT_INTERVAL`; re-discovers approved versions; manifest change → server `status='pending_review'`, diff in `review_notes`, outbox `tool_server.review_requested` with reason `manifest_drift`, notification `tool_review_requested`; meanwhile the gateway drift guard fails calls with `tool_manifest_drift` until a version is re-approved).
- **Done when:** a changed upstream schema is detected, never silently adopted, and calls fail with `tool_manifest_drift` until re-approval.
- **Tests:** integration test console; Temporal drift test with a mutating test server.

### M4-T10 · Web: tools, review queue, connections, tool-call UI
- **Depends on:** M4-T05, M4-T06, M4-T07, M4-T09
- **Areas:** `apps/web/src/app/(app)/tools/**`, `apps/web/src/app/(app)/connections/**`, `apps/web/src/components/chat/ToolCallCard/**`
- **Spec:** [spec 19 `/tools`, `/connections`](../03-specs/19-web-app.md)
- **Do:** Tool servers table, registration wizard (Remote MCP / OpenAPI / SQL), version diff viewer, review queue with approve/reject, tool detail with risk class overrides and test console, connections page (connect/disconnect), chat tool-call cards (name, status, arguments for owners, result preview, "connect account" CTA on `credential_required`), plan panel.
- **Done when:** the M4 exit-criteria flow is executable through the UI.
- **Tests:** Vitest; Playwright register → review → bind to agent → chat calls tool; axe.
