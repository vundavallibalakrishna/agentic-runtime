# Declarative definition schema (agents, tools, knowledge, routines, policies, skills)

Companies define their capabilities either in the web UI or as YAML/JSON **bundles** checked into Git and imported via the API/CLI. Both paths validate against the same Pydantic models in `ar_contracts.definitions` ([ADR-0018](../02-architecture/adr/ADR-0018-declarative-definitions.md)). JSON Schema files are exported by `make gen` to `libs/ar_contracts/schemas/*.schema.json` and served at `GET /api/v1/schemas/{kind}`.

Public definition files use camelCase keys ([ADR-0026](../02-architecture/adr/ADR-0026-public-json-camel-case.md)). The models accept snake_case on input so a file written the old way still imports. Examples below use the public form. Python attributes remain snake_case (`owner_team` is the attribute; `ownerTeam` is the file key).

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

Each resource can also be a standalone document (`kind: Agent`, `kind: Routine`, ...). Import (`POST /api/v1/bundles:import`, [spec 05](../03-specs/05-agent-registry.md)) is idempotent by `(kind, slug)` (routines and policies by `name`): it creates or creates-a-new-version, never deletes unless `prune: true`. `dryRun: true` returns the plan (create / new_version / unchanged / error per resource). Export (`GET /api/v1/bundles:export?kinds=Agent,Routine`) produces the same format with ids stripped and references expressed by slug/name.

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
  ownerTeam: sre               # team slug (optional)
  riskTier: medium             # low | medium | high
spec:
  persona:
    displayName: Incident Analyst
    greeting: "Hi! Ask me about incidents, MTTR or on-call load."
    avatarFile: null           # file id (uploaded via files API)
  instructions: |
    You help SRE teams analyse incidents. Always cite ticket keys.
    Use the sandbox for any calculation over more than 10 rows.
  starterPrompts:
    - "Summarise last week's P1 incidents with an MTTR chart"
  model:
    alias: reasoning            # chat model alias for planning/tool use
    fastAlias: fast            # used for titles, compaction, memory extraction, routing
    visionAlias: vision        # optional; used when images are present
    params: { temperature: 0.2, topP: 0.95, maxOutputTokens: 4096, reasoningEffort: medium }
    degradeToFast: true       # after 2 failed model steps on alias, retry the step on fastAlias
  tools:
    - server: jira              # tool server slug (tenant or built-in)
      version: "^1"             # semver range on server version; resolved at publish
      include: [search_issues, get_issue, create_issue]   # or ["*"]
      overrides:
        create_issue: { requireApproval: always }        # tighten only: always | policy (default)
        search_issues: { pinned: true }                   # always loaded when tool search is active
    - server: sandbox           # built-in
      include: ["*"]
    - server: knowledge         # built-in
      include: [search, get_document, list_collections]
  toolSearch: { mode: auto, topK: 12 }   # auto: enabled when > 30 tools are granted; on | off
  knowledge:
    collections: [sre-runbooks, postmortems]
    autoRetrieve: false        # true = run knowledge.search on the user message before the first model call
    topK: 8
    minScore: 0.30             # answerability threshold after rerank (0..1)
  skills: [mttr-report]
  memory:
    enabled: true
    readScopes: [user, agent, team, agent_user]
    userWrites: auto           # auto (extraction + explicit) | explicit_only | off
    agentWrites: review        # review (proposals go to pending_review) | off
    recallTopK: 8
  subagents:
    allowed: [web-researcher]   # agent slugs this agent may delegate to
    allowSelfClone: true      # delegate to a copy of itself with a narrowed tool subset
    maxDepth: 2                # 1..3; platform max 3
    maxParallel: 3
  sandbox:
    enabled: true
    template: default           # sandbox template slug
    scope: conversation         # conversation | agent_user | agent
    extraEgressAllowlist: []  # must be a subset of the tenant allowlist
  budget:                       # RunBudget (per top-level run, subagents draw from it)
    maxSteps: 30
    maxTokens: 600000
    maxCostMicros: 50000000
    maxWallClockS: 1200
    maxToolCalls: 60
    maxParallelToolCalls: 4
  context:
    compactionThreshold: 0.7   # fraction of the model context window
    toolResultMaxTokens: 4000
    historyMaxMessages: 40
  output:
    citations: preferred        # required | preferred | off
    showReasoning: false
  safety:
    piiMasking: false          # mask PII in prompts sent to the model (Presidio)
    injectionClassifier: true  # flag suspicious tool output (fast model)
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
| `tools[].overrides.<tool>.timeoutS` | int | 1..120. Per-tool time limit for general code, shell, fetch and HTTP |
| `tools[].overrides.<tool>.maxOutputBytes` | int | 256..65536 |
| `tools[].overrides.<tool>.maxFileBytes` | int | 1024..5242880 |
| `tools[].overrides.<tool>.network` | bool | Sandbox network. Off unless set. On still requires the egress allow list |
| `tools[].overrides.<tool>.allowHosts` | string[] | Extra hosts for `general.fetch` and `general.http` |
| `tool_search.mode` | enum | `auto`, `on`, `off`; `top_k` 4..32 |
| `knowledge.collections` | slug[] | ≤ 20; caller must be able to see each at save time |
| `knowledge.min_score` | number | 0..1 |
| `skills` | slug[] | ≤ 30; published skills. A `slug@^1` constraint resolves at publish ([spec 14](../03-specs/14-skills.md)) |
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
    - { qualifiedName: jira.create_issue, toolId: "...", toolVersionId: "...", riskClass: W2 }
  model: { alias: reasoning }
  skills: [ { slug: mttr-report, skillVersionId: "..." } ]
  knowledge: [ { slug: sre-runbooks, collectionId: "..." } ]
