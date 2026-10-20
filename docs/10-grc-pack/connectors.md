# GRC evidence connectors

Each connector is an MCP server registered through the normal tool lifecycle ([spec 08 §2](../03-specs/08-tool-registry-mcp.md#2-lifecycle)). Read tools are R0 or R1. Write tools are W2. Every successful read that is kept as evidence calls the core helper `records.capture` ([spec 21 §1.1](../03-specs/21-records-governance.md#11-built-in-tools)) with `source_system` set to the server slug, `collection_method=tool_call`, and `provenance.request_sha256` set to the SHA-256 of the canonical request. Pagination uses the remote API's cursor and stops at `AR_GRC_CONNECTOR_MAX_PAGES` (default 50, [environments §3.1](../07-ops/environments.md#31-variables-added-for-records-grounding-and-packs)). M17-T01 adds that variable to `ar_common.settings` and `.env.example` when the kit is implemented.

The shared kit (`packs/grc/src/ar_pack_grc/connectors/kit.py`) supplies: cursor loops, exponential backoff on 429, a stable `args_hash`, and the capture helper. Connectors do not write the evidence bucket themselves.

## P1

| Server slug | Systems | Read tools (R0/R1) | Write tools (W2) |
|---|---|---|---|
| `grc_aws` | AWS Config, IAM, CloudTrail, Security Hub | `list_config_rules`, `list_iam_users`, `get_trail_status`, `list_security_hub_findings` | none |
| `grc_azure` | Azure Policy, Entra ID, Defender for Cloud | `list_policy_states`, `list_users`, `list_role_assignments`, `list_defender_alerts` | none |
| `grc_gcp` | Security Command Center, IAM | `list_findings`, `list_iam_policy` | none |
| `grc_okta` | Okta | `list_users`, `list_factors`, `list_admin_roles` | none |
| `grc_entra` | Microsoft Entra ID | `list_users`, `list_auth_methods`, `list_directory_roles` | none |
| `grc_google` | Google Workspace | `list_users`, `list_mfa`, `list_admin_roles` | none |
| `grc_github` | GitHub | `list_branch_protection`, `list_pr_reviews` | none |
| `grc_gitlab` | GitLab | `list_protected_branches`, `list_approvals` | none |
| `grc_jira` | Jira | `search_issues` | `create_issue`, `update_issue` |
| `grc_servicenow` | ServiceNow ITSM and GRC tables | `get_records` | `create_record`, `update_record` |

Write tools pass policy and approval like any other W2 tool. Findings sync is: a pack workflow creates or updates the external record, then stores `issues.external_ref`.

## P2

| Server slug | Systems | Evidence |
|---|---|---|
| `grc_crowdstrike` | CrowdStrike | Endpoint coverage, sensor health |
| `grc_defender` | Microsoft Defender | Endpoint coverage, alerts |
| `grc_intune` | Intune | Encryption, compliance state |
| `grc_jamf` | Jamf | Encryption, inventory |
| `grc_tenable` | Tenable | Vulnerability aging |
| `grc_qualys` | Qualys | Vulnerability aging |
| `grc_openvas` | OpenVAS | Vulnerability aging |
| `grc_darwinbox` | Darwinbox | Joiners, movers, leavers |
| `grc_keka` | Keka | Joiners, movers, leavers |
| `grc_workday` | Workday | Joiners, movers, leavers, training |
| `grc_successfactors` | SuccessFactors | Joiners, movers, leavers, training |
| `grc_wazuh` | Wazuh | Alert handling, log retention |
| `grc_elastic` | Elastic | Alert handling, log retention |
| `grc_splunk` | Splunk-compatible API | Alert handling, log retention |

## P3

Regulator feeds are knowledge `web` sources plus the parsers in [domain-model](domain-model.md), not MCP write tools. E-signature and DMS imports are `records.capture` of a file the user uploads, `source_system=dms_import`. No extra server is required for 1.0 of the pack.

## Pack MCP server `grc`

Registered by the pack through the tool lifecycle ([spec 08](../03-specs/08-tool-registry-mcp.md)). Names are fixed.

| Tool | Risk | Behaviour |
|---|---|---|
| `grc.controls.search` | R0 | Query `q`, `framework_key`. Returns control ids, titles and framework keys the caller may read. |
| `grc.controls.get` | R0 | One control, its mappings and evidence-link counts. |
| `grc.evidence.attach` | W1 | Body `{control_id, evidence_item_id, freshness_days}`. Calls `POST /api/v1/ext/grc/evidence-links`. |
| `grc.tests.record_result` | W1 | Body `{test_id, outcome, summary, evidence_item_ids}`. Inserts `test_results`. |
| `grc.findings.create` | W2 | Body `{title, severity, control_id, evidence_item_id}`. Approval required. |
| `grc.risks.propose` | W1 | Body `{title, statement, likelihood, impact, asset_id?}`. Audits `grc.risk.proposed`. |
| `grc.questionnaire.search_answers` | R0 | Search the approved answer library. Expired answers are omitted. |
| `grc.questionnaire.draft_answer` | R1 | Returns a draft with citations. Does not write the library. |
| `grc.mapping.suggest` | R1 | Suggests `control_mappings` with `status=suggested`. Does not confirm. |
| `grc.vendors.get` | R0 | Vendor, tier and latest assessment. |
| `grc.policies.search` | R0 | Published GRC policy versions. |
| `grc.obligations.search` | R0 | Obligation register. |
| `grc.incidents.update_draft` | W2 | Updates an incident summary or a notification draft. Does not file. |

## Tests

Each P1 server has a contract test with recorded HTTP fixtures under `packs/grc/tests/fixtures/<slug>/`. The test asserts: pages are followed, a capture is invoked once per kept object, and the request hash is stable for the same fixture.
