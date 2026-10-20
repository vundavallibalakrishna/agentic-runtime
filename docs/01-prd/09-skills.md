# PRD 09 — Skills

Skills are reusable, versioned procedures (instructions + optional assets) that agents load on demand, keeping the base prompt small. Spec: [spec 14](../03-specs/14-skills.md), [definition-schema §8](../05-contracts/definition-schema.md#8-skill-kind-skill). Plan: [M9](../09-plan/M09-subagents-skills.md).

### US-SKL-01 · Author a skill (P0)
As a **builder**, I want to write a skill (description, Markdown instructions, assets such as scripts and templates, required tools) so that several agents can reuse a proven procedure.
- `POST /api/v1/skills` creates a draft; the editor provides Markdown preview, asset upload and `required_tools` selection; size limits per spec 14 §5.
- Spec: spec 14 §1, §3. Plan: M9-T02, M9-T04.

### US-SKL-02 · Publish immutable versions (P0)
As a **builder**, I want published skill versions to be immutable so that agents behave predictably.
- `:publish` creates a new `skill_versions` row; agents keep the version resolved at their own publish time; `GET …/where-used` lists dependent agents; `:republish-dependants` lets editors republish those agents to pick up the new version (each republish follows agent publish rules).
- Spec: spec 14 §2–3. Plan: M9-T02.

### US-SKL-03 · Agents load skills only when needed (P0)
As a **builder**, I want the model to see a one-line description of each bound skill and load the full instructions only when relevant.
- The capabilities index lists `- <slug>: <description>`; `skills.load` returns the instructions and writes assets to `/workspace/.skills/<slug>/` when a sandbox is used; the run shows which skills were loaded.
- Spec: spec 14 §4, spec 07 §4. Plan: M9-T03.

### US-SKL-04 · Required tools are enforced (P0)
As a **builder**, I want publishing to fail if an agent binds a skill without the tools it needs.
- Agent publish fails with `skill_missing_tools` when a skill's `required_tools` are not a subset of the agent's resolved tools.
- Spec: [spec 05 §4](../03-specs/05-agent-registry.md#4-validation-and-resolution-at-publish-agentsserviceresolve). Plan: M3-T02, M9-T02.

### US-SKL-05 · Share skills across the tenant (P1)
As a **builder**, I want to discover skills made by others and archive obsolete ones.
- Skills list with search and owner; visibility per spec 14; `:archive` prevents new bindings while existing agent versions keep working.
- Spec: spec 14 §2–3. Plan: M9-T02, M9-T04.
