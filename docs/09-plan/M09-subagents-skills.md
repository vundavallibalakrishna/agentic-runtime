# M9 — Subagents & skills

Goal: composition. Agents delegate subtasks to other agents (or clones of themselves) as child workflows with their own budgets and approvals; builders package reusable instructions and assets as versioned skills loaded on demand.

Exit criteria: a "research lead" agent delegates two parallel research tasks to a "researcher" subagent and merges the results; the run trace shows the tree; a "brand-guidelines" skill with a template asset is loaded and used to produce a DOCX in the sandbox.

---

### M9-T01 · Subagent delegation
- **Depends on:** M5-T05
- **Areas:** `ar_runtime/control/delegate.py`, `ar_runtime/activities/create_child_run.py`, `ar_runtime/workflows/agent_run.py`, `ar_api/routers/runs.py`
- **Spec:** [spec 07 §7](../03-specs/07-agent-runtime.md#7-subagents-agentsdelegate), [request-flows §7](../02-architecture/request-flows.md#7-subagent-delegation)
- **Do:** `agents__delegate` control tool (allowed subagents from definition, self-clone option), `create_child_run` (depth ≤ `AR_MAX_DEPTH`, budget = min(child, remaining parent)), child `AgentRunWorkflow` with parent close policy `REQUEST_CANCEL`, parallel delegations, child approvals surfaced on the parent conversation stream, `subagent.started/completed` events, usage roll-up to parent; enable `GET /api/v1/runs/{run_id}/children`; resolver `subagent` (cycle detection across published versions).
- **Done when:** cancelling the parent cancels children; depth limit enforced; cycles rejected at publish.
- **Tests:** Temporal tests (parallel children, cancel propagation, budget exhaustion, child approval wait); resolver cycle test.

### M9-T02 · Revision 0016 `skills` and skills API
- **Depends on:** M3-T02, M2-T07
- **Areas:** `ar_domain/skills/**`, migration 0016, `ar_api/routers/skills.py`
- **Spec:** [spec 14 §1–3, §5](../03-specs/14-skills.md#3-public-api), [schema §12](../04-data/schema.md#12-skills-ar_domainskills)
- **Do:** Tables of schema §12 with `skill_versions_immutable` (version ≥ 1; version 0 is the mutable draft); `GET/POST /api/v1/skills`, `GET/PATCH /api/v1/skills/{skill_id}` (edits draft v0 incl. assets as `files(kind='skill_asset')`), `POST /api/v1/skills/{skill_id}:publish`, `:archive`, `GET /api/v1/skills/{skill_id}/versions`, `GET /api/v1/skills/{skill_id}/versions/{version}`, `GET /api/v1/skills/{skill_id}/where-used`, `POST /api/v1/skills/{skill_id}:republish-dependants`; resolver `skill` with version constraints (`^1`); bundles include skills.
- **Done when:** published versions are immutable; agents pin by constraint and resolve at publish.
- **Tests:** integration per endpoint; trigger tests; constraint resolution unit tests.

### M9-T03 · Skills at runtime
- **Depends on:** M9-T02, M6-T06
- **Areas:** `ar_mcp_gateway/builtins/skills.py`, `ar_runtime/context/sections.py`
- **Spec:** [spec 14 §4](../03-specs/14-skills.md#4-runtime-behaviour)
- **Do:** Capabilities index block; `skills.load` returning instructions + asset manifest, writing assets to `/workspace/.skills/<slug>/` (ensuring a sandbox when needed); `conversations.loaded_skills` so reloaded skills persist across turns; skills treated as trusted content.
- **Done when:** the brand-guidelines exit scenario passes with fake-llm scripts.
- **Tests:** integration (docker sandbox); prompt snapshot with loaded skill.

### M9-T04 · Web: skills editor and run trace graph
- **Depends on:** M9-T01, M9-T03
- **Areas:** `apps/web/src/app/(app)/skills/**`, `apps/web/src/components/runs/RunTraceGraph/**`
- **Spec:** [spec 19](../03-specs/19-web-app.md)
- **Do:** Skills list/editor (Markdown with preview, assets upload, publish with change note, versions, where-used, republish dependants), run trace graph (xyflow) showing parent/children, steps and tool calls, linked from chat and run inspector.
- **Done when:** M9 exit scenario visible in the UI.
- **Tests:** Vitest; Playwright create/publish skill and view trace; axe.
