# GRC solution pack

A solution pack for governance, risk and compliance buyers. It is not part of core 1.0. It installs through the content-pack and extension hooks ([spec 05 §10](../03-specs/05-agent-registry.md#10-content-packs), [spec 21 §6](../03-specs/21-records-governance.md#6-pack-extension-points), [ADR-0023](../02-architecture/adr/ADR-0023-pack-extensions.md)) and never changes a core table.

| Item | Value |
|---|---|
| Package | `ar_pack_grc` |
| Path | `packs/grc` |
| Schema | `grc` |
| Alembic version table | `grc_alembic_version` |
| HTTP mount | `/api/v1/ext/grc` |
| Web routes | `/grc/*`, rendered only when the pack is enabled for the tenant |
| MCP server | `grc` |
| Plan | [M16](../09-plan/M16-grc-foundation.md) through [M19](../09-plan/M19-grc-audit-reporting.md) |

## Documents

| File | What it specifies |
|---|---|
| [prd.md](prd.md) | User stories `US-GRC-01`..`US-GRC-15` |
| [use-cases.md](use-cases.md) | Use-case catalogue and coverage matrix |
| [domain-model.md](domain-model.md) | Schema `grc` (27 tables) and RLS |
| [api.md](api.md) | HTTP contracts under `/api/v1/ext/grc` |
| [framework-catalogues.md](framework-catalogues.md) | What text ships, and how customers import licensed text |
| [connectors.md](connectors.md) | Evidence connectors and the `grc` MCP tools |
| [agent-templates.md](agent-templates.md) | Agent, skill and routine definitions |

Core behaviour the pack depends on is specified outside this folder: evidence ([spec 21](../03-specs/21-records-governance.md)), sign-off ([spec 09 §11](../03-specs/09-policy-approvals.md#11-reviews-and-sign-off)), strict grounding ([spec 07 §13](../03-specs/07-agent-runtime.md#13-strict-grounding)), run records ([spec 18 §7](../03-specs/18-observability-eval.md#7-run-records-and-re-performance)), guests ([spec 21 §4](../03-specs/21-records-governance.md#4-guest-principals)).

M16 starts after [M14-T13](../09-plan/M14-security-compliance.md). It may run in parallel with M15. The breach workflow ([M18-T06](../09-plan/M18-grc-workflows.md)) is targeted before DPDP Rule 7 applies on 13 May 2027. CSCRF ATR and sampling skills are targeted before the FY 2026-27 audit cycle (mid-2027).
