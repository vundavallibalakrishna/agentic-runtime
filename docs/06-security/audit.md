# Audit

Implementation: [spec 17 §1](../03-specs/17-audit-usage-metering.md#1-audit), table `audit_events` ([schema §15](../04-data/schema.md#15-audit-and-usage-ar_domainaudit-ar_domainusage)). This file is the **action catalogue**: `ar_domain.audit.actions.AuditAction` must contain exactly the actions below (test `test_audit_actions_match_docs` parses this file).

## 1. Properties

- Written in the same transaction as the change (no change without audit).
- Per-tenant hash chain (`tenant_seq`, `prev_hash`, `hash`), append-only trigger, `ar_app` has no UPDATE/DELETE.
- No content: message text, file contents, tool arguments/results, secrets never appear; tool arguments are represented by `args_hash`; diffs of settings exclude secret fields.
- Verification: `POST /api/v1/audit-events:verify` on demand; nightly per tenant (alert `ARAuditChainBroken`, runbook `rb-09-audit-chain-broken`).
- Export: `POST /api/v1/audit-exports` (JSONL/CSV with verification); archive to Object Lock bucket before retention purge or tenant deletion.
- SIEM: outbox `audit.event` → tenant webhook ([spec 17 §1.2](../03-specs/17-audit-usage-metering.md#12-siem-streaming)).
- Platform-level events (`tenant_id NULL`) form their own chain (platform admin actions, `platform.session_opened`).

## 2. Naming

`<resource>.<verb_past_tense>` in snake_case, resource singular (e.g. `agent.published`). Wildcards in other documents (e.g. `scim.user.*`) refer to all catalogue entries with that prefix. `outcome='failure'` is recorded for denied or failed security-relevant attempts listed with **(F)**.

## 3. Catalogue

| Area | Actions |
|---|---|
| Auth & sessions | `auth.login`, `auth.login_failed` (F), `auth.logout`, `auth.step_up`, `auth.tenant_switched`, `auth.session_revoked` |
| Tenant | `tenant.provisioned`, `tenant.updated`, `tenant.suspended`, `tenant.resumed`, `tenant.deletion_requested`, `tenant.deleted`, `tenant.domain_added`, `tenant.domain_verified`, `tenant.domain_removed`, `tenant.run_callback_secret_rotated` |
| Identity providers & SCIM | `idp.created`, `idp.updated`, `idp.deleted`, `scim_token.created`, `scim_token.revoked`, `scim.user.created`, `scim.user.updated`, `scim.user.deprovisioned`, `scim.group.created`, `scim.group.updated`, `scim.group.deleted` |
| Users, groups, teams | `user.provisioned`, `user.updated`, `user.suspended`, `user.reactivated`, `user.erasure_requested`, `user.notice_accepted`, `user.data_exported`, `invitation.created`, `invitation.revoked`, `invitation.accepted`, `group.created`, `group.deleted`, `group.member_added`, `group.member_removed`, `team.created`, `team.updated`, `team.deleted`, `team.member_added`, `team.member_removed` |
| Roles & keys | `role.created`, `role.updated`, `role.deleted`, `role_assignment.created`, `role_assignment.deleted`, `service_account.created`, `service_account.updated`, `service_account.deleted`, `service_account.on_behalf_of_enabled`, `api_key.created`, `api_key.revoked`, `api_key.denied` (F) |
| Support access | `support_access.granted`, `support_access.revoked`, `support_access.expired`, `platform.session_opened` |
| Secrets & connections | `secret.created`, `secret.updated`, `secret.rotated`, `secret.deleted`, `credential_provider.created`, `credential_provider.updated`, `credential_provider.deleted`, `connection.created`, `connection.revoked`, `connection.expired` |
| Models | `model_provider.created`, `model_provider.updated`, `model_provider.deleted`, `model.created`, `model.updated`, `model.disabled`, `model.deleted`, `model_alias.created`, `model_alias.updated`, `model_alias.deleted` |
| Agents & bundles | `agent.created`, `agent.updated`, `agent.deleted`, `agent.draft_saved`, `agent.published`, `agent.rolled_back`, `agent.duplicated`, `agent.archived`, `agent.unarchived`, `agent.disabled`, `agent.enabled`, `bundle.exported`, `bundle.imported` |
| Conversations & files | `conversation.deleted`, `conversation.shared`, `conversation.unshared`, `conversation.exported`, `conversation.read_privileged`, `file.uploaded`, `file.downloaded`, `file.deleted`, `file.quarantined` |
| Runs | `run.created_api`, `run.cancelled`, `run.budget_exceeded`, `run.started_on_behalf_of` |
| Tools | `tool_server.created`, `tool_server.updated`, `tool_server.deleted`, `tool_server.version_created`, `tool_server.review_requested`, `tool_server.approved`, `tool_server.rejected`, `tool_server.deprecated`, `tool_server.disabled`, `tool_server.enabled`, `tool.updated`, `tool.disabled`, `tool.enabled`, `tool.called`, `tool.denied` (F), `tool.tested`, `tool_result.injection_suspected`, `data_connection.created`, `data_connection.updated`, `data_connection.deleted` |
| Policies & approvals | `policy.created`, `policy.updated`, `policy.deleted`, `policy.version_created`, `policy.activated`, `policy.disabled`, `policy.simulated`, `approval.requested`, `approval.decided`, `approval.cancelled`, `approval.expired`, `approval.standing_used`, `standing_approval.created`, `standing_approval.revoked` |
| Knowledge | `collection.created`, `collection.updated`, `collection.deleted`, `collection.reindexed`, `source.created`, `source.updated`, `source.deleted`, `source.synced`, `document.added`, `document.deleted`, `document.classified`, `collection.store_migrated` |
| Memory | `memory.created`, `memory.updated`, `memory.deleted`, `memory.extracted`, `memory.approved`, `memory.rejected`, `memory.cleared` |
| Sandboxes | `sandbox_template.created`, `sandbox_template.updated`, `sandbox_template.deleted`, `sandbox.created`, `sandbox.terminated`, `sandbox.egress_denied` (F) |
| Skills | `skill.created`, `skill.updated`, `skill.published`, `skill.archived` |
| Routines | `routine.created`, `routine.updated`, `routine.deleted`, `routine.paused`, `routine.resumed`, `routine.transferred`, `routine.run_requested`, `routine.webhook_secret_rotated` |
| Channels | `channel_integration.created`, `channel_integration.updated`, `channel_integration.deleted`, `channel_identity.linked`, `channel_identity.unlinked` |
| Webhooks & notifications | `webhook.created`, `webhook.updated`, `webhook.deleted`, `webhook.secret_rotated` |
| Usage & quotas | `quota.created`, `quota.updated`, `quota.deleted`, `quota.exceeded` (F) |
| Audit & retention | `audit.verified`, `audit.exported`, `audit.purged`, `retention.swept`, `erasure.completed` |
| Evals | `eval_suite.created`, `eval_suite.updated`, `eval_suite.deleted`, `eval_run.started`, `eval_run.cancelled` |
| Content packs | `pack.installed`, `pack.upgraded`, `pack.uninstalled`, `pack.signature_rejected` (F), `tenant_pack.enabled`, `tenant_pack.disabled` |
| Reviews and SoD | `review_queue.created`, `review_queue.updated`, `review_queue.deleted`, `review_item.created`, `review_item.decided`, `review_item.expired`, `review_item.superseded`, `signoff.recorded`, `sod_constraint.created`, `sod_constraint.updated`, `sod_constraint.deleted`, `sod.violation_blocked` (F) |
| Run records | `run_record.sealed`, `run_record.seal_failed` (F), `run_record.replayed`, `run_record.replay_diverged` |
| Evidence and holds | `evidence.captured`, `evidence.accessed`, `evidence.verified`, `evidence.exported`, `evidence.disposed`, `legal_hold.created`, `legal_hold.released`, `retention_schedule.updated`, `disposition.certified` |
| AI governance | `agent_card.published`, `agent_card.updated`, `ai_incident.created`, `ai_incident.updated`, `ai_governance.exported` |
| Guests | `guest.invited`, `guest.login`, `guest.login_failed` (F), `guest.revoked`, `guest.grant_created`, `guest.grant_revoked`, `guest.access`, `guest.downloaded` |
| Binders | `binder.created`, `binder.built`, `binder.downloaded` |
| GRC pack | `grc.framework.imported`, `grc.control.updated`, `grc.mapping.confirmed`, `grc.mapping.rejected`, `grc.evidence.linked`, `grc.test_result.recorded`, `grc.finding.created`, `grc.finding.closed`, `grc.risk.proposed`, `grc.risk.accepted`, `grc.vendor.created`, `grc.assessment.completed`, `grc.policy.published`, `grc.policy.acknowledged`, `grc.obligation.updated`, `grc.regulatory_change.triaged`, `grc.incident.opened`, `grc.incident.notified`, `grc.campaign.started`, `grc.campaign_item.decided`, `grc.answer.approved`, `grc.pbc.updated`, `grc.entitlement.ingested`, `grc.report.exported`, `grc.entity.updated`, `grc.exception.signed`, `grc.ethics.opened`, `grc.inspection.opened`, `grc.dsar.fulfilled`, `grc.consent.recorded`, `grc.resilience.recorded` |

`audit.event` is **not** an action: it is the outbox topic carrying each audit row to the SIEM webhook.

## 4. Required fields by action family

| Family | `target_type` | Extra fields |
|---|---|---|
| `tool.*`, `approval.*` | `tool_call` / `approval` | `agent_id`, `run_id`, `tool_call_id`, `decision`, `detail.args_hash`, `detail.risk_class`, `detail.policy_reasons` |
| `auth.*` | `user` | `ip`, `user_agent` |
| Settings changes (`*.updated`) | resource | `detail.diff` (field paths with old/new values, secrets excluded) |
| `conversation.read_privileged` | `conversation` | `detail.reason` (required in UI), `detail.support_grant_id?` |
| `run.started_on_behalf_of` | `run` | `actor_type='service_account'`, `on_behalf_of_user_id` |
