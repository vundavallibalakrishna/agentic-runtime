# M16 — GRC pack foundation

Goal: the GRC pack schema, framework catalogues and control catalogue are usable by later pack tasks. Core tables are not modified.

Exit criteria: a tenant with the pack enabled can import the NIST OSCAL catalogue, see the common control set, confirm a crosswalk, and link a core evidence item. ISO, PCI and SOC 2 rows have ids and titles only until a licensed-text import.

M16 starts after M14-T13. It may run in parallel with M15.

---

### M16-T01 · Pack skeleton, `grc` schema and RLS
- **Depends on:** M14-T13
- **Areas:** `packs/grc/**`, `packs/grc/migrations/`, `packs/grc/alembic.ini`
- **Spec:** [10-grc-pack](../10-grc-pack/README.md), [domain-model](../10-grc-pack/domain-model.md), [migrations §6](../04-data/migrations.md#6-pack-schemas)
- **Do:** Package `ar_pack_grc`. Alembic environment from `ar_domain.packs.alembic_env('grc', 'grc')` with version table `grc_alembic_version`. Create every table in the domain-model DDL, including `grc.regulator_feeds` (27 tables). RLS using the core helper, `FORCE ROW LEVEL SECURITY`. Register the router mount, permissions and audit actions from the manifest, but leave route bodies for the tasks below. Content-pack manifest `metadata.id=grc` signed in M19-T05; this task installs it in dev with `AR_PACK_SIGNATURE_REQUIRED=false`.
- **Done when:** `alembic -c packs/grc/alembic.ini upgrade head` creates schema `grc` and does not add a core revision; a second tenant cannot read the first tenant's controls.
- **Tests:** pack migration upgrade/downgrade; RLS cross-tenant; import-linter still forbids `ar_pack_grc` from `libs/` and `services/`.

### M16-T02 · Frameworks, requirements, controls and OSCAL
- **Depends on:** M16-T01
- **Areas:** `packs/grc/src/ar_pack_grc/{frameworks.py,oscal.py}`, `packs/grc/catalogues/`
- **Spec:** [framework-catalogues](../10-grc-pack/framework-catalogues.md), [api](../10-grc-pack/api.md), [OQ-27](../open-questions.md)
- **Do:** Endpoints under `/api/v1/ext/grc/frameworks`, `/requirements` and `/controls`. Ship NIST CSF 2.0, NIST 800-53 and CSA CCM/CAIQ as OSCAL imports, plus DPDP, CERT-In and CSCRF obligation ids from public text. ISO 27001, SOC 2 and PCI DSS are id-and-title skeletons. `import-licensed-text` requires `attestation: true` and refuses `licence=free`.
- **Done when:** an OSCAL fixture round-trips through import and export; a skeleton export contains no statement text; a licensed import fills statements only for matching ids.
- **Tests:** OSCAL fixture; licence refusal; audit `grc.framework.imported`.

### M16-T03 · Common controls and crosswalk confirmation
- **Depends on:** M16-T02
- **Areas:** `packs/grc/catalogues/common-controls.yaml`, `packs/grc/src/ar_pack_grc/mappings.py`
- **Spec:** [framework-catalogues](../10-grc-pack/framework-catalogues.md), [api](../10-grc-pack/api.md)
- **Do:** Seed common controls `CC-*`. Mapping endpoints including `:suggest`, `:confirm` and `:reject`. Confirm requires a different user from `suggested_by`. Suggestions are not confirmed by the agent.
- **Done when:** a suggested mapping stays `suggested` until a second principal confirms it; the confirmer cannot be the suggester.
- **Tests:** two-person confirm; reject audit `grc.mapping.rejected`.

### M16-T04 · Evidence links and freshness
- **Depends on:** M16-T02, M14-T08
- **Areas:** `packs/grc/src/ar_pack_grc/evidence_links.py`
- **Spec:** [api](../10-grc-pack/api.md), [spec 21 §1](../03-specs/21-records-governance.md#1-evidence-vault)
- **Do:** `grc.evidence_links` pointing at core `evidence_items`. Link create requires `grc.evidence:link` and `evidence:read`. `stale=true` when `now()` is past `collected_at + freshness_days`. Delete removes the link only.
- **Done when:** a link to another tenant's evidence returns 404; deleting the link leaves the evidence item.
- **Tests:** freshness query; permission pair; cross-tenant.

### M16-T05 · `grc` MCP read tools
- **Depends on:** M16-T02, M16-T04
- **Areas:** `packs/grc/src/ar_pack_grc/mcp_server.py`
- **Spec:** [connectors](../10-grc-pack/connectors.md)
- **Do:** Register MCP server `grc` with the read tools: `grc.controls.search`, `grc.controls.get`, `grc.mapping.suggest` (R1), `grc.questionnaire.search_answers`, `grc.vendors.get`, `grc.policies.search`, `grc.obligations.search`. Write tools are registered in the task that defines their behaviour (M17-T05, M18). Disabled pack returns 404 from the gateway.
- **Done when:** an agent in an enabled tenant can search controls; the same call in a disabled tenant is `tool_server_unavailable`.
- **Tests:** MCP conformance for the read tools; enable flag.

### M16-T06 · Web: frameworks, controls, evidence
- **Depends on:** M16-T05
- **Areas:** `apps/web/src/app/(app)/grc/{frameworks,controls,evidence}/**`
- **Spec:** [spec 19 §10](../03-specs/19-web-app.md), [10-grc-pack](../10-grc-pack/README.md)
- **Do:** Pages under `/grc` for frameworks, controls and evidence links. The nav item comes from `GET /api/v1/tenant/packs` and is absent when the pack is disabled. Empty, loading and error states. Permission `grc.controls:read` gates the pages.
- **Done when:** disabling the pack hides `/grc` and a direct visit 404s in the UI.
- **Tests:** Vitest; Playwright import OSCAL and open a control; axe.

### M16-T07 · Entities inside one tenant
- **Depends on:** M16-T01
- **Areas:** `packs/grc/src/ar_pack_grc/entities.py`
- **Spec:** [use-cases U16](../10-grc-pack/use-cases.md), [domain-model](../10-grc-pack/domain-model.md)
- **Do:** Table `grc.entities` with `parent_id`. A control, risk, vendor, and policy may set `entity_id` (nullable, added in this migration). Rollup `GET /api/v1/ext/grc/entities/{entity_id}/posture` returns child counts. This is not a second tenant and it does not cross RLS.
- **Done when:** a parent sees child counts; a child principal with a grant scoped to one entity does not see the sibling.
- **Tests:** tree cycle rejected; cross-entity read denied.
