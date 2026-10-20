# PRD 01 — Agent builder

Builders create declarative agents (instructions, model alias, tools, knowledge, memory, skills, subagents, sandbox, policies, channels) without code, version them, test them and publish them. Spec: [spec 05](../03-specs/05-agent-registry.md), [definition-schema §2](../05-contracts/definition-schema.md#2-agentdefinition-kind-agent), UI [spec 19 §5](../03-specs/19-web-app.md#5-agentbuilder). Plan: [M3](../09-plan/M03-agent-builder.md).

### US-AGT-01 · Create an agent from a template (P0)
As a **builder**, I want to start from a template so that I get a working agent quickly.
- Given I hold `agents:create`, when I choose a template (`blank`, `assistant`, `researcher`, `analyst`, `support`) and enter slug and name, then a draft agent (version `draft`) is created with the template's definition and I land in the builder.
- Slug is unique per tenant (`^[a-z0-9][a-z0-9-]{1,62}$`); a duplicate returns 409 `conflict` and the form shows the field error.
- Visibility defaults to `private`; owner is me.
- Spec: spec 05 §3 `POST /api/v1/agents`. Plan: M2-T05, M3-T01, M3-T07.

### US-AGT-02 · Edit an agent in form or YAML (P0)
As a **builder**, I want to edit the definition in a guided form or as YAML so that both novices and experts are productive.
- The form tabs and the YAML editor edit the same draft; switching tabs never loses changes; YAML is validated live against `GET /api/v1/schemas/Agent`.
- Saving (`PUT /api/v1/agents/{agent_id}/versions/draft` with `If-Match`) returns field-level errors (`errors[].loc`) mapped onto form fields; a concurrent edit returns 412 and offers reload/merge.
- Autosave debounced 1.5 s with a visible "Saved" state.
- Spec: spec 05 §3, definition-schema §2.1. Plan: M3-T01, M3-T02, M3-T07.

### US-AGT-03 · Validate references before publishing (P0)
As a **builder**, I want to see which tools, collections, skills or subagents are missing or not permitted so that publish never fails at runtime.
- `POST /api/v1/agents/{agent_id}:validate` returns all problems at once (errors and warnings with `loc`, e.g. `unknown_reference` for missing/invisible objects, `skill_missing_tools`, missing model capability `tools`/`vision`, unsatisfiable tool version range, subagent cycle); each links to its form field.
- I can only bind resources I am allowed to use (tool servers approved and visible to me, collections I can read).
- Spec: spec 05 §4. Plan: M3-T02.

### US-AGT-04 · Test a draft in a preview chat (P0)
As a **builder**, I want to chat with my unpublished draft so that I can iterate before publishing.
- A preview conversation runs the current draft (`conversations.is_preview=true`), shows tool calls, citations and the run inspector, and is not listed in normal conversation history (`include_previews=false` by default).
- Policies and approvals apply exactly as for published agents (W2/W3 calls still need approval).
- Spec: [spec 06](../03-specs/06-conversations-runs.md). Plan: M3-T04.

### US-AGT-05 · Publish and roll back versions (P0)
As a **builder**, I want immutable published versions with rollback so that changes are safe.
- Publish creates version `n+1` with resolved bindings (`agent_version_bindings`); existing conversations keep their version until the user starts a new conversation or accepts "Use latest".
- Publishing a `risk_tier='high'` agent or one bound to a `W3` tool requires a second person with `agents:manage_all`.
- Rollback re-activates a previous version as a new version number (history is linear); both write audit (`agent.published`, `agent.rolled_back`).
- If a publish gate suite is configured it must pass first ([US-EVAL-04](14-evaluation.md#us-eval-04--gate-publishing-on-evaluation-p1)).
- Spec: spec 05 §2–4. Plan: M3-T01, M13-T04.

### US-AGT-06 · Control visibility and ownership (P0)
As a **builder**, I want to share an agent with my team or the whole tenant.
- Visibility `private` | `team` | `tenant`; non-visible agents return 404; the catalogue (`usable=true`) shows only published, enabled, visible agents.
- Transferring ownership to another user or team requires `agents:manage_all` or being owner.
- Spec: spec 05 §2. Plan: M3-T01, M3-T08.

### US-AGT-07 · Kill switch (P0)
As a **tenant admin**, I want to disable an agent immediately so that a misbehaving agent stops acting.
- `POST /api/v1/agents/{agent_id}:disable` (permission `agents:disable`) blocks new runs (`resource_disabled`) and cancels active runs; enabling restores it; both audited.
- Spec: spec 05 §3. Plan: M3-T01.

### US-AGT-08 · One-shot draft API (P1)
As a **builder**, I want a single call that turns a description into a definition.
- `POST /api/v1/agents:draft-from-description` returns a definition that passes schema validation and references only resources visible to me; nothing is saved until I accept.
- The screen people use is US-AGT-11. This endpoint is what the builder agent calls.
- Spec: spec 05 §3. Plan: M3-T06.

### US-AGT-09 · Import and export bundles (P1)
As a **builder**, I want to move agents (with skills, policies, routines) between environments as files.
- Export produces `ar.yaml` (or zip with assets) with references by slug and never secrets.
- Import supports `dry_run` with a per-object diff (`create`, `update`, `unchanged`, `conflict`); applying is atomic.
- Spec: [definition-schema §1](../05-contracts/definition-schema.md#1-bundle-format), spec 05 §3. Plan: M3-T05.

### US-AGT-10 · Browse the agent catalogue (P0)
As a **member**, I want to find agents relevant to me and start chatting.
- Catalogue with search, filters (team, channel, recently used), agent detail (description, starter prompts, owner, version) and a "Chat" action that opens a new conversation.
- Spec: [spec 19 §3](../03-specs/19-web-app.md#3-pages). Plan: M3-T08.

### US-AGT-11 · Describe the agent you want (P0)
As a **builder**, I want to type what the agent should do and get a full draft I can correct.
- The first control is a natural-language field. The built-in `builder` agent returns a preview of persona, tools, knowledge, policies and routines.
- I can refine in the conversation or open the same draft in the form or YAML editor. Nothing is published until I publish.
- Spec: [spec 05 §11](../03-specs/05-agent-registry.md#11-natural-language-builder). Plan: M3-T10.
