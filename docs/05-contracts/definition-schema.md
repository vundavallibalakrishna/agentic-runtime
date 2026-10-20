# Declarative definition schema (agents, tools, knowledge, routines, policies, skills)

Companies define their capabilities either in the web UI or as YAML/JSON **bundles** checked into Git and imported via the API/CLI. Both paths validate against the same Pydantic models in `ar_contracts.definitions` ([ADR-0018](../02-architecture/adr/ADR-0018-declarative-definitions.md)). JSON Schema files are exported by `make gen` to `libs/ar_contracts/schemas/*.schema.json` and served at `GET /api/v1/schemas/{kind}`.

## 1. Bundle format

```yaml
apiVersion: agentic-runtime.dev/v1
kind: Bundle
metadata:
  name: finance-assistants          # informational
spec:
  resources:
    - kind: Agent
      metadata: { slug: finance-analyst }
      spec: { ...AgentDefinition... }
    - kind: ToolServer
      metadata: { slug: erp }
      spec: { ...ToolServerDefinition... }
```

Each resource can also be a standalone document (`kind: Agent`, `kind: Routine`, ...). Import (`POST /api/v1/bundles:import`, [spec 05](../03-specs/05-agent-registry.md)) is idempotent by `(kind, slug)` (routines and policies by `name`): it creates or creates-a-new-version, never deletes unless `prune: true`. `dry_run: true` returns the plan (create / new_version / unchanged / error per resource). Export (`GET /api/v1/bundles:export?kinds=Agent,Routine`) produces the same format with ids stripped and references expressed by slug/name.

References between resources always use **slugs/names**, resolved to ids at import/save time and stored as ids in `agent_version_bindings`.

Kinds: `Agent`, `ToolServer`, `DataConnection`, `KnowledgeCollection`, `Routine`, `Policy`, `Skill`, `ModelAlias`, `SandboxTemplate`, `ChannelIntegration`. Secrets are never inlined; a definition references a secret by name (`secret: jira-bot-token`), created separately via `POST /api/v1/secrets`.

## 2. AgentDefinition (`kind: Agent`)

Stored in `agent_versions.definition`. Metadata fields (`slug`, `name`, `description`, `visibility`, `owner_team`, `risk_tier`) live on the `agents` row; `spec` is the versioned definition.

```yaml
kind: Agent
metadata:
  slug: incident-analyst
  name: Incident Analyst
  description: Summarises incidents, computes MTTR, files follow-up tickets.
  visibility: tenant            # private | team | tenant
  owner_team: sre               # team slug (optional)
  risk_tier: medium             # low | medium | high
spec:
  persona:
    display_name: Incident Analyst
    greeting: "Hi! Ask me about incidents, MTTR or on-call load."
    avatar_file: null           # file id (uploaded via files API)
  instructions: |
    You help SRE teams analyse incidents. Always cite ticket keys.
    Use the sandbox for any calculation over more than 10 rows.
  starter_prompts:
    - "Summarise last week's P1 incidents with an MTTR chart"
  model:
    alias: reasoning            # chat model alias for planning/tool use
    fast_alias: fast            # used for titles, compaction, memory extraction, routing
    vision_alias: vision        # optional; used when images are present
    params: { temperature: 0.2, top_p: 0.95, max_output_tokens: 4096, reasoning_effort: medium }
    degrade_to_fast: true       # after 2 failed model steps on alias, retry the step on fast_alias
  tools:
    - server: jira              # tool server slug (tenant or built-in)
      version: "^1"             # semver range on server version; resolved at publish
      include: [search_issues, get_issue, create_issue]   # or ["*"]
      overrides:
        create_issue: { require_approval: always }        # tighten only: always | policy (default)
        search_issues: { pinned: true }                   # always loaded when tool search is active
    - server: sandbox           # built-in
      include: ["*"]
    - server: knowledge         # built-in
      include: [search, get_document, list_collections]
  tool_search: { mode: auto, top_k: 12 }   # auto: enabled when > 30 tools are granted; on | off
  knowledge:
    collections: [sre-runbooks, postmortems]
    auto_retrieve: false        # true = run knowledge.search on the user message before the first model call
    top_k: 8
    min_score: 0.30             # answerability threshold after rerank (0..1)
  skills: [mttr-report]
  memory:
    enabled: true
    read_scopes: [user, agent, team, agent_user]
    user_writes: auto           # auto (extraction + explicit) | explicit_only | off
    agent_writes: review        # review (proposals go to pending_review) | off
    recall_top_k: 8
  subagents:
    allowed: [web-researcher]   # agent slugs this agent may delegate to
    allow_self_clone: true      # delegate to a copy of itself with a narrowed tool subset
    max_depth: 2                # 1..3; platform max 3
    max_parallel: 3
  sandbox:
    enabled: true
    template: default           # sandbox template slug
    scope: conversation         # conversation | agent_user | agent
    extra_egress_allowlist: []  # must be a subset of the tenant allowlist
  budget:                       # RunBudget (per top-level run, subagents draw from it)
    max_steps: 30
    max_tokens: 600000
    max_cost_micros: 50000000
    max_wall_clock_s: 1200
    max_tool_calls: 60
    max_parallel_tool_calls: 4
  context:
    compaction_threshold: 0.7   # fraction of the model context window
    tool_result_max_tokens: 4000
    history_max_messages: 40
  output:
    citations: preferred        # required | preferred | off
    show_reasoning: false
  safety:
    pii_masking: false          # mask PII in prompts sent to the model (Presidio)
    injection_classifier: true  # flag suspicious tool output (fast model)
  channels: { web: true, slack: true, teams: true, email: false, api: true, widget: false }
```

