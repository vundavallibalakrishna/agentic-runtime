# Product principles

These rules bind every milestone. [AGENTS.md](../../AGENTS.md) repeats the short form. A spec that disagrees with this file is wrong until the spec is updated.

North star: an enterprise AI assistant, a corporate assistant with its own computer, running entirely in the customer's environment and able to automate any work. See [vision](vision.md).

The goals, written this way and no other way: **CLEAN CODE**, **CUSTOMISABLE**, **EXTENSIBLE**, **SIMPLE UI/UX**, **OUTSTANDING PRESENTATION**.

## 1. API and UI casing

Public JSON uses camelCase. Python stays snake_case. Database columns and environment variables stay as they are.

Checkable:

- Every public request and response body, SSE `data` object, webhook JSON body, and definition file the UI shows uses camelCase property names (`createdAt`, `runId`, `dryRun`).
- No snake_case property name appears in the UI or in a generated TypeScript or Zod type.
- Python models subclass `ar_contracts.api_model.ApiModel` (`alias_generator=to_camel`, `populate_by_name=True`, `serialize_by_alias=True`). Attributes stay `created_at`. `model_validate` accepts either form. `model_dump()` and JSON Schema emit the alias.
- `scripts/check_public_camel_case.py` fails CI when a public schema property is not camelCase. The docs job runs it.
- Internal service JSON (`/internal/v1`) may stay snake_case. It is not a UI contract.
- Permission keys (`agents:publish`), audit actions (`agent.published`), error `code` values (`validation_failed`), stream `type` values (`tool_call.completed`), and enum string values already fixed in `ar_contracts` (`waiting_approval`, `max_steps`, `in_progress`) are identifier grammars. They are not property names. The UI shows a label, not the raw token, wherever a person would have to read an underscore.

Decision: [ADR-0026](../02-architecture/adr/ADR-0026-public-json-camel-case.md).

## 2. Outstanding UI and presentation

The product is demo-grade. A rough admin screen is a failed task.

Checkable:

- The primary way to create an agent is a natural-language instruction, for example "create an agent that reviews vendor SOC 2 reports and flags gaps". A built-in `builder` agent drafts the full definition (persona, tools, knowledge, policies, routines), shows a reviewable preview, and lets the user refine in the conversation or switch to the form or YAML view. Specified in [spec 05 §11](../03-specs/05-agent-registry.md#11-natural-language-builder) and [spec 19 §5.1](../03-specs/19-web-app.md#51-natural-language-builder).
- Every page has a designed empty state, a loading state, and an error state. Streaming shows a caret and does not jump the scroll position when the user has scrolled up.
- WCAG 2.1 AA, keyboard access, visible focus, labelled inputs, and axe clean on the page. Layouts work at 375 px and 1280 px.
- First login lands in a short onboarding path: one sentence of what the product does, then the natural-language builder. No settings wall.
- Quality bar: [ux-quality](../08-quality/ux-quality.md) and [spec 19 §11](../03-specs/19-web-app.md#11-presentation-quality-bar).

## 3. Industry-agnostic, extensible core

Core has no industry in it. Governance, risk, compliance, and any other vertical live in packs.

Checkable:

- No core table, column, setting, permission, route, or Python module is named for an industry. Evidence is an immutable record store. Guests are external participants. Sign-off, segregation of duties, legal hold, retention, the AI register, and binders are generic.
- A feature that only one industry needs is a pack, installed through the extension framework, with no core code change.
- Integrations, MCP servers, tools, connectors, agent templates, skills, domain tables, and UI pages are packs or connector plugins.
- The framework covers packaging, manifest, versioning, install, upgrade, uninstall, permissions, a config schema, UI contribution points, pack-owned migrations, and a testing kit. Normative: [extension-framework](../05-contracts/extension-framework.md).

## 4. The GRC pack covers the ask

The GRC pack is the first solution pack. It is specified to answer the GRC work a client asks for, including the corner cases in [use-cases](../10-grc-pack/use-cases.md). A row in that catalogue is either implemented by a named task or marked as a deliberate later cut.

## 5. Best defaults

A new tenant or deployment works after secrets and identity are set. Nothing else is mandatory.

Checkable:

- Every setting has a default in [environments](../07-ops/environments.md) or in `tenants.settings`. The required set is only the variables marked in [environments §3.2](../07-ops/environments.md#32-required-versus-defaulted).
- Definition fields document their default in [definition-schema §12](../05-contracts/definition-schema.md#12-defaults).
- Settings screens have Simple mode (plain language, the common choices) and Advanced mode (every field and the raw document). Specified in [spec 19 §12](../03-specs/19-web-app.md#12-simple-and-advanced-settings).

## 6. Clean code

Names match the spec. Modules stay inside the layering rules. Generated clients are not hand-edited. A task that needs a new name adds it to the owning spec and the catalogue in the same change.