```

A published version therefore always runs exactly the tool versions that were reviewed at publish time. Upgrading a tool server minor version requires re-publishing the agent (UI shows "updates available").

## 3. ToolServerDefinition (`kind: ToolServer`)

```yaml
kind: ToolServer
metadata: { slug: jira, name: Jira, ownerTeam: platform }
spec:
  kind: remoteMcp              # remoteMcp | openapi | sql
  version: 1.3.0
  description: Jira Data Center tools.
  remoteMcp:
    url: https://mcp-jira.tools.svc.cluster.local/mcp
    headers: { X-Env: prod }
  auth:
    mode: user_oauth            # none | static_secret | user_oauth | token_exchange | internal_jwt
    credentialProvider: jira-oauth   # for user_oauth / token_exchange
    secret: null                # for static_secret: secret name
  tools:                        # optional per-tool governance overrides (discovered tools are the source of schemas)
    create_issue: { riskClass: W2, dataClassification: internal, timeoutS: 30, rateLimitPerMinute: 20 }
    search_issues: { riskClass: R0 }
  allowedTools: ["*"]          # subset of discovered tools exposed to agents
```

`openapi` kind:

```yaml
spec:
  kind: openapi
  version: 1.0.0
  openapi:
    specFile: hr-api-openapi.yaml    # uploaded file name (files.kind='openapi_spec')
    baseUrl: https://hr.internal.example/api
    operations: [getEmployee, listLeaveBalances]   # operationIds to expose
  auth: { mode: token_exchange, credentialProvider: hr-api }
```

`sql` kind:

```yaml
spec:
  kind: sql
  version: 1.0.0
  sql:
    dataConnection: finance-replica   # DataConnection name
  auth: { mode: none }                 # credentials come from the data connection
```

Risk class defaults when not overridden: derived from MCP annotations: `readOnlyHint=true` → `R0`; `destructiveHint=true` → `W3`; otherwise `W2`. Reviewers must confirm every tool's risk class before approval.

## 4. DataConnection (`kind: DataConnection`)

```yaml
kind: DataConnection
metadata: { name: finance-replica }
spec:
  engine: postgres
  dsnSecret: finance-replica-dsn   # secret containing postgresql://user:pass@host:5432/db
  identityMode: service            # service | per_user_mapped | passthrough
  allowlist:
    schemas: [reporting]
    tables: [reporting.invoices, reporting.customers]
    columnsDeny: [reporting.customers.pan_number]
  rowLimit: 1000
  statementTimeoutS: 30
  classification: confidential
  schemaNotes: |
    Fiscal year starts 1 April. amounts are in INR paise.
