# Entity-relationship diagrams

Columns are abbreviated; the authoritative definition is [schema.md](schema.md). Split into domains for readability. Every entity except `PLANS` and `TENANTS` carries `tenant_id`.

## 1. Identity, tenancy, secrets

```mermaid
erDiagram
  PLANS ||--o{ TENANTS : "plan_id"
  TENANTS ||--o{ TENANT_DOMAINS : has
  TENANTS ||--o{ IDENTITY_PROVIDERS : brokers
  TENANTS ||--o{ USERS : has
  TENANTS ||--o{ GROUPS : has
  GROUPS ||--o{ GROUP_MEMBERS : contains
  USERS ||--o{ GROUP_MEMBERS : member
  TENANTS ||--o{ TEAMS : has
  TEAMS ||--o{ TEAM_MEMBERS : contains
  USERS ||--o{ TEAM_MEMBERS : member
  GROUPS |o--o{ TEAMS : mirrors
  ROLES ||--o{ ROLE_ASSIGNMENTS : granted
  TENANTS ||--o{ SERVICE_ACCOUNTS : has
  SERVICE_ACCOUNTS ||--o{ API_KEYS : authenticates
  USERS ||--o{ API_KEYS : personal
  TENANTS ||--o{ SCIM_TOKENS : has
  TENANTS ||--o{ INVITATIONS : sends
  TENANTS ||--o{ SECRET_REFS : stores
  SECRET_REFS |o--o| ENCRYPTED_SECRETS : "db_encrypted backend"
  CREDENTIAL_PROVIDERS ||--o{ CREDENTIAL_GRANTS : issues
  USERS ||--o{ CREDENTIAL_GRANTS : connects
  SECRET_REFS ||--o{ CREDENTIAL_GRANTS : holds
  TENANTS { uuid id PK  citext slug  text status  uuid plan_id FK  text isolation_tier }
  USERS { uuid id PK  uuid tenant_id FK  text idp_subject  citext email  text status  jsonb attributes }
  ROLE_ASSIGNMENTS { uuid id PK  uuid role_id FK  text principal_type  uuid principal_id  text scope_type  uuid scope_id }
  SECRET_REFS { uuid id PK  text name  text backend  text path }
```

## 2. Agents, models, tools, policy

```mermaid
erDiagram
  MODEL_PROVIDERS ||--o{ MODELS : serves
  MODELS ||--o{ MODEL_ALIASES : "primary / fallback"
  AGENTS ||--o{ AGENT_VERSIONS : versions
  AGENT_VERSIONS ||--o{ AGENT_VERSION_BINDINGS : references
  TOOL_SERVERS ||--o{ TOOL_SERVER_VERSIONS : versions
  TOOL_SERVERS ||--o{ TOOLS : exposes
  TOOLS ||--o{ TOOL_VERSIONS : versions
  TOOL_SERVER_VERSIONS ||--o{ TOOL_VERSIONS : "snapshot of"
  DATA_CONNECTIONS |o--o{ TOOL_SERVER_VERSIONS : "sql config"
  CREDENTIAL_PROVIDERS |o--o{ TOOL_SERVER_VERSIONS : "user_oauth"
  POLICIES ||--o{ POLICY_VERSIONS : versions
  AGENT_VERSIONS }o--o{ TOOLS : "binding kind=tool"
  AGENT_VERSIONS }o--o{ KNOWLEDGE_COLLECTIONS : "binding kind=knowledge_collection"
  AGENT_VERSIONS }o--o{ SKILLS : "binding kind=skill"
  AGENT_VERSIONS }o--o{ AGENTS : "binding kind=subagent"
  AGENTS { uuid id PK  citext slug  text status  timestamptz disabled_at  uuid published_version_id FK }
  AGENT_VERSIONS { uuid id PK  int version  text state  jsonb definition  text definition_hash }
  TOOL_VERSIONS { uuid id PK  text description  text description_hash  jsonb input_schema  text risk_class }
  MODEL_ALIASES { uuid id PK  text alias  uuid primary_model_id FK  uuid[] fallback_model_ids }
```

## 3. Conversations, runs, tool calls, approvals

