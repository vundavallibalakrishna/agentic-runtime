# Request flows

Sequence diagrams for the main flows. Endpoint and table names are those of the specs linked in each section.

## 1. Login (BFF)

Specs: [spec 01](../03-specs/01-api-bff.md), [spec 02](../03-specs/02-identity-tenancy.md).

```mermaid
sequenceDiagram
  participant B as Browser
  participant W as web
  participant A as api
  participant K as Keycloak
  participant V as Valkey
  B->>W: GET /chat (no session)
  W-->>B: redirect /login
  B->>A: GET /api/v1/auth/login?tenant=acme&return_to=/chat
  A-->>B: 302 to Keycloak (PKCE, organization=acme, scope openid offline_access)
  B->>K: authenticate (brokered company IdP)
  K-->>B: 302 /api/v1/auth/callback?code
  B->>A: GET /api/v1/auth/callback
  A->>K: token exchange (code + verifier)
  A->>A: upsert users row (JIT), map groups, store offline token as __delegation__ secret
  A->>V: SET ar:sess:{sid} {tokens, user, tenant, csrf}
  A-->>B: Set-Cookie ar_session (HttpOnly), ar_csrf, 302 /chat
```

## 2. Chat turn with streaming

Specs: [spec 06](../03-specs/06-conversations-runs.md), [spec 07](../03-specs/07-agent-runtime.md).

```mermaid
sequenceDiagram
  participant B as web (browser)
  participant A as api
  participant T as Temporal
  participant R as runtime-worker
  participant G as model-gateway
  participant M as model server
  participant V as Valkey
  B->>A: POST /api/v1/conversations/{conversation_id}/messages
  A->>A: tx: message + run(queued) + outbox run.start_requested
  A->>T: start AgentRunWorkflow run-{run_id}
  A-->>B: 202 {message, run}
  B->>A: GET /api/v1/runs/{run_id}/events (SSE)
  T->>R: start_run, recall_memory, model_step
  R->>G: POST /v1/chat/completions (stream, alias reasoning)
  G->>M: upstream request
  M-->>G: token chunks
  G-->>R: chunks
  R->>V: XADD message.delta (coalesced)
  A->>V: XREAD
  A-->>B: SSE message.delta ...
  R->>R: persist assistant message, run_steps
  R->>V: XADD message.completed, run.completed
  A-->>B: SSE run.completed
```

## 3. Tool call requiring approval

Specs: [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 09](../03-specs/09-policy-approvals.md).

```mermaid
sequenceDiagram
  participant R as runtime-worker
  participant X as mcp-gateway
  participant O as OPA
  participant DB as Postgres
  participant U as approver (web/Slack)
  participant A as api
  participant S as tool server (MCP)
  R->>X: POST /internal/v1/tool-calls:execute
  X->>X: entitlement, rate limit, schema validation, args_hash
  X->>O: decision(PolicyInput)
  O-->>X: require_approval
  X->>DB: insert approvals + outbox approval.requested
  X-->>R: requires_approval {approval_id, expires_at}
  R->>R: status waiting_approval, wait signal
  U->>A: POST /api/v1/approvals/{approval_id}:decide {approve, args_hash}
  A->>DB: approval_decisions, approvals.status=approved
  A->>R: signal approval_decided
  R->>X: execute again with approval_id
  X->>DB: verify + consumed_at
  X->>S: tools/call (credentials by auth mode)
  S-->>X: result
  X->>X: redact, neutralise, classify, truncate, wrap
  X-->>R: succeeded + content_for_model
```

## 4. Knowledge-grounded answer (RAG)

Specs: [spec 10](../03-specs/10-knowledge.md).

```mermaid
sequenceDiagram
  participant R as runtime-worker
  participant X as mcp-gateway
  participant G as model-gateway
  participant Q as RetrievalStore (Postgres pgvector by default)
  participant C as source connector
  R->>X: knowledge.search {query}
  X->>G: /v1/embeddings (embed)
  X->>Q: hybrid search: HNSW dense + tsvector lexical, filter tenant/collection/version/acl/classification in-query, RRF
  Q-->>X: 50 candidates
  X->>G: /v1/rerank
  X->>C: check_access (only sensitivity=high)
  X-->>R: hits with citation indices (or "no relevant documents")
  R->>R: model cites [n], emits citation.added
```

