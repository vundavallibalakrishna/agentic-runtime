# Spec 05: Agent registry and definitions (`ar_domain.agents`)

Hosted in `api` (`ar_api.routers.agents`, `ar_api.routers.bundles`). Owns `agents`, `agent_versions`, `agent_version_bindings` ([schema §4](../04-data/schema.md#4-agents-ar_domainagents)). Definition format: [definition-schema.md §2](../05-contracts/definition-schema.md#2-agentdefinition-kind-agent). PRD: [01-agent-builder](../01-prd/01-agent-builder.md).

## 1. Responsibilities

1. CRUD of agents (metadata) and versioned, validated definitions (draft → published → superseded).
2. Reference validation and **resolution at publish** (tool version ranges → concrete `tool_versions`, skills → versions, collections → ids), writing `agent_version_bindings`.
3. Visibility and edit rights; kill switch; rollback; duplication.
4. Publish gate: optional evaluation suite must pass ([spec 18](18-observability-eval.md)).
5. Bundle import/export for all definition kinds (delegating to each module's service for non-agent kinds).
6. AI-assisted drafting of a definition from a natural-language description.
7. Provide `get_runtime_config(agent_version_id)` to the runtime: the frozen, resolved definition plus derived values.

## 2. Access rules

| Action | Who |
|---|---|
| See an agent in lists / chat with it | `agents:read` AND (visibility `tenant`; or `team` and caller is a member of `owner_team_id`; or `private` and caller is owner) AND (status `published` or caller can edit). Disabled agents are listed with `disabled: true` but cannot start runs. |
| Edit draft, validate | owner, leads/members-with-`builder` of the owner team (team-scoped `agents:edit`), or `agents:manage_all` |
| Publish / rollback | editors who also hold `agents:publish` (team- or tenant-scoped), or `agents:manage_all`. Agents with `risk_tier='high'` or any bound tool with risk class `W3` additionally require `agents:manage_all` (second person). |
| Disable / enable (kill switch) | `agents:disable` |
| Archive / delete | owner or `agents:manage_all` |

Non-visible agents return 404.

## 3. Public API

#### GET /api/v1/agents
Permission `agents:read`. Query: `q`, `status` (`draft|published|archived`), `visibility`, `owner=me`, `team_id`, `usable=true` (published, not disabled, visible: used by the chat picker), `channel` (`web|slack|...` filters by `definition.channels`), `sort` (`name`, `-updated_at`). Item `AgentSummary {id, slug, name, description, avatar_url, visibility, status, disabled, risk_tier, owner: {id, display_name}, owner_team: {id, name}|null, published_version: int|null, draft_version: int|null, updated_at, can_edit: bool}`.

#### POST /api/v1/agents
Permission `agents:create`. Body `{slug, name, description?, visibility?, owner_team_id?, risk_tier?, definition?: AgentDefinition, template?: "blank"|"assistant"|"researcher"|"analyst"|"support"}`. Creates the agent (`status='draft'`) and draft version 1 (definition from body or template; templates live in `ar_domain.agents.templates`). Response `Agent` (`AgentSummary` + `draft: AgentVersion`). Errors: 409 `conflict` (slug), 422.

#### GET /api/v1/agents/{agent_id}
Permission `agents:read` + visibility. Response `Agent` including `published: AgentVersion|null`, `draft: AgentVersion|null` (draft only if `can_edit`), `etag`.

#### PATCH /api/v1/agents/{agent_id}
Editors. Body `{name?, description?, visibility?, owner_team_id?, owner_user_id?, risk_tier?, avatar_file_id?}` with `If-Match`. Changing `visibility` to `tenant` requires `agents:publish`.

#### DELETE /api/v1/agents/{agent_id}
Owner or `agents:manage_all`. Allowed only if the agent was never published and has no conversations; otherwise 409 `invalid_state` (use `:archive`).

#### POST /api/v1/agents/{agent_id}:archive
Sets `status='archived'`; existing conversations become read-only; routines using it are paused (`paused_reason='agent_archived'`).

#### POST /api/v1/agents/{agent_id}:unarchive
Back to `published` (if it has a published version) or `draft`.

#### GET /api/v1/agents/{agent_id}/versions
Editors. Items `AgentVersionSummary {id, version, state, definition_hash, change_note, created_by, created_at, published_at, published_by}`.

#### GET /api/v1/agents/{agent_id}/versions/{version_ref}
`version_ref` = integer, `draft`, or `published`. Response `AgentVersion {id, version, state, definition, change_note, ..., etag}`. Non-editors may read only `published` and only `definition` fields `persona`, `starter_prompts`, `channels` (others redacted).

#### PUT /api/v1/agents/{agent_id}/versions/draft
Editors. Body `{definition: AgentDefinition, change_note?}`, header `If-Match` (draft etag) required. If no draft exists (latest is published), creates version `max+1` from the body. Validates **structurally** (Pydantic) and returns warnings for unresolved references without failing (drafts may be incomplete). Response `AgentVersion`.

#### POST /api/v1/agents/{agent_id}:validate
Editors. Body `{version_ref?: "draft"}`. Full validation as at publish (§4) without persisting. Response `{valid: bool, errors: [{loc, msg, type}], warnings: [...], resolved: ResolvedBlock}`.

#### POST /api/v1/agents/{agent_id}:publish
Publishers. Body `{change_note, skip_eval_gate?: false}` with `If-Match` on the draft. Steps in one transaction: full validation → resolution → write `definition.resolved` + bindings → draft `state='published'`, previous published `state='superseded'` → `agents.published_version_id`, `status='published'`, `draft_version_id=NULL` → emit `agent.published` → audit `agent.published` (with definition hash). If the agent has an eval suite with `gate.required=true` and `skip_eval_gate` is false: response `202 {eval_run_id}` and publication completes automatically when the `EvalRunWorkflow` passes (`agent_versions.state` stays `draft` meanwhile; failure → notification + no publish). `skip_eval_gate` requires `agents:manage_all`.

#### POST /api/v1/agents/{agent_id}:rollback
Publishers. Body `{version: int, change_note}`. Creates a new version `max+1` with the old definition (re-resolved against current tool registry; fails with 422 if references are no longer valid) and publishes it.

#### POST /api/v1/agents/{agent_id}:duplicate
`agents:create`. Body `{slug, name}`. Copies the latest (published, else draft) definition into a new agent draft owned by the caller.

#### POST /api/v1/agents/{agent_id}:disable
Permission `agents:disable`. Body `{reason}`. Sets `disabled_at`; publishes invalidation; running runs of this agent are cancelled at their next step boundary (runtime checks kill switch before each model call and tool call); new runs → 423 `resource_disabled`. Audit `agent.disabled`.

#### POST /api/v1/agents/{agent_id}:enable
Permission `agents:disable`.

#### GET /api/v1/agents/{agent_id}/where-used
Editors. `{routines: [...], channel_integrations: [...], parent_agents: [...]}` (from routines.agent_id, channel default/routing, and `agent_version_bindings` kind `subagent`).

#### POST /api/v1/agents:draft-from-description
`agents:create`. Body `{description (≤ 4,000 chars), available_only: true}`. Calls the `fast` alias (purpose `builder_assist`) with the JSON Schema of `AgentDefinition`, the list of visible tool servers/collections/skills (names + descriptions) and guided JSON output; returns `{definition: AgentDefinition, rationale: string}`. Never persists. Output is validated; invalid suggestions are repaired once, then returned with `warnings`.

#### POST /api/v1/bundles:import
Permission: depends on contained kinds (each resource checks its module's create/edit permission). Body `{bundle: object | yaml_text: string, dry_run: bool, prune: false, publish: false}`. Response `{results: [{kind, key, action: "create"|"new_version"|"unchanged"|"error", id?, errors?}]}`. Executes in dependency order: `ModelAlias`, `SandboxTemplate`, `DataConnection`, `ToolServer`, `KnowledgeCollection`, `Skill`, `Policy`, `Agent`, `ChannelIntegration`, `Routine`. Not atomic across resources (each resource commits separately; a failed resource does not roll back earlier ones) but idempotent, so re-running converges. `publish: true` publishes agents/skills after import (subject to permissions and gates).

#### GET /api/v1/bundles:export
Query `kinds` (comma list), `ids` (optional). Returns `application/yaml` (default) or JSON (`Accept: application/json`).

## 4. Validation and resolution at publish (`agents.service.resolve`)

For the definition being published:
1. Pydantic validation (field rules in [definition-schema §2.1](../05-contracts/definition-schema.md#21-field-rules-validated-on-save-errors-use-validation_failed--unknown_reference)).
2. Model aliases exist, active, kind `chat`, and the primary model has capability `tools` if any tools are bound; `vision_alias` model has `vision`.
3. For each `tools[]`: server visible, `status='approved'`, not disabled; pick the highest approved `tool_server_versions.version` satisfying the range; each included tool exists in that version and is not disabled; record `tool_version_id` and `risk_class`. `["*"]` expands to all tools of that version at publish time (later-added tools need a re-publish).
4. Each skill: published; its `required_tools` ⊆ the agent's resolved tools (else error `skill_missing_tools`).
5. Each knowledge collection visible to the publisher.
6. Subagents: published, visible; detect cycles via DFS over published definitions up to `max_depth`.
7. Sandbox template exists and is active if `sandbox.enabled` or any `sandbox`/`browser` tool is included (and vice versa: including `sandbox.*` tools requires `sandbox.enabled`).
8. Budget values ≤ tenant caps; `extra_egress_allowlist` ⊆ tenant allowlist.
9. Compute `definition_hash = sha256(JCS(definition_without_resolved))`.

## 5. Runtime config (`agents.service.get_runtime_config`)

Returns `AgentRuntimeConfig` (frozen Pydantic, cached in Valkey `ar:agentcfg:{agent_version_id}` indefinitely since versions are immutable; drafts cached 5 s): resolved definition + `agent_id`, `tenant_id`, `risk_tier`, `disabled` (checked live, not cached), owner ids, and the computed `system_prompt_static` (see [spec 07 §4](07-agent-runtime.md#4-context-assembly)).

## 6. Events and audit

Events: `agent.published`, `agent.disabled`, `agent.enabled`. Audit actions: `agent.created`, `agent.updated`, `agent.draft_saved` (hash only), `agent.published`, `agent.rolled_back`, `agent.archived`, `agent.deleted`, `agent.disabled`, `agent.enabled`, `bundle.imported`.

## 7. Limits

Agents per tenant: plan `max_agents` (default 200). Versions per agent: unlimited (old superseded versions retained; referenced by runs). Definition size ≤ 256 KiB JSON.

## 8. Metrics

`ar_agents{tenant,status}` (gauge, from rollup), `ar_agent_publish_total{result}`, `ar_bundle_import_resources_total{kind,action}`.

## 9. Test plan

- Unit: resolver (semver range selection, `*` expansion, cycle detection, skill tool coverage), visibility predicate truth table, definition hash stability (property test: key order permutations produce same hash).
- Integration: draft save with/without If-Match; publish supersedes previous; published version immutable (trigger raises on direct UPDATE); disable → new run 423; rollback re-resolves; bundle import idempotency (import twice → second run all `unchanged`); export → import round-trip equality.
- E2E: builder creates agent from template, adds tool, publishes, chats in preview and in main chat.
