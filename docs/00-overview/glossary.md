# Glossary

Canonical terms. Code, API fields, tables and UI copy use these names. Deployable and module names: [service-decomposition](../02-architecture/service-decomposition.md).

| Term | Definition | Where defined |
|---|---|---|
| **Tenant** | A company using the platform; maps 1:1 to a Keycloak Organization and a `tenants` row. | [spec 02](../03-specs/02-identity-tenancy.md) |
| **Plan** | Commercial/limit package (`plans`) whose `limits` (PlanLimits) bound quotas and settings. | [spec 02](../03-specs/02-identity-tenancy.md) |
| **Isolation tier** | `shared`, `dedicated_db`, `dedicated_cluster`. | [tenancy-isolation](../02-architecture/tenancy-isolation.md) |
| **Deployment mode** | `saas` (multi-tenant) or `single_tenant` (on-prem/k8s); `AR_DEPLOYMENT_MODE`. | [deployment-modes](deployment-modes.md) |
| **User** | A person in a tenant (`users`), provisioned JIT, by SCIM or by invitation. | spec 02 |
| **Group** | IdP/SCIM or local group of users, used for ACLs and role assignment. | spec 02 |
| **Team** | Platform org unit that owns agents, tool servers, collections, skills; has leads and members. | spec 02 |
| **Role / permission** | Named bundle of permission keys (e.g. `agents:publish`) assigned to users, groups or service accounts at tenant or team scope. | [authn-authz](../06-security/authn-authz.md) |
| **Service account** | Non-human principal with API keys, optionally allowed to act on behalf of users (`allow_on_behalf_of`). | spec 02 |
| **Principal** | The authenticated actor of a request: user, service account, platform admin, system. | spec 01 |
| **Agent** | A configured assistant (`agents`) with versions. | [spec 05](../03-specs/05-agent-registry.md) |
| **Agent version** | Row in `agent_versions` with `state` `draft` (editable, at most one per agent), `published` (immutable, at most one current) or `superseded`. | spec 05 |
| **Agent definition** | Declarative YAML/JSON document describing an agent. | [definition-schema](../05-contracts/definition-schema.md) |
| **Bundle** | Export/import archive of agents, skills, policies, routines (no secrets). | spec 05 |
| **Model alias** | Stable name (`reasoning`, `fast`, `vision`, `embed`, `rerank`, or tenant-defined) mapped to concrete models. | [spec 04](../03-specs/04-model-gateway.md) |
| **Model provider** | A registered company-hosted inference endpoint (OpenAI-compatible, TEI, etc.). | spec 04 |
| **Conversation** | A chat thread between a user and an agent (`conversations`), on any channel. | [spec 06](../03-specs/06-conversations-runs.md) |
| **Message** | One turn item (`messages`) with ContentParts (text, file, tool_use, tool_result, citation, …). | spec 06 |
| **Run** | One durable execution of an agent (`runs`), triggered by chat, API, routine, subagent delegation or eval; a Temporal `AgentRunWorkflow`. | spec 06, [spec 07](../03-specs/07-agent-runtime.md) |
| **Run step** | One model step or tool batch within a run (`run_steps`). | spec 07 |
| **Run event** | Streamed event (`run.started`, `message.delta`, `tool_call.started`, `approval.requested`, …). | [stream-events](../05-contracts/stream-events.md) |
| **Subagent / child run** | A run started by another run via `agents__delegate`; a Temporal child workflow. | spec 07 §7 |
| **Budget** | Per-run caps on steps, tokens, cost, wall time, tool calls. | spec 07 |
| **Plan (run plan)** | The agent-maintained checklist updated with `plan__update`; shown in the UI. Not to be confused with *Plan* (limits). | spec 07 |
| **Compaction** | Summarising older context when the prompt nears the context limit. | [spec 11](../03-specs/11-memory.md) |
| **Tool server** | A registered MCP server (remote, OpenAPI-generated, SQL, or built-in) with versions. | [spec 08](../03-specs/08-tool-registry-mcp.md) |
| **Tool** | One callable operation of a tool server; qualified name `server.tool`, model-facing name `server__tool`. | spec 08 |
| **Built-in server** | Platform-provided MCP server served by `mcp-gateway` (knowledge, memory, files, skills, conversations, web, sandbox, browser, delivery) or control tools (agents, plan, tools.search). | [mcp-integration](../05-contracts/mcp-integration.md) |
| **Data connection** | A registered database (`data_connections`) exposed through `mcp-sql`. | spec 08 |
| **Risk class** | `R0` read public/own, `R1` read sensitive, `W1` reversible write to own scope, `W2` write visible to others, `W3` irreversible/production/financial. | [spec 09](../03-specs/09-policy-approvals.md) |
| **Policy** | Rego rules (package `ar.policy`) evaluated by OPA per tool call; outcome allow / deny / require_approval. | spec 09 |
| **Approval** | Human decision on one tool call, bound to its `args_hash`, single use. | spec 09, [ADR-0015](../02-architecture/adr/ADR-0015-approval-args-hash.md) |
| **Standing approval** | Pre-authorisation for repeated calls matching a pattern (never W3). | spec 09 |
| **Step-up** | Re-authentication within `AR_STEP_UP_TTL_S` (600 s) required for sensitive actions. | spec 01 |
| **Credential provider / connection** | OAuth or API-key provider configuration; a user's grant to it (`credential_grants`). | [spec 03](../03-specs/03-secrets-credentials.md) |
| **Secret ref** | Pointer (`secret_refs`) to a secret stored in vault or encrypted in DB. | spec 03 |
| **Collection** | Knowledge container (`knowledge_collections`) with sources and documents. | [spec 10](../03-specs/10-knowledge.md) |
| **Source** | A connector configuration feeding a collection (upload, web, sharepoint, confluence, gdrive, s3). | spec 10 |
| **Document / chunk** | Ingested item and its indexed pieces (`document_chunks`, indexed through the `RetrievalStore` port: `chunk_embeddings` rows with the default pgvector adapter). | spec 10 |
| **ACL principals** | `user:{id}`, `group:{id}`, `team:{id}`, `tenant:*` attached to chunks and matched at query time. | spec 10 |
| **Citation** | Reference `[n]` from an answer to a retrieved chunk or tool result. | spec 06 |
| **Memory fact** | Durable remembered statement (`memory_facts`) with scope `user`, `agent_user`, `agent`, `team`. | spec 11 |
| **Sandbox** | Isolated pod (gVisor/Kata) with `sandbox-agent` for code execution and browsing. | [spec 12](../03-specs/12-sandbox-manager.md) |
| **Sandbox template** | Image + resources + egress + packages policy for sandboxes. | spec 12 |
| **File / artifact** | Stored object (`files`); `kind` is one of `upload`, `artifact` (agent-generated), `tool_result`, `sandbox_snapshot`, `knowledge_raw`, `knowledge_parsed`, `skill_asset`, `avatar`, `export`, `openapi_spec`, `eval_dataset`, `event_payload`. | [spec 13](../03-specs/13-files-artifacts.md) |
| **Skill** | Versioned package of instructions + assets loaded on demand (`skills.load`); version 0 is the mutable draft. | [spec 14](../03-specs/14-skills.md) |
| **Routine** | Unattended agent task with triggers (schedule, webhook, event, poll) and delivery. | [spec 15](../03-specs/15-routines-triggers.md) |
| **Routine event** | One accepted/rejected trigger firing (`routine_events`). | spec 15 |
| **Delivery** | Posting a routine/run result to a channel, email or webhook via `delivery.*` tools. | spec 15 |
| **Channel** | Surface where users talk to agents: `web`, `slack`, `teams`, `api`, `widget`; plus `email` for outbound delivery and notifications. Integrations are `channel_integrations.kind` ∈ `slack`, `teams`, `email`, `widget`. | [spec 16](../03-specs/16-channels.md) |
| **Channel integration** | Tenant's configured Slack/Teams/email/widget app (`channel_integrations`). | spec 16 |
| **Audit event** | Hash-chained, append-only record of a security-relevant action (`audit_events`). | [spec 17](../03-specs/17-audit-usage-metering.md), [audit](../06-security/audit.md) |
| **Usage event / quota** | Metered consumption (tokens, tool calls, sandbox seconds, storage) and limits on it. | spec 17 |
| **Outbox event / domain event** | Transactionally recorded event relayed to subscribers. | [domain-events](../05-contracts/domain-events.md) |
| **Webhook** | Tenant-registered outbound HTTP endpoint for domain events. | [spec 20](../03-specs/20-notifications-events.md) |
| **Eval suite / case / run** | Test set of agent tasks with graders and their executions. | [spec 18](../03-specs/18-observability-eval.md) |
| **Untrusted content** | Any tool output, retrieved document, file content or channel message from others; wrapped and never treated as instructions. | [prompt-injection](../06-security/prompt-injection.md) |
| **Internal JWT** | Short-lived service-to-service token carrying acting context. | [internal-apis](../05-contracts/internal-apis.md) |
| **Evidence item** | Immutable bytes plus a signed manifest in the evidence bucket. | [spec 21](../03-specs/21-records-governance.md) |
| **Run record** | Sealed recording of a run, including encrypted tool I/O, so the run can be re-performed. | [spec 18](../03-specs/18-observability-eval.md) |
| **Sign-off** | A person's attestation of a statement and a content hash. Not a tool-call approval. | [spec 09](../03-specs/09-policy-approvals.md) |
| **Guest principal** | An external participant with a time-boxed grant. Not a user. | [spec 21](../03-specs/21-records-governance.md) |
| **Content pack** | A signed bundle with an id and a version. A solution pack adds schema and UI through the extension framework. | [spec 05](../03-specs/05-agent-registry.md) |
| **Legal hold** | A matter that stops disposition of the records it covers. | spec 21 |
| **Agent card** | The platform's record of one published agent version. | spec 21 |
| **Binder** | A ZIP of selected records, a hash manifest, and an offline verifier. | spec 21 |
