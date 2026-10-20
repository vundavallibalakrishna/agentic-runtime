# Framework catalogues

Decision: [OQ-27](../open-questions.md). The pack ships control identifiers and, where the text is freely licensed, the statement text. Customers import licensed text for copyrighted catalogues. Machine-readable exchange uses NIST OSCAL (catalog and profile JSON) through [api.md](api.md).

## What ships

| Catalogue | `licence` | What is in the pack |
|---|---|---|
| NIST CSF 2.0 | `free` | OSCAL catalog converted from the NIST publication. Identifiers, titles and statements. |
| NIST SP 800-53 | `free` | OSCAL catalog from NIST. |
| CSA CCM and CAIQ | `free` | Control ids, titles and the CAIQ question text CSA publishes for reuse. |
| DPDP Act 2023 and DPDP Rules 2025 | `free` | Obligation rows citing the public statute and rules. Not a substitute for the Gazette text. |
| CERT-In directions (2022) | `free` | Obligation rows for the 6-hour report and 180-day log retention, citing the public directions. |
| RBI / SEBI CSCRF obligation list | `free` | Obligation ids and short titles drawn from the public circulars, with the source URL. Not the circular PDF. |
| ISO/IEC 27001:2022 Annex A | `skeleton` | Control ids and the short titles that ISO's publicly listed annex headings use. Statement text is empty until the customer imports a licensed copy. |
| SOC 2 Trust Services Criteria | `skeleton` | Criteria ids only. |
| PCI DSS v4.0.1 | `skeleton` | Requirement ids only. |

## Customer import

`POST /api/v1/ext/grc/frameworks/{framework_id}:import-licensed-text` accepts a CSV or OSCAL file with columns `key` and `statement`. The caller sends `attestation: true`, recorded on the audit event `grc.framework.imported` as `detail.licence_attested=true`. The pack does not phone home to check the licence. Import matches on `key` and refuses unknown keys (422 with the list). It never runs against `licence=free` frameworks.

## Common control set

The pack seeds a tenant-local common control set (`grc.controls` rows with `framework_id` null, keys `CC-*`). Shipped crosswalk rows map each common control to NIST CSF and NIST 800-53 with `status=confirmed` and `confidence=1` where the NIST OSCAL relationship is explicit. Mappings to ISO, SOC 2 and PCI are `status=suggested` with `confidence` below 1 and must be confirmed by a person who did not suggest them (`:confirm`). The crosswalk agent ([agent-templates](agent-templates.md)) may only insert `suggested` rows.

## Export

`GET ...:export-oscal` emits a catalog. Skeleton frameworks omit `statement` prose. Free frameworks include it. The export is the tenant's copy, including confirmed mappings as OSCAL mapping collection when the caller asks `?include_mappings=true`.
