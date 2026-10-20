# GRC use-case catalogue

What a client can ask the pack to do, and where it is specified. Core capabilities are generic ([principles §3](../00-overview/principles.md#3-industry-agnostic-extensible-core)). Templates: [agent-templates](agent-templates.md). Stories U1–U15: [prd](prd.md).

Status: **covered** (a task implements it), **partial** (the thin path is specified; the full product is a later pack), **cut** (deliberately not in this pack).

| Id | Use case | Status | Pack | Core |
|---|---|---|---|---|
| U1 | Continuous control monitoring | covered | M17-T05, `control-tester` | routines, sandbox, evidence |
| U2 | Evidence collection from cloud, IdP, ITSM, code, HR, EDR | covered for P1; P2 servers are fixtures in [connectors](connectors.md) | M17-T01..T04 | `records.capture` |
| U3 | PBC and auditor portal | covered | M19-T01, `pbc-responder` | guests, binders, sign-off |
| U4 | Questionnaires (CAIQ, SIG-style, XLSX) | covered | M18-T01 | strict grounding, bulk sign-off |
| U5 | Vendor risk and SOC 2 review | covered | M18-T02 | guests, evidence |
| U6 | Policy draft, publish, acknowledge | covered | M18-T03 | sign-off |
| U7 | Crosswalks, several frameworks per control | covered | M16-T02, M16-T03, `crosswalk-mapper` | none |
| U8 | Regulatory change (India and global feeds) | covered | M18-T05 | knowledge `web` source |
| U9 | Risk register and acceptance | covered | M18-T04 | sign-off |
| U10 | Findings, remediation, ATR | covered | M17-T04, M17-T05, `cscrf-atr` | evidence verify |
| U11 | Breach clocks (CERT-In 6 h, DPDP/GDPR 72 h) | covered | M18-T06 | legal hold, sign-off |
| U12 | Access reviews and business SoD | covered | M19-T02 | sign-off; platform SoD stays core |
| U13 | Attestations and recurring certifications | covered | M19-T03 | sign-off, routines |
| U14 | AI inventory beyond this platform | covered | asset `kind=model`, M19-T08 | agent cards for this platform's agents |
| U15 | Board pack | covered | M19-T04 | binder, `review_before_send` |
| U16 | Multi-entity group (parent, subsidiary, rollup) | covered as a tree inside one tenant | M16-T07 | tenancy stays one tenant; a second tenant is not an entity |
| U17 | Several frameworks on one control | covered | M16-T03 mappings | none |
| U18 | Exceptions and waivers with expiry | covered | M18-T07 | sign-off |
| U19 | Compensating controls | covered | M18-T07 | evidence link |
| U20 | Sampling on a control test | covered | skill `cscrf-sampling`, M18-T05 | sandbox if the population is computed |
| U21 | Evidence expiry | covered | M16-T04 freshness | retention schedules |
| U22 | Auditor independence | covered | M19-T01 guest cannot be the control owner; the grant is not a member role | guests are not users |
| U23 | Regulator inspection room | covered | M19-T06 | binder export |
| U24 | Whistleblower / ethics case | partial | M18-T08 restricted case row | legal hold. No telephone hotline, no case-law library |
| U25 | BCP / DR test records | covered | M19-T08 | evidence |
| U26 | Model risk (SR 11-7 style inventory, validation evidence, tier) | partial | M19-T08 asset `kind=model` plus sign-off | agent cards. No model-development workbench |
| U27 | ESG / CSRD / BRSR reporting engine | cut | obligations and `board_pack` can cite a metric the customer stores as evidence | none. A disclosure taxonomy is a later pack |
| U28 | Privacy DSAR | covered | M19-T07 | erasure and export already in core ([spec 17](../03-specs/17-audit-usage-metering.md)) |
| U29 | Consent records | covered | M19-T07 | evidence item for the proof |
| U30 | Control owner recertification calendar | covered | M19-T03 campaigns | routines |
| U31 | Issue sync to Jira / ServiceNow | covered | M17-T04 | approvals on W2 |
| U32 | Licensed framework text (ISO, PCI, SOC 2, SIG) | covered | customer import, [framework-catalogues](framework-catalogues.md), [OQ-27](../open-questions.md) | none |
| U33 | Hindi and regional circulars | covered as an eval, not a translation product | M18-T05 | model the customer hosts |
| U34 | Group-wide evidence sharing across tenants | cut | not in this pack | would break tenant isolation. Share inside one tenant via U16 |

## Corner-case rules

- A control has many mappings. Confirming one mapping does not confirm the others.
- An exception past `expires_at` is `expired` and the control's test treats it as absent.
- A waiver without a compensating control fails validation.
- An ethics case with `restricted=true` is visible only to principals with `grc.ethics:manage` and to nobody else, including tenant auditors.
- A DSAR of type `erasure` opens the core erasure flow for the matched user when the subject is a platform user. It does not delete evidence under legal hold.
- An inspection binder is a core binder. The regulator's guest grant lists that binder only.

## Suggested cuts

ESG disclosure engines, cross-tenant evidence sharing, a whistleblower hotline, and a model-development workbench are out of this pack on purpose. They are named above so a later agent does not invent them inside core.