```

## 5. KnowledgeCollection (`kind: KnowledgeCollection`)

```yaml
kind: KnowledgeCollection
metadata: { slug: sre-runbooks, name: SRE runbooks }
spec:
  description: Runbooks and postmortems for production services.
  visibility: tenant
  aclMode: source              # source | collection
  sensitivity: normal           # normal | high
  classification: internal
  embeddingAlias: embed
  textSearchConfig: simple    # simple | english (lexical signal of hybrid retrieval)
  chunking: { targetTokens: 512, overlapPct: 12, contextual: false }
  sources:
    - name: confluence-sre
      kind: confluence          # upload | web | s3 | sharepoint | confluence | google_drive | database | mcp_resource
      confluence: { baseUrl: https://wiki.example.com, spaceKeys: [SRE], includeAttachments: true }
      secret: confluence-bot
      syncSchedule: "0 * * * *"
      aclSyncSchedule: "*/10 * * * *"
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
| `confluence` | `baseUrl`, `spaceKeys[]`, `includeAttachments` + secret ; ACLs from space/page restrictions |
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
  agentVersion: null           # null = published
  runAs: owner                 # owner | serviceAccount
  serviceAccount: null
  instructions: |
    Summarise last week's P1/P2 incidents, compute MTTR, post to #sre-digest.
  trigger:
    type: schedule              # schedule | webhook | channel_event | email | file_arrival | db_change | manual
    schedule: { cron: "0 9 * * MON", timezone: Asia/Kolkata, jitterS: 120, catchupWindowS: 3600 }
  eventFilter: null            # JMESPath on the event envelope
  delivery:
    - { type: slack, integration: corp-slack, channel: "#sre-digest", preApproved: true }
    - { type: email, to: [sre-leads@example.com], preApproved: false }
    - { type: conversation }    # always: run is recorded as a conversation of the owner
  budget: { maxSteps: 20, maxTokens: 300000, maxWallClockS: 900, maxToolCalls: 30, maxCostMicros: 20000000, maxParallelToolCalls: 4 }
  maxRunsPerDay: 4
  concurrencyPolicy: skip      # skip | buffer_one | allow
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
      effect: requireApproval           # allow | deny | requireApproval
      match:
        tools: ["mail.send_message", "mail.reply"]   # glob on qualified names
        riskClasses: []                 # any
        agents: []                       # agent slugs; empty = any
        triggers: []                     # chat | api | channel | routine | subagent | eval
        channels: []                     # web | slack | teams | email | api | routine | widget
        userGroups: []                  # group names
        userAttributes: { department: [finance] }
        dataClassifications: []
        args:
          - { path: "$.to[*]", op: not_domain_in, value: ["example.com"] }
        timeWindow: null                # { days: [MON..FRI], from: "09:00", to: "18:00", timezone: Asia/Kolkata }
      approval:
        approvers: { mode: group, groups: [finance-managers] }   # requester | agent_owner | group | users
        requiredApprovals: 1
        fourEyes: true                  # requester cannot approve
        stepUp: false
        ttlS: 86400
      message: "External emails need manager approval."
  tests:                               # run on every new version; activation requires all to pass
    - name: external recipient needs approval
      input: { tool: { qualifiedName: mail.send_message, riskClass: W2 }, user: { attributes: { department: finance } }, args: { to: ["x@other.org"] } }
      expect: { decision: requireApproval, ruleIds: [ext-email] }
    - name: internal recipient follows defaults
      input: { tool: { qualifiedName: mail.send_message, riskClass: W2 }, user: { attributes: { department: finance } }, args: { to: ["a@example.com"] } }
      expect: { decision: requireApproval }
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
  requiredTools: [jira.search_issues, sandbox.exec]
  instructionsMd: |
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
spec: { kind: chat, primaryModel: qwen-moe-fp8, fallbackModels: [gpt-oss-120b], trafficSplit: {}, defaultParams: { temperature: 0.3 } }
---
kind: SandboxTemplate
metadata: { slug: data-science }
spec: { imageRef: "registry.internal/ar-sandbox@sha256:...", runtimeClass: gvisor, cpuMillis: 4000, memoryMb: 8192, diskGb: 20, allowBrowser: false, egressAllowlist: [pypi.mirror.internal], maxClassification: confidential, idleSuspendS: 900, maxLifetimeS: 86400, execTimeoutS: 300, retentionDays: 7 }
---
kind: ChannelIntegration
metadata: { name: corp-slack }
spec: { kind: slack, secret: slack-bot, defaultAgent: incident-analyst, config: { teamId: T0123, appId: A0456, socketMode: true }, agentRouting: [ { match: { channelId: C0789 }, agent: finance-analyst } ] }
```

## 10. Versioning of the schema itself

`apiVersion: agentic-runtime.dev/v1`. Additive optional fields are allowed in v1. A breaking change introduces `v2` with an automatic converter in `ar_contracts.definitions.migrate` applied on read for older stored definitions.

## 11. Content packs and assurance fields

Additive in `apiVersion: agentic-runtime.dev/v1`. Existing documents stay valid.

### 11.1 Agent fields

```yaml
spec:
  output:
    citations: preferred
    grounding: off            # off | preferred | strict
  assurance:
    recordMode: off           # off | on
```

| Field | Type | Constraints |
|---|---|---|
| `output.grounding` | enum | `off` (default), `preferred`, `strict`. Behaviour: [spec 07 §13](../03-specs/07-agent-runtime.md#13-strict-grounding) |
| `assurance.recordMode` | enum | `off` (default), `on`. Behaviour: [spec 18 §7](../03-specs/18-observability-eval.md#7-run-records-and-re-performance). A solution-pack template that must be re-performed sets `on` |

### 11.2 Content pack (`kind: ContentPack`)

```yaml
apiVersion: agentic-runtime.dev/v1
kind: ContentPack
metadata:
  id: grc
  version: 1.0.0
  name: GRC solution pack
  minPlatform: 1.0.0
spec:
  resources: []               # same resource documents as a Bundle
  extension:                  # omitted for a pack that is only declarative resources
    schema: grc
    alembic: packs/grc/migrations
    apiMount: /api/v1/ext/grc
    webSlot: grc
    configSchema:
      type: object
      properties: {}
    ui:
      nav:
        - { href: /grc, label: GRC, permission: grc.controls:read }
    permissions: [grc.controls:read]
    auditActions: [grc.control.updated]
    mcpServer: grc
```

The signature is not inside the manifest. It is a sibling value supplied to `:install` ([spec 05 §10](../03-specs/05-agent-registry.md#10-content-packs)). `spec.resources` follows [§1](#1-bundle-format). Kind `ContentPack` is not itself a member of `spec.resources`. `configSchema` and `ui` are the extension-framework fields ([extension-framework](extension-framework.md)).

## 12. Defaults

A new agent, routine, policy, or skill is valid with the defaults below. The UI Simple mode edits only the fields a person must understand. Advanced mode exposes the rest and the raw document.

| Field | Default |
|---|---|
| `visibility` | `private` |
| `riskTier` | `low` |
| `model.alias` | `reasoning` |
| `model.fastAlias` | `fast` |
| `model.params.temperature` | `0.2` |
| `model.degradeToFast` | `true` |
| `output.citations` | `preferred` |
| `output.grounding` | `off` |
| `assurance.recordMode` | `off` |
| `memory.enabled` | `false` |
| `sandbox.enabled` | `false` |
| `channels.web` | `true` |
| `budget` | the tenant cap in `tenants.settings.run_budget_caps` when set, otherwise spec 07's platform caps |

Omitting a field means the default. A pack template may set a stricter default in its own file; core does not.