### 2.1 Field rules (validated on save; errors use `validation_failed` / `unknown_reference`)

| Field | Type | Constraints |
|---|---|---|
| `persona.display_name` | string | 1..80 |
| `persona.greeting` | string | ≤ 500 |
| `instructions` | string | 1..32,000 chars |
| `starter_prompts` | string[] | ≤ 6 items, each ≤ 200 |
| `model.alias`, `fast_alias`, `vision_alias` | string | must resolve to an active alias of the matching kind (`chat`) visible to the tenant |
| `model.params.temperature` | number | 0..2 |
| `model.params.max_output_tokens` | int | 1..model `max_output_tokens` |
| `model.params.reasoning_effort` | enum | `low`, `medium`, `high` (passed only if the model has capability `reasoning`) |
| `tools[].server` | slug | approved, non-disabled tool server visible to the tenant |
| `tools[].version` | semver range | npm-style (`^1`, `~1.2`, `1.4.0`); must match ≥ 1 approved server version |
| `tools[].include` | string[] | tool names on that server or `["*"]` |
| `tools[].overrides.<tool>.require_approval` | enum | `always`, `policy` |
| `tools[].overrides.<tool>.pinned` | bool | default false; pinned tools are always loaded when tool search is active ([spec 07 §8](../03-specs/07-agent-runtime.md#8-tool-search)) |
| `tool_search.mode` | enum | `auto`, `on`, `off`; `top_k` 4..32 |
| `knowledge.collections` | slug[] | ≤ 20; caller must be able to see each at save time |
| `knowledge.min_score` | number | 0..1 |
| `skills` | slug[] | ≤ 50; published skills |
| `memory.read_scopes` | enum[] | subset of `user`, `agent`, `team`, `agent_user` |
| `subagents.allowed` | slug[] | published agents; no cycles deeper than `max_depth` |
| `subagents.max_depth` | int | 1..3 |
| `sandbox.template` | slug | active template; `extra_egress_allowlist` ⊆ tenant allowlist (`tenants.settings.egress_allowlist`) |
| `budget.*` | int | each ≤ the tenant cap in `tenants.settings.run_budget_caps` |
| `context.compaction_threshold` | number | 0.4..0.9 |
| `output.citations` | enum | `required` forces the model to cite or say it found nothing |

Resolution at **publish**: `tools[].version` ranges are resolved to concrete `tool_server_versions` ids and every included tool to a `tool_versions.id`; these resolved ids are written to `agent_version_bindings` and into `definition.resolved` (read-only block added by the server):

```yaml
resolved:
  tools:
    - { qualified_name: jira.create_issue, tool_id: "...", tool_version_id: "...", risk_class: W2 }
  model: { alias: reasoning }
  skills: [ { slug: mttr-report, skill_version_id: "..." } ]
  knowledge: [ { slug: sre-runbooks, collection_id: "..." } ]
```

A published version therefore always runs exactly the tool versions that were reviewed at publish time. Upgrading a tool server minor version requires re-publishing the agent (UI shows "updates available").

## 3. ToolServerDefinition (`kind: ToolServer`)

```yaml
kind: ToolServer
metadata: { slug: jira, name: Jira, owner_team: platform }
spec:
  kind: remote_mcp              # remote_mcp | openapi | sql
  version: 1.3.0
  description: Jira Data Center tools.
  remote_mcp:
    url: https://mcp-jira.tools.svc.cluster.local/mcp
    headers: { X-Env: prod }
  auth:
    mode: user_oauth            # none | static_secret | user_oauth | token_exchange | internal_jwt
    credential_provider: jira-oauth   # for user_oauth / token_exchange
    secret: null                # for static_secret: secret name
  tools:                        # optional per-tool governance overrides (discovered tools are the source of schemas)
    create_issue: { risk_class: W2, data_classification: internal, timeout_s: 30, rate_limit_per_minute: 20 }
    search_issues: { risk_class: R0 }
  allowed_tools: ["*"]          # subset of discovered tools exposed to agents
```

`openapi` kind:

```yaml
spec:
  kind: openapi
  version: 1.0.0
  openapi:
    spec_file: hr-api-openapi.yaml    # uploaded file name (files.kind='openapi_spec')
    base_url: https://hr.internal.example/api
    operations: [getEmployee, listLeaveBalances]   # operationIds to expose
  auth: { mode: token_exchange, credential_provider: hr-api }
```

`sql` kind:

```yaml
spec:
  kind: sql
  version: 1.0.0
  sql:
    data_connection: finance-replica   # DataConnection name
  auth: { mode: none }                 # credentials come from the data connection
```

Risk class defaults when not overridden: derived from MCP annotations: `readOnlyHint=true` → `R0`; `destructiveHint=true` → `W3`; otherwise `W2`. Reviewers must confirm every tool's risk class before approval.

## 4. DataConnection (`kind: DataConnection`)

```yaml
kind: DataConnection
metadata: { name: finance-replica }
spec:
  engine: postgres
  dsn_secret: finance-replica-dsn   # secret containing postgresql://user:pass@host:5432/db
  identity_mode: service            # service | per_user_mapped | passthrough
  allowlist:
    schemas: [reporting]
    tables: [reporting.invoices, reporting.customers]
    columns_deny: [reporting.customers.pan_number]
  row_limit: 1000
  statement_timeout_s: 30
  classification: confidential
  schema_notes: |
    Fiscal year starts 1 April. amounts are in INR paise.
```

## 5. KnowledgeCollection (`kind: KnowledgeCollection`)

```yaml
kind: KnowledgeCollection
metadata: { slug: sre-runbooks, name: SRE runbooks }
spec:
  description: Runbooks and postmortems for production services.
  visibility: tenant
  acl_mode: source              # source | collection
  sensitivity: normal           # normal | high
  classification: internal
  embedding_alias: embed
  text_search_config: simple    # simple | english (lexical signal of hybrid retrieval)
  chunking: { target_tokens: 512, overlap_pct: 12, contextual: false }
  sources:
    - name: confluence-sre
      kind: confluence          # upload | web | s3 | sharepoint | confluence | google_drive | database | mcp_resource
      confluence: { base_url: https://wiki.example.com, space_keys: [SRE], include_attachments: true }
      secret: confluence-bot
      sync_schedule: "0 * * * *"
      acl_sync_schedule: "*/10 * * * *"
    - name: uploads
      kind: upload
```

`KnowledgeSourceConfig` variants (discriminated by `kind`):

| kind | Required config |
|---|---|
| `upload` | none (files added via API) |
| `web` | `start_urls[]`, `allowed_domains[]`, `max_pages` (≤ 10,000), `max_depth` (≤ 5), `respect_robots` (true) |
| `s3` | `bucket`, `prefix`, `endpoint_url?`, `region?` + secret (access key) |
| `sharepoint` | `tenant_id`, `site_ids[]`, `drive_ids?[]` + secret (app credentials) ; ACLs from Microsoft Graph permissions |
| `confluence` | `base_url`, `space_keys[]`, `include_attachments` + secret ; ACLs from space/page restrictions |
| `google_drive` | `shared_drive_ids[]` + secret (service account with domain-wide delegation) |
| `database` | `data_connection`, `query` (SELECT returning `id, title, body, updated_at, acl?`) |
| `mcp_resource` | `tool_server`, `resource_uri_prefix` (ingests MCP resources) |

## 6. Routine (`kind: Routine`)

```yaml
kind: Routine
metadata: { name: weekly-incident-digest }
spec:
  description: Monday digest of last week's incidents.
  agent: incident-analyst
  agent_version: null           # null = published
  run_as: owner                 # owner | service_account
  service_account: null
  instructions: |
    Summarise last week's P1/P2 incidents, compute MTTR, post to #sre-digest.
  trigger:
    type: schedule              # schedule | webhook | channel_event | email | file_arrival | db_change | manual
    schedule: { cron: "0 9 * * MON", timezone: Asia/Kolkata, jitter_s: 120, catchup_window_s: 3600 }
  event_filter: null            # JMESPath on the event envelope
  delivery:
    - { type: slack, integration: corp-slack, channel: "#sre-digest", pre_approved: true }
    - { type: email, to: [sre-leads@example.com], pre_approved: false }
    - { type: conversation }    # always: run is recorded as a conversation of the owner
  budget: { max_steps: 20, max_tokens: 300000, max_wall_clock_s: 900, max_tool_calls: 30, max_cost_micros: 20000000, max_parallel_tool_calls: 4 }
  max_runs_per_day: 4
  concurrency_policy: skip      # skip | buffer_one | allow
```

`RoutineTrigger` variants:

| type | config |
|---|---|
| `schedule` | `cron` (5-field), `timezone` (IANA), `jitter_s` (0..3600), `catchup_window_s` (0..86400) |
| `webhook` | `{}` (the server generates `webhook_path_token` and an HMAC secret; shown once) ; optional `idempotency_key_path` (JMESPath into body; default header `X-Idempotency-Key` or body sha256) |
| `channel_event` | `integration`, `events: [message, mention, reaction_added, slash_command]`, `channel_ids[]`, `reaction?`, `command?` |
| `email` | `integration` (email channel), `from_filter?`, `subject_filter?` |
| `file_arrival` | `knowledge_source` or `s3: {bucket, prefix}`; fires on new/updated object |
| `db_change` | `data_connection`, `poll_query` (returns rows with `id` + `updated_at`), `poll_interval_s` (≥ 60) |
| `manual` | `{}` (run via API/UI only) |

`DeliveryTarget` variants: `conversation`, `slack {integration, channel, thread_ts?}`, `teams {integration, channel_id | conversation_ref}`, `email {to[], cc[], subject_template?}`, `webhook {url, secret}`, `file {}` (artifacts only). `pre_approved: true` creates a `standing_approvals` row for the delivery tool scoped to this routine with an argument constraint equal to the target (requires `approvals:grant_standing` permission of the owner); without it, delivery is approval-gated to the owner.

## 7. Policy (`kind: Policy`)

```yaml
kind: Policy
metadata: { name: external-email-guard }
spec:
  description: Emails to external domains always need approval by the user's manager group.
  status: active
  priority: 100                    # lower = higher precedence when merging approval requirements (spec 09 §3.1)
  rules:
    - id: ext-email
      effect: require_approval           # allow | deny | require_approval
      match:
        tools: ["mail.send_message", "mail.reply"]   # glob on qualified names
        risk_classes: []                 # any
        agents: []                       # agent slugs; empty = any
        triggers: []                     # chat | api | channel | routine | subagent | eval
        channels: []                     # web | slack | teams | email | api | routine | widget
        user_groups: []                  # group names
        user_attributes: { department: [finance] }
        data_classifications: []
        args:
          - { path: "$.to[*]", op: not_domain_in, value: ["example.com"] }
        time_window: null                # { days: [MON..FRI], from: "09:00", to: "18:00", timezone: Asia/Kolkata }
      approval:
        approvers: { mode: group, groups: [finance-managers] }   # requester | agent_owner | group | users
        required_approvals: 1
        four_eyes: true                  # requester cannot approve
        step_up: false
        ttl_s: 86400
      message: "External emails need manager approval."
  tests:                               # run on every new version; activation requires all to pass
    - name: external recipient needs approval
      input: { tool: { qualified_name: mail.send_message, risk_class: W2 }, user: { attributes: { department: finance } }, args: { to: ["x@other.org"] } }
      expect: { decision: require_approval, rule_ids: [ext-email] }
    - name: internal recipient follows defaults
      input: { tool: { qualified_name: mail.send_message, risk_class: W2 }, user: { attributes: { department: finance } }, args: { to: ["a@example.com"] } }
      expect: { decision: require_approval }
```

Argument predicate ops: `eq`, `neq`, `in`, `not_in`, `matches` (RE2), `not_matches`, `domain_in`, `not_domain_in` (for email addresses / URLs), `gt`, `gte`, `lt`, `lte`, `len_gt` (arrays/strings), `exists`, `not_exists`. `path` is a JSONPath subset (`$.a.b`, `$.a[*]`, `$.a[0]`); with `[*]` the predicate is true if **any** element matches (for `not_*` ops: if any element fails the positive test).

Combination: see [spec 09](../03-specs/09-policy-approvals.md) §4 (deny > require_approval > allow > default by risk class).

## 8. Skill (`kind: Skill`)

```yaml
kind: Skill
metadata: { slug: mttr-report, name: MTTR report }
spec:
  description: How to compute MTTR from incident tickets and render the standard chart. Use when asked for MTTR or incident duration statistics.
  visibility: tenant
  required_tools: [jira.search_issues, sandbox.exec]
  instructions_md: |
    1. Query incidents with jira.search_issues (JQL: priority in (P1,P2) AND resolved >= -7d).
    2. Copy /workspace/.skills/mttr-report/mttr.py and run it with the JSON results.
    3. Present a table and the chart; cite ticket keys.
  assets:
    - { path: mttr.py, file: mttr.py }   # uploaded file names
```

## 9. ModelAlias, SandboxTemplate, ChannelIntegration

```yaml
kind: ModelAlias
metadata: { alias: reasoning }
spec: { kind: chat, primary_model: qwen-moe-fp8, fallback_models: [gpt-oss-120b], traffic_split: {}, default_params: { temperature: 0.3 } }
---
kind: SandboxTemplate
metadata: { slug: data-science }
spec: { image_ref: "registry.internal/ar-sandbox@sha256:...", runtime_class: gvisor, cpu_millis: 4000, memory_mb: 8192, disk_gb: 20, allow_browser: false, egress_allowlist: [pypi.mirror.internal], max_classification: confidential, idle_suspend_s: 900, max_lifetime_s: 86400, exec_timeout_s: 300, retention_days: 7 }
---
kind: ChannelIntegration
metadata: { name: corp-slack }
spec: { kind: slack, secret: slack-bot, default_agent: incident-analyst, config: { team_id: T0123, app_id: A0456, socket_mode: true }, agent_routing: [ { match: { channel_id: C0789 }, agent: finance-analyst } ] }
```

## 10. Versioning of the schema itself

`apiVersion: agentic-runtime.dev/v1`. Additive optional fields are allowed in v1. A breaking change introduces `v2` with an automatic converter in `ar_contracts.definitions.migrate` applied on read for older stored definitions.
