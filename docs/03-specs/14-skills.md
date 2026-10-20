# Spec 14: Skills (`ar_domain.skills`)

Endpoints served by `api`; loading at run time by the `skills.load` built-in tool in `mcp-gateway`. Owns `skills`, `skill_versions` ([schema §12](../04-data/schema.md#12-skills-ar_domainskills)). Definition: [definition-schema §8](../05-contracts/definition-schema.md#8-skill-kind-skill). PRD: [09-skills](../01-prd/09-skills.md).

## 1. Concept

A **skill** is a reusable, versioned procedure: a short `description` (always visible to the model in the capabilities index so it can decide when to load it), Markdown `instructions_md` (loaded on demand, progressive disclosure), optional `assets` (scripts, templates, reference files) and `required_tools`. Skills keep agent instructions short and let many agents share expertise. Skills never grant tools: a skill can only be bound to an agent that already has all `required_tools`.

## 2. Lifecycle

`draft` → publish (new immutable `skill_versions` row, `published_version_id`) → `archived`. Editing a published skill creates a new version on the next publish; agents bound to the skill always use the skill's **published version at agent publish time** (recorded in `definition.resolved.skills`), so skill updates require re-publishing dependent agents; the UI lists dependants with an "update available" badge and a bulk "re-publish dependants" action (each agent is validated; failures reported).

## 3. Public API

Permissions: `skills:read`, `skills:create` (own skills), `skills:manage_all`.

#### GET /api/v1/skills
Query `q`, `status`, `owner=me`, `team_id`. Item `Skill {id, slug, name, description, visibility, status, owner, owner_team, published_version: int|null, required_tools, updated_at, used_by_count}`.

#### POST /api/v1/skills
`skills:create`. Body `{slug, name, description (≤ 500), visibility?, owner_team_id?, instructions_md, required_tools?: [qualified_name], assets?: [{path, file_id}]}`. Creates the skill (`draft`) with draft content stored in the skill row's working copy (`skill_versions` row with `version = 0` reserved as the mutable draft; versions ≥ 1 are immutable via trigger `skill_versions_immutable`).

#### GET /api/v1/skills/{skill_id}
Includes draft (if editor) and published version content.

#### PATCH /api/v1/skills/{skill_id}
Editors. Metadata and draft content `{name?, description?, visibility?, owner_team_id?, instructions_md?, required_tools?, assets?}`. Asset rules: ≤ 50 assets, each ≤ 10 MiB, total ≤ 50 MiB, `path` relative (`^[A-Za-z0-9._/-]{1,200}$`, no `..`), file `kind` converted to `skill_asset`.

#### POST /api/v1/skills/{skill_id}:publish
Editors. Body `{change_note?}`. Validates: `required_tools` exist (approved); instructions non-empty; computes `hash = sha256(JCS({instructions_md, assets[].sha256, required_tools}))`; creates version `max+1`. Emits `skill.published`. Audit.

#### POST /api/v1/skills/{skill_id}:archive
409 if bound to a published agent version (list returned).

#### GET /api/v1/skills/{skill_id}/versions
#### GET /api/v1/skills/{skill_id}/versions/{version}

#### GET /api/v1/skills/{skill_id}/where-used
Agents (published/draft) referencing the skill and whether they use the latest version.

#### POST /api/v1/skills/{skill_id}:republish-dependants
Requires publish rights on each agent; runs `agents :publish` with change note `Update skill <slug> to v<n>` for each dependant; returns per-agent results.

## 4. Runtime behaviour

- Capabilities index block (spec 07 §4 block 3) lists each bound skill as `- <slug>: <description>`.
- `skills.load {skill}` (R0): returns `instructions_md` of the resolved version (≤ 50,000 chars) plus an asset manifest. If the run has a sandbox (or the skill has assets and the agent has sandbox enabled, in which case `ensure` is called), assets are written to `/workspace/.skills/<slug>/` (via sandbox-agent `PUT /files/content`), idempotent by sha256. The loaded instructions are appended to the system prompt (block 4) for the rest of the conversation: the skill reference `{skill_id, version}` is added to `conversations.loaded_skills` (child runs keep their own list in the run context) and the runtime re-reads the immutable version content when assembling each prompt.
- Skills are treated as **trusted** content (authored by tenant users through review), unlike tool output.

## 5. Limits

Skills per tenant: 500; per agent: 30; instruction size 50,000 chars.

## 6. Metrics

`ar_skill_loads_total{skill}`, `ar_skill_publish_total`.

## 7. Test plan

- Unit: asset path validation; hash stability; required tool coverage check.
- Integration: publish increments versions; version 0 mutable but ≥ 1 immutable (trigger); agent publish pins version; `skills.load` copies assets into the sandbox and appends instructions to the next prompt (snapshot test of prompt); archive blocked when bound.
