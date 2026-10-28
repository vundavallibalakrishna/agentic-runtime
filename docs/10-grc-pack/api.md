# GRC pack HTTP API

Mounted at `/api/v1/ext/grc` only when the tenant has the pack enabled ([spec 21 §6](../03-specs/21-records-governance.md#6-pack-extension-points)). Disabled pack routes return 404. Conventions: [api-conventions](../05-contracts/api-conventions.md). Tables: [domain-model](domain-model.md). Every state change audits the action named in [audit §3](../06-security/audit.md#3-catalogue).

Cross-tenant access returns 404. Guest callers may use only the routes whose text says a guest grant applies, and only for ids in `scope.pack_record_ids`.

## Frameworks

#### GET /api/v1/ext/grc/frameworks
`grc.frameworks:read`. List frameworks. Query `q`, `licence` (`free`|`skeleton`). Item `{id, key, name, version, licence, requirement_count}`.

#### POST /api/v1/ext/grc/frameworks
`grc.frameworks:manage`. Create a tenant framework shell. Body `{key, name, version, licence: skeleton|free}`. `licence=free` is only for catalogues the pack ships. Audit `grc.framework.imported` when the body is an import.

#### GET /api/v1/ext/grc/frameworks/{framework_id}
`grc.frameworks:read`. Framework plus counts of requirements and controls.

#### PATCH /api/v1/ext/grc/frameworks/{framework_id}
`grc.frameworks:manage`. Update name or version label. Refuses edits to `licence=free` rows the pack owns (403 `pack_owned`).

#### POST /api/v1/ext/grc/frameworks:import-oscal
`grc.frameworks:manage`. Body `{file_id}` of an OSCAL catalog or profile JSON. Creates or updates a `licence=free` framework, requirements and controls. Response `{framework_id, created, updated, errors}`.

#### GET /api/v1/ext/grc/frameworks/{framework_id}:export-oscal
`grc.frameworks:read`. Returns OSCAL catalog JSON for a free framework. Skeleton frameworks export ids and titles only.

#### POST /api/v1/ext/grc/frameworks/{framework_id}:import-licensed-text
`grc.frameworks:manage`. Body `{file_id, attestation: true}`. `attestation` must be true (the caller confirms they hold a licence). Fills `statement` on matching control ids. Refuses `licence=free`. Audit `grc.framework.imported`.

#### GET /api/v1/ext/grc/frameworks/{framework_id}/requirements
`grc.frameworks:read`. Requirements for one framework.

#### GET /api/v1/ext/grc/requirements/{requirement_id}
`grc.frameworks:read`. Requirement plus linked controls.

## Controls and crosswalks

#### GET /api/v1/ext/grc/controls
`grc.controls:read`. Query `framework_id`, `q`, `owner_user_id`. Common controls have `framework_id` null.

#### POST /api/v1/ext/grc/controls
`grc.controls:manage`. Create a tenant control. Body `{key, title, statement?, framework_id?, owner_user_id?}`.

#### GET /api/v1/ext/grc/controls/{control_id}
`grc.controls:read`. Control, mappings, tests and evidence link counts.

#### PATCH /api/v1/ext/grc/controls/{control_id}
`grc.controls:manage`. Update title, statement, owner. Audit `grc.control.updated`.

#### GET /api/v1/ext/grc/control-mappings
`grc.controls:read`. Query `status` (`suggested`|`confirmed`|`rejected`), `from_control_id`, `to_control_id`.

#### POST /api/v1/ext/grc/control-mappings
`grc.controls:manage`. Body `{from_control_id, to_control_id, confidence, rationale}`. Status `suggested` unless `confirmed: true`, which requires the caller to be a second user when confidence is below 1.

#### POST /api/v1/ext/grc/control-mappings/{mapping_id}:confirm
`grc.controls:manage`. Sets `status=confirmed`, `confirmed_by`, `confirmed_at`. The confirmer must not be `suggested_by` ([spec 09 §12](../03-specs/09-policy-approvals.md#12-segregation-of-duties) agent-owner rule does not apply; this is a two-person confirm). Audit `grc.mapping.confirmed`.

#### POST /api/v1/ext/grc/control-mappings/{mapping_id}:reject
`grc.controls:manage`. Audit `grc.mapping.rejected`.

#### POST /api/v1/ext/grc/control-mappings:suggest
`grc.controls:read`. Body `{from_framework_id, to_framework_id}`. Runs the crosswalk agent template asynchronously. Response `202 {run_id}`. Suggestions land as `status=suggested` and wait for `:confirm`.

## Evidence links and tests

#### GET /api/v1/ext/grc/evidence-links
`grc.controls:read`. Query `control_id`, `stale=true`. A link is stale when `now() > collected_at + freshness_days`.

#### POST /api/v1/ext/grc/evidence-links
`grc.evidence:link`. Body `{control_id, evidence_item_id, freshness_days}`. The evidence item must exist in the core vault and the caller must hold `evidence:read`. Audit `grc.evidence.linked`.

#### DELETE /api/v1/ext/grc/evidence-links/{link_id}
`grc.evidence:link`. Removes the link. Does not delete the evidence item.

#### GET /api/v1/ext/grc/control-tests
`grc.tests:read`. Query `control_id`.

#### POST /api/v1/ext/grc/control-tests
`grc.controls:manage`. Body `{control_id, key, procedure, schedule, freshness_days}`.

#### PATCH /api/v1/ext/grc/control-tests/{test_id}
`grc.controls:manage`. Update procedure or schedule.

#### POST /api/v1/ext/grc/control-tests/{test_id}:run
`grc.tests:run`. Starts the control-tester routine immediately. Response `202 {run_id}`.

#### GET /api/v1/ext/grc/test-results
`grc.tests:read`. Query `test_id`, `outcome` (`pass`|`fail`|`error`).

## Findings and issues

#### GET /api/v1/ext/grc/findings
`grc.findings:read`. Query `status`, `severity`, `control_id`.

#### POST /api/v1/ext/grc/findings
`grc.findings:manage`. Body `{title, severity, control_id?, evidence_item_id?, owner_user_id?}`. Audit `grc.finding.created`. Tool `grc.findings.create` is W2 and calls this service.

#### GET /api/v1/ext/grc/findings/{finding_id}
`grc.findings:read`. Finding plus linked issue ids.

#### PATCH /api/v1/ext/grc/findings/{finding_id}
`grc.findings:manage`. Update owner, severity, due date.

#### POST /api/v1/ext/grc/findings/{finding_id}:close
`grc.findings:manage`. Body `{evidence_item_id}`. Refuses 409 `closure_evidence_required` when the evidence item is missing or fails verification. Audit `grc.finding.closed`.

#### GET /api/v1/ext/grc/issues
`grc.findings:read`. Remediation issues. Query `status`, `due_before`.

#### POST /api/v1/ext/grc/issues
`grc.findings:manage`. Body `{finding_id, title, owner_user_id, due_at, external_ref?}`.

#### PATCH /api/v1/ext/grc/issues/{issue_id}
`grc.findings:manage`. Update status, owner, due date, external reference.

## Risks and assets

#### GET /api/v1/ext/grc/assets
`grc.risks:read`. Asset inventory.

#### POST /api/v1/ext/grc/assets
`grc.risks:manage`. Body `{name, kind, owner_user_id?}`.

#### GET /api/v1/ext/grc/risks
`grc.risks:read`. Query `status`, `asset_id`.

#### POST /api/v1/ext/grc/risks
`grc.risks:manage`. Body `{title, statement, asset_id?, likelihood, impact}`. Inherent score is `likelihood * impact` using the tenant's 1..5 scales. Audit `grc.risk.proposed` when `source=agent`.

#### GET /api/v1/ext/grc/risks/{risk_id}
`grc.risks:read`. Risk, assessments, treatments.

#### PATCH /api/v1/ext/grc/risks/{risk_id}
`grc.risks:manage`. Update statement or scores. Score changes open a new `risk_assessments` row; they do not overwrite history.

#### POST /api/v1/ext/grc/risks/{risk_id}:accept
`grc.risks:manage`. Body `{statement_text, expires_at}`. Opens a review item on the risk statement hash ([spec 09 §11](../03-specs/09-policy-approvals.md#11-reviews-and-sign-off)). Status becomes `accepted` only when that item is `signed`. Audit `grc.risk.accepted` at that moment, not at this call.

#### GET /api/v1/ext/grc/risks/{risk_id}/treatments
`grc.risks:read`. Treatments for one risk.

#### POST /api/v1/ext/grc/risks/{risk_id}/treatments
`grc.risks:manage`. Body `{kind: mitigate|transfer|avoid, plan, owner_user_id, due_at}`.

## Vendors

#### GET /api/v1/ext/grc/vendors
`grc.vendors:read`. Query `tier`, `q`.

#### POST /api/v1/ext/grc/vendors
`grc.vendors:manage`. Body `{name, owner_user_id}`. Audit `grc.vendor.created`.

#### GET /api/v1/ext/grc/vendors/{vendor_id}
`grc.vendors:read`. Vendor plus assessments.

#### PATCH /api/v1/ext/grc/vendors/{vendor_id}
`grc.vendors:manage`. Update name, owner, tier.

#### GET /api/v1/ext/grc/vendors/{vendor_id}/assessments
`grc.vendors:read`. Assessments, newest first.

#### POST /api/v1/ext/grc/vendors/{vendor_id}/assessments
`grc.vendors:manage`. Body `{kind: intake|questionnaire|document_review, due_at}`. Creates a campaign of kind `vendor` when a questionnaire is requested.

#### POST /api/v1/ext/grc/vendor-assessments/{assessment_id}:score
`grc.vendors:manage`. Body `{tier, rationale, evidence_item_ids}`. Audit `grc.assessment.completed`.

## Policies and obligations

#### GET /api/v1/ext/grc/policies
`grc.policies:read`. GRC policy documents, not OPA policies.

#### POST /api/v1/ext/grc/policies
`grc.policies:manage`. Body `{key, title, owner_user_id}`.

#### GET /api/v1/ext/grc/policies/{policy_id}
`grc.policies:read`. Policy plus versions.

#### POST /api/v1/ext/grc/policies/{policy_id}/versions
`grc.policies:manage`. Body `{body_md, change_note}`. Creates a draft version.

#### POST /api/v1/ext/grc/policies/{policy_id}:submit-review
`grc.policies:manage`. Opens a review item bound to the draft version hash.

#### POST /api/v1/ext/grc/policy-versions/{version_id}:publish
`grc.policies:manage`. Allowed only when the review item is `signed`. Audit `grc.policy.published`.

#### GET /api/v1/ext/grc/obligations
`grc.obligations:read`. Query `regulator`, `status`.

#### POST /api/v1/ext/grc/obligations
`grc.obligations:manage`. Body `{regulator, citation, statement, owner_user_id}`.

#### PATCH /api/v1/ext/grc/obligations/{obligation_id}
`grc.obligations:manage`. Audit `grc.obligation.updated`.

#### GET /api/v1/ext/grc/regulatory-changes
`grc.obligations:read`. Query `status` (`new`|`triaged`|`dismissed`).

#### POST /api/v1/ext/grc/regulatory-changes/{change_id}:triage
`grc.obligations:manage`. Body `{relevant: bool, obligation_ids, control_ids, note}`. Audit `grc.regulatory_change.triaged`.

#### GET /api/v1/ext/grc/regulator-feeds
`grc.obligations:read`. Configured feeds.

#### POST /api/v1/ext/grc/regulator-feeds
`grc.obligations:manage`. Body `{regulator, url}`. The URL must pass the SSRF guard.

## Incidents

#### GET /api/v1/ext/grc/incidents
`grc.incidents:read`. Query `status`.

#### POST /api/v1/ext/grc/incidents
`grc.incidents:manage`. Body `{title, detected_at, summary}`. Audit `grc.incident.opened`. Does not start a clock until `:start-clock`.

#### GET /api/v1/ext/grc/incidents/{incident_id}
`grc.incidents:read`. Incident plus clocks and notification drafts.

#### PATCH /api/v1/ext/grc/incidents/{incident_id}
`grc.incidents:manage`. Update summary or status.

#### POST /api/v1/ext/grc/incidents/{incident_id}:start-clock
`grc.incidents:manage`. Body `{regime: cert_in|dpdp|gdpr}`. Starts a Temporal timer for 6 h (`cert_in`) or 72 h (`dpdp`, `gdpr`). A second start for the same regime returns the existing clock.

#### POST /api/v1/ext/grc/incidents/{incident_id}:file-notification
`grc.incidents:manage`. Body `{regime, body_md}`. Opens a review item. Filing is recorded only after sign-off, with the signed hash. Audit `grc.incident.notified`.

## Campaigns and questionnaires

#### GET /api/v1/ext/grc/campaigns
`grc.campaigns:read`. Query `kind` (`questionnaire`|`vendor`|`acknowledgement`|`attestation`|`access_review`).

#### POST /api/v1/ext/grc/campaigns
`grc.campaigns:manage`. Body `{kind, title, due_at, audience}`.

#### GET /api/v1/ext/grc/campaigns/{campaign_id}
`grc.campaigns:read`. Campaign plus item counts.

#### POST /api/v1/ext/grc/campaigns/{campaign_id}:start
`grc.campaigns:manage`. Materialises `campaign_items` and notifies assignees. Audit `grc.campaign.started`.

#### POST /api/v1/ext/grc/campaigns/{campaign_id}:close
`grc.campaigns:manage`. Refuses when required items are still open unless `force: true` with step-up.

#### GET /api/v1/ext/grc/campaign-items
`grc.campaigns:read`. Query `campaign_id`, `assignee=me`, `status`.

#### POST /api/v1/ext/grc/campaign-items/{item_id}:decide
`object-level (see spec)`. Assignee, or `grc.campaigns:manage`. Body `{decision, statement_text}`. Writes a sign-off through the core review API when the campaign kind is `acknowledgement`, `attestation` or `access_review`. Audit `grc.campaign_item.decided` and `grc.policy.acknowledged` for acknowledgement campaigns.

#### GET /api/v1/ext/grc/answer-library
`grc.questionnaires:read`. Query `q`, `include_expired=false`.

#### POST /api/v1/ext/grc/answer-library
`grc.questionnaires:manage`. Body `{question, answer_md, owner_user_id, expires_at, citations}`.

#### PATCH /api/v1/ext/grc/answer-library/{answer_id}
`grc.questionnaires:manage`. Update answer or expiry. Audit `grc.answer.approved` when `status` becomes `approved`.

#### POST /api/v1/ext/grc/questionnaires:draft
`grc.questionnaires:manage`. Body `{file_id}`. Starts the questionnaire-answerer. Response `202 {run_id}`.

#### POST /api/v1/ext/grc/questionnaires/{job_id}:export
`grc.questionnaires:manage`. Exports the reviewed workbook in the source format. Every exported answer must be `approved` or the response is 409 `review_required`.

## Audit portal, access reviews and reports

#### GET /api/v1/ext/grc/pbc-requests
`grc.audit_portal:manage`. Also visible to a guest with a grant whose `pack_record_ids` include the request, and to the request owner.

#### POST /api/v1/ext/grc/pbc-requests
`grc.audit_portal:manage`. Body `{title, control_id?, owner_user_id, due_at}`.

#### PATCH /api/v1/ext/grc/pbc-requests/{request_id}
`grc.audit_portal:manage`. Update status or response. Status `provided` requires a signed review of the response. A guest whose grant lists the request may set status `accepted` only after it is `provided`. Audit `grc.pbc.updated`.

#### GET /api/v1/ext/grc/pbc-requests/{request_id}/response
`grc.audit_portal:manage`, the owner, or a guest whose grant lists the request. Returns the response PDF. A guest download is watermarked by the core watermark.

#### POST /api/v1/ext/grc/pbc-lists:import
`grc.audit_portal:manage`. Body `{file_id}` of an XLSX list. Creates one request per row.

#### GET /api/v1/ext/grc/entitlements
`grc.campaigns:read`. Query `source`, `subject`.

#### POST /api/v1/ext/grc/entitlements:ingest
`grc.campaigns:manage`. Body `{source: okta|entra|google, connection_id}`. Audit `grc.entitlement.ingested`.

#### GET /api/v1/ext/grc/sod-rules
`grc.campaigns:read`. Business SoD rules. These are not core `sod_constraints`.

#### POST /api/v1/ext/grc/sod-rules
`grc.campaigns:manage`. Body `{name, entitlement_a, entitlement_b}`.

#### PATCH /api/v1/ext/grc/sod-rules/{rule_id}
`grc.campaigns:manage`. Update name or pair.

#### DELETE /api/v1/ext/grc/sod-rules/{rule_id}
`grc.campaigns:manage`. Delete a business SoD rule.

#### GET /api/v1/ext/grc/report-templates
`grc.reports:export`. Template keys: `soa`, `soc2_binder`, `cscrf`, `dpdp_breach`, `board_pack`.

#### POST /api/v1/ext/grc/reports:render
`grc.reports:export`. Body `{template, params}`. Calls the core binder API ([spec 21 §5](../03-specs/21-records-governance.md#5-binder-export)) and returns `202 {binderId}`. Audit `grc.report.exported`.

## Extended records

#### GET /api/v1/ext/grc/entities
`grc.entities:read`. Tree of legal entities, divisions and regions inside the tenant.

#### POST /api/v1/ext/grc/entities
`grc.entities:manage`. Body `{name, kind, parentId?}`. Audit `grc.entity.updated`.

#### GET /api/v1/ext/grc/entities/{entity_id}/posture
`grc.entities:read`. Counts of controls, open findings and risks for the entity and its children.

#### GET /api/v1/ext/grc/exceptions
`grc.controls:read`. Query `controlId`, `status`.

#### POST /api/v1/ext/grc/exceptions
`grc.exceptions:manage`. Body `{controlId, kind, rationale, compensatingControlId?, expiresAt}`. A waiver requires `compensatingControlId`. Opens a review item. Audit `grc.exception.signed` when the item is signed, not on this call.

#### GET /api/v1/ext/grc/ethics-cases
`grc.ethics:manage`. Restricted cases are omitted for every other permission.

#### GET /api/v1/ext/grc/ethics-cases/{case_id}
`grc.ethics:manage`. A caller without that permission, including a tenant auditor, receives 404.

#### POST /api/v1/ext/grc/ethics-cases
`grc.ethics:manage`. Body `{title, legalHoldId?}`. Audit `grc.ethics.opened`. A legal hold is attached only when `legalHoldId` already exists. The call does not create one.

#### GET /api/v1/ext/grc/inspections
`grc.inspections:manage`.

#### POST /api/v1/ext/grc/inspections
`grc.inspections:manage`. Body `{regulator, startedOn}`. Creates a binder and returns `{inspectionId, binderId}`. Audit `grc.inspection.opened`.

#### GET /api/v1/ext/grc/dsar-requests
`grc.privacy:manage`.

#### POST /api/v1/ext/grc/dsar-requests
`grc.privacy:manage`. Body `{requestType, dueAt, subjectUserId?}`. An `erasure` opens a review. Audit `grc.dsar.fulfilled` when status becomes `fulfilled`.

#### POST /api/v1/ext/grc/dsar-requests/{request_id}:fulfil
`grc.privacy:manage`. Marks the request `fulfilled`. An `erasure` for a platform user starts the core erasure flow after the review is signed and skips records under a legal hold.

#### GET /api/v1/ext/grc/consent-records
`grc.privacy:manage`.

#### POST /api/v1/ext/grc/consent-records
`grc.privacy:manage`. Body `{subjectRef, purpose, state, evidenceItemId}`. Audit `grc.consent.recorded`.

#### GET /api/v1/ext/grc/resilience-tests
`grc.controls:read`.

#### POST /api/v1/ext/grc/resilience-tests
`grc.controls:manage`. Body `{kind, testedOn, outcome, evidenceItemId}`. Audit `grc.resilience.recorded`.

#### POST /api/v1/ext/grc/assets
`grc.risks:manage`. Body `{name, kind, ownerUserId?, tier?, agentCardId?}`. `kind=model` is the model-risk inventory and requires `ownerUserId` and `tier`. `agentCardId` is optional and refers to a core card. The call does not write `agent_cards`.
