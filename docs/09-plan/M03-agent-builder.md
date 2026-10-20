# M3 — Agent builder & bundles

Goal: builders own the agent lifecycle — draft, validate, test, publish, roll back, duplicate, archive, disable — through a form + YAML builder, and move agents between environments as bundles.

Exit criteria: Playwright: builder creates agent from template, edits instructions, test-chats the draft, publishes v1, edits and publishes v2, rolls back to v1; exports a bundle and imports it into another tenant (dry-run diff shown first).

M3-T09 is required for 1.0. It is not part of the Playwright scenario above.

---

### M3-T01 · Agent registry: full lifecycle API
- **Depends on:** M2-T05
- **Areas:** `ar_api/routers/agents.py`, `ar_domain/agents/service.py`
- **Spec:** [spec 05 §2–3, §6–7](../03-specs/05-agent-registry.md#3-public-api)
- **Do:** `PATCH/DELETE /api/v1/agents/{agent_id}` (If-Match ETag), `POST /api/v1/agents/{agent_id}:archive`, `:unarchive`, `:validate`, `:rollback`, `:duplicate`, `:disable`, `:enable` (kill switch → `resource_disabled` on new runs, cancels active runs when `cancel_active=true`), `GET /api/v1/agents/{agent_id}/where-used`; full access rules (owner, team editors, `agents:publish`, `agents:manage_all`, second-person rule for high-risk); audit + domain events.
- **Done when:** the access-rule table in spec 05 §2 is enforced exactly.
- **Tests:** table-driven permission tests; ETag 412; disable blocks new runs (423) and cancels active ones.

### M3-T02 · Definition validation and reference resolution
- **Depends on:** M3-T01
- **Areas:** `ar_domain/agents/{validation.py,resolution.py}`, `ar_domain/references.py` (resolver registry)
- **Spec:** [spec 05 §4](../03-specs/05-agent-registry.md#4-validation-and-resolution-at-publish-agentsserviceresolve), [definition-schema](../05-contracts/definition-schema.md)
- **Do:** Two-phase validation: schema (Pydantic) then references through a resolver registry keyed by binding kind (`tool`, `tool_server`, `knowledge_collection`, `skill`, `subagent`, `sandbox_template`, `model_alias`). Modules register resolvers when they land (M4, M6, M7, M9); until then an unregistered kind yields `unknown_reference` with message "feature not available". Write `agent_version_bindings` on publish; compute `definition_hash`.
- **Done when:** errors carry `loc` paths per api-conventions §5; publish is blocked on any error; warnings (e.g. unused skill) do not block.
- **Tests:** unit tests per rule; hypothesis: random valid definitions round-trip JSON ↔ YAML.

### M3-T03 · Context assembly v2 and prompt templates
- **Depends on:** M3-T02, M2-T09
- **Areas:** `ar_runtime/context/{assembler.py,blocks.py,budget.py}`, `ar_runtime/prompts/{platform.md,citations.md}`, `libs/ar_common/src/ar_common/wrapping.py`
- **Spec:** [spec 07 §4](../03-specs/07-agent-runtime.md#4-context-assembly), [prompt-injection §3](../06-security/prompt-injection.md#3-untrusted-content-wrapping)
- **Do:** `ar_runtime.context.build_prompt(run) -> PromptBundle` with the fixed block order 1–11 of spec 07 §4 (blocks whose features land later — capabilities index entries, loaded skills, memory, plan, summary, auto-retrieved knowledge — render empty until their milestone), token budget per block using `/v1/tokenize` with tiktoken fallback, history truncation oldest-first, `ar_common.wrapping` (all three tag forms), prompt files versioned and their hash stored in `run_steps.detail.prompt_hash`.
- **Done when:** assembled prompts are snapshot-tested for three templates; budget overflow truncates history oldest-first, never blocks 1–5.
- **Tests:** inline-snapshot tests; budget unit tests; wrapping property test.

### M3-T04 · Test chat for drafts
- **Depends on:** M3-T03
- **Areas:** `ar_domain/conversations/service.py`, `ar_api/routers/conversations.py`
- **Spec:** [spec 05](../03-specs/05-agent-registry.md), [spec 06](../03-specs/06-conversations-runs.md)
- **Do:** `POST /api/v1/conversations` with `agent_version_id` of a draft (editors only, per spec 06) creates a preview conversation (`conversations.is_preview=true`). Preview conversations are excluded from `GET /api/v1/conversations` unless `include_previews=true`, visible only to the agent's editors, still metered but excluded from per-agent adoption metrics; the builder UI lists them per agent.
- **Done when:** non-editors cannot create or read preview conversations (404); preview runs are labelled `preview` in run lists.
- **Tests:** integration access tests; list exclusion.

### M3-T05 · Bundles import/export
- **Depends on:** M3-T02
- **Areas:** `ar_domain/bundles/{export.py,import_.py,diff.py}`, `ar_api/routers/bundles.py`
- **Spec:** [spec 05 §3](../03-specs/05-agent-registry.md#3-public-api), [definition-schema](../05-contracts/definition-schema.md), [ADR-0018](../02-architecture/adr/ADR-0018-declarative-definitions.md)
- **Do:** `GET /api/v1/bundles:export` (selected agents with their skills, policies and routines as `ar.yaml` or zip with assets; references by slug; never secrets) and `POST /api/v1/bundles:import` (`dry_run` diff: create/update/unchanged/conflict per object; apply creates drafts, never auto-publishes). Kinds whose modules are not yet built are reported as `skipped`.
- **Done when:** export → import into an empty tenant → re-export yields an identical bundle (modulo ids/timestamps).
- **Tests:** round-trip integration test; conflict detection; secrets never exported (grep test on output).

### M3-T06 · Draft agent from description
- **Depends on:** M3-T02
- **Areas:** `ar_domain/agents/assist.py`, `ar_api/routers/agents.py`, prompt `ar_domain/agents/prompts/draft_from_description.md`
- **Spec:** [spec 05 §3](../03-specs/05-agent-registry.md#3-public-api)
- **Do:** `POST /api/v1/agents:draft-from-description` calls `model-gateway` (purpose `builder_assist`, structured JSON output) with the description and the caller-visible catalogue (tools, collections, skills); returns a proposed `AgentDefinition` that passes schema validation (retry once with validation errors fed back).
- **Done when:** response always validates against `AgentDefinition` or returns 502 `upstream_error` after the retry.
- **Tests:** fake-llm scripted valid/invalid outputs.

### M3-T07 · Web: AgentBuilder
- **Depends on:** M3-T04, M3-T05, M3-T06
- **Areas:** `apps/web/src/app/(app)/agents/{new,[agentId]/edit}/**`, `apps/web/src/components/agent-builder/**`
- **Spec:** [spec 19 §5 AgentBuilder](../03-specs/19-web-app.md)
- **Do:** Template picker / describe-to-draft; builder tabs (instructions, model, tools, knowledge, memory, skills, subagents, sandbox, policies, channels, advanced) backed by one form state ↔ YAML (Monaco with JSON Schema from `/api/v1/schemas/Agent`); live validation panel; version history with diff; publish dialog with change note; rollback; test chat side panel bound to the draft; bundle import/export dialogs.
- **Done when:** M3 exit-criteria Playwright scenario passes; form and YAML stay in sync both ways.
- **Tests:** Vitest form↔YAML sync; Playwright scenario; axe.

### M3-T08 · Web: agent catalogue
- **Depends on:** M3-T07
- **Areas:** `apps/web/src/app/(app)/agents/{page.tsx,[agentId]/page.tsx}`
- **Spec:** [spec 19 `/agents`](../03-specs/19-web-app.md)
- **Do:** Catalogue grid/table with search and filters, agent detail (persona, starter prompts, owner, version, "Chat" button), favourites stored in user preferences.
- **Done when:** users only see agents visible to them; "Chat" starts a conversation with the published version.
- **Tests:** Vitest; Playwright browse-and-chat.

### M3-T09 · Content packs
- **Depends on:** M3-T05
- **Areas:** `ar_domain/agents/{packs.py,models.py}`, `ar_api/routers/content_packs.py`, `ar_contracts/definitions.py`, migration `0020_content_packs`
- **Spec:** [spec 05 §10](../03-specs/05-agent-registry.md#10-content-packs), [definition-schema §11](../05-contracts/definition-schema.md#11-content-packs-and-assurance-fields), [schema §20](../04-data/schema.md#20-content-packs-ar_domainagents), [ADR-0023](../02-architecture/adr/ADR-0023-pack-extensions.md)
- **Do:** Tables `installed_packs` and `installed_pack_resources`. Endpoints `GET /api/v1/content-packs`, `POST /api/v1/content-packs:install`, `GET /api/v1/content-packs/{pack_id}`, `POST /api/v1/content-packs/{pack_id}:upgrade`, `POST /api/v1/content-packs/{pack_id}:uninstall`. Verify the Ed25519 signature over the JCS SHA-256 of the manifest against `AR_PACK_TRUSTED_KEYS` when `AR_PACK_SIGNATURE_REQUIRED` is true. Import `spec.resources` through the bundle importer. A manifest with `extension.schema` is accepted and stored; schema migration is performed by the helper that [M14-T13](M14-security-compliance.md) adds. Until that helper exists, install of a manifest that sets `extension` returns 422 `extension_unavailable` after the signature check, and `:uninstall` with `dropSchema: true` returns the same code. Declarative packs (no `extension`) install, upgrade and uninstall in this task.
- **Done when:** a signed declarative pack round-trips; a bad signature audits `pack.signature_rejected` and returns 422 `pack_signature_invalid`; upgrade refuses a version that is not strictly greater; a tenant-edited resource is `conflict` until `accept_conflicts: true`.
- **Tests:** signature known-answer; unsigned pack rejected when the flag is true and accepted when `AR_ENV=dev`; upgrade conflict; cross-tenant 404.

### M3-T10 · Natural-language builder agent
- **Depends on:** M3-T06, M3-T07
- **Areas:** `ar_domain/agents/builder.py`, `ar_domain/seed/builder_agent.py`, `ar_api/routers/builder.py`, `apps/web/src/app/(app)/agents/new/**`
- **Spec:** [spec 05 §11](../03-specs/05-agent-registry.md#11-natural-language-builder), [spec 19 §5.1](../03-specs/19-web-app.md#51-natural-language-builder), [ux-quality](../08-quality/ux-quality.md)
- **Do:** Seed agent `builder`. Endpoints `POST /api/v1/builder/sessions`, `GET /api/v1/builder/sessions/{session_id}`, `POST /api/v1/builder/sessions/{session_id}/messages`, `POST /api/v1/builder/sessions/{session_id}:apply`. Tool `builder.propose_definition` stores a camelCase bundle fragment (agent, and any policies, routines, skills) without publishing. `/agents/new` leads with the instruction field and a preview; form and YAML are the escape hatch after apply. Templates sit below the field.
- **Done when:** the instruction "create an agent that reviews vendor SOC 2 reports and flags gaps" yields a preview containing a persona, at least one tool slot, and a validation panel; a follow-up message changes the proposal; apply creates a draft the form editor opens.
- **Tests:** fake-llm scripted proposal; apply does not publish; Playwright creates from the sentence and opens the form.