```mermaid
erDiagram
  USERS ||--o{ CONVERSATIONS : owns
  AGENTS ||--o{ CONVERSATIONS : serves
  CONVERSATIONS ||--o{ CONVERSATION_SHARES : "shared with"
  CONVERSATIONS ||--o{ MESSAGES : contains
  CONVERSATIONS ||--o{ RUNS : executes
  RUNS ||--o{ RUNS : "parent_run_id (subagents)"
  RUNS ||--o{ RUN_STEPS : has
  RUNS ||--o{ RUN_EVENTS : streams
  RUNS ||--o{ MESSAGES : produces
  MESSAGES ||--o{ MESSAGE_FEEDBACK : rated
  RUNS ||--o{ TOOL_CALLS : issues
  TOOL_VERSIONS ||--o{ TOOL_CALLS : "invoked as"
  TOOL_CALLS ||--o| APPROVALS : "may require"
  APPROVALS ||--o{ APPROVAL_DECISIONS : collects
  TOOLS ||--o{ STANDING_APPROVALS : "pre-approved"
  RUNS ||--o{ FILES : creates
  ROUTINES ||--o{ RUNS : triggers
  RUNS { uuid id PK  uuid parent_run_id FK  int depth  text trigger  text status  text temporal_workflow_id  jsonb budget  jsonb usage }
  TOOL_CALLS { uuid id PK  text qualified_name  text args_hash  text policy_decision  text status  text idempotency_key }
  APPROVALS { uuid id PK  uuid tool_call_id FK  text status  text args_hash  int required_approvals  timestamptz expires_at }
```

## 4. Knowledge, memory, sandboxes, files, skills, routines, channels

```mermaid
erDiagram
  KNOWLEDGE_COLLECTIONS ||--o{ KNOWLEDGE_SOURCES : "fed by"
  KNOWLEDGE_SOURCES ||--o{ DOCUMENTS : yields
  DOCUMENTS ||--o{ DOCUMENT_CHUNKS : "split into"
  DOCUMENT_CHUNKS ||--o| CHUNK_EMBEDDINGS : "indexed as (pgvector adapter)"
  KNOWLEDGE_SOURCES ||--o{ INGESTION_JOBS : runs
  USERS ||--o{ MEMORY_FACTS : "scope=user"
  AGENTS ||--o{ MEMORY_FACTS : "scope=agent"
  TEAMS ||--o{ MEMORY_FACTS : "scope=team"
  SANDBOX_TEMPLATES ||--o{ SANDBOXES : instantiates
  CONVERSATIONS |o--o{ SANDBOXES : "scope=conversation"
  FILES |o--o| SANDBOXES : snapshot
  SKILLS ||--o{ SKILL_VERSIONS : versions
  ROUTINES ||--o{ ROUTINE_EVENTS : receives
  CHANNEL_INTEGRATIONS ||--o{ CHANNEL_IDENTITIES : maps
  CHANNEL_INTEGRATIONS ||--o{ CHANNEL_THREADS : tracks
  CHANNEL_THREADS }o--|| CONVERSATIONS : "is"
  DOCUMENTS { uuid id PK  text external_id  text version_hash  text[] acl_principals  text status }
  CHUNK_EMBEDDINGS { uuid chunk_id PK  int index_version  text[] acl  smallint dims  halfvec embedding  tsvector tsv }
  MEMORY_FACTS { uuid id PK  text scope  text content  vector embedding  text trust_level  text status }
  SANDBOXES { uuid id PK  text scope_key  text status  text driver  text endpoint_url }
  ROUTINES { uuid id PK  text trigger_type  jsonb trigger_config  jsonb delivery  text status }
```

## 5. Audit, usage, evaluation, events

```mermaid
erDiagram
  TENANTS ||--o{ AUDIT_EVENTS : "hash chain"
  TENANTS ||--o{ USAGE_EVENTS : meters
  USAGE_EVENTS }o--|| USAGE_DAILY : "rolled up"
  TENANTS ||--o{ QUOTAS : limits
  EVAL_SUITES ||--o{ EVAL_CASES : contains
  EVAL_SUITES ||--o{ EVAL_RUNS : executes
  EVAL_RUNS ||--o{ EVAL_RESULTS : produces
  EVAL_CASES ||--o{ EVAL_RESULTS : "result of"
  OUTBOX_EVENTS ||--o{ WEBHOOK_DELIVERIES : "fan out"
  OUTBOUND_WEBHOOKS ||--o{ WEBHOOK_DELIVERIES : receives
  USERS ||--o{ NOTIFICATIONS : receives
  AUDIT_EVENTS { bigint id PK  bigint tenant_seq  text action  text prev_hash  text hash }
  USAGE_EVENTS { uuid id PK  text metric  bigint quantity  bigint cost_micros  text dedupe_key }
```