## 5. Document ingestion

Specs: [spec 10 §4](../03-specs/10-knowledge.md#4-ingestion-workflows-ingest-worker).

```mermaid
sequenceDiagram
  participant TS as Temporal Schedule
  participant I as ingest-worker
  participant SRC as Source system
  participant S3 as Object store
  participant G as model-gateway
  participant DB as Postgres (pgvector adapter)
  TS->>I: SourceSyncWorkflow(source_id)
  I->>SRC: list_changes(cursor)
  loop each changed item (child IngestDocumentWorkflow)
    I->>SRC: fetch
    I->>S3: raw file
    I->>I: parse (Docling) → chunk → contextualise
    I->>G: embeddings (batch 64)
    I->>DB: one transaction: document_chunks + chunk_embeddings (vector, tsvector, acl), documents.status=indexed
  end
  I->>DB: save cursor, ingestion_jobs stats
```

## 6. Routine run with delivery

Specs: [spec 15](../03-specs/15-routines-triggers.md).

```mermaid
sequenceDiagram
  participant TS as Temporal Schedule
  participant SY as system-worker
  participant R as runtime-worker
  participant X as mcp-gateway
  participant CH as channels
  participant SL as Slack
  TS->>SY: RoutineRunWorkflow
  SY->>SY: accept event (dedupe, cap, concurrency), owner + delegation checks
  SY->>R: child AgentRunWorkflow (trigger routine)
  R->>R: agent loop (owner identity)
  R->>X: delivery.slack_post (standing approval → allow)
  X->>CH: POST /internal/v1/outbound
  CH->>SL: chat.postMessage
  R-->>SY: RunResult
  SY->>SY: complete event, next_run_at, outbox routine.run_completed
```

## 7. Subagent delegation

Specs: [spec 07 §7](../03-specs/07-agent-runtime.md#7-subagents-agentsdelegate).

```mermaid
sequenceDiagram
  participant P as parent AgentRunWorkflow
  participant DB as Postgres
  participant C as child AgentRunWorkflow
  P->>P: model calls agents__delegate {agent, task}
  P->>DB: create_child_run (depth+1, budget = min(child, remaining))
  P->>C: start child run-{child_id}
  C->>C: own loop, tools, approvals (on conversation stream)
  C-->>P: RunResult {final_text, files, usage}
  P->>P: add usage, emit subagent.completed, tool result to model
```

## 8. Slack message

Specs: [spec 16](../03-specs/16-channels.md).

```mermaid
sequenceDiagram
  participant SL as Slack
  participant CH as channels
  participant A as api
  participant V as Valkey
  SL->>CH: POST /channels/slack/events (signed)
  CH-->>SL: 200 (ack < 3 s)
  CH->>A: POST /internal/v1/channels/inbound
  A->>A: identity map, agent routing, channel_threads, post_message
  A-->>CH: {conversation_id, run_id}
  CH->>SL: placeholder message
  loop run events
    CH->>V: XREAD ar:run:{run_id}:events
    CH->>SL: chat.update (≤ every 1.5 s)
  end
  CH->>SL: final message + files + citations
```

## 9. Sandbox code execution

Specs: [spec 12](../03-specs/12-sandbox-manager.md).

```mermaid
sequenceDiagram
  participant X as mcp-gateway
  participant SM as sandbox-manager
  participant K as Kubernetes
  participant SA as sandbox-agent
  participant SQ as Squid
  X->>SM: POST /internal/v1/sandboxes:ensure {scope_key}
  SM->>K: claim warm pod / create pod (gVisor)
  SM->>SA: POST /admin/claim {token, egress identity}
  SM-->>X: {endpoint_url, token}
  X->>SA: tools/call sandbox.exec (bearer token)
  SA->>SQ: pip install via proxy (allowlist check)
  SA-->>X: progress (stdout) ... result {exit_code, new_files}
  X->>SM: files:export /workspace/outputs/chart.png
  X-->>X: artifact.created
```
