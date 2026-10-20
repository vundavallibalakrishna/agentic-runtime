# Domain events (outbox topics)

Domain services write events to `outbox_events` **in the same transaction** as the state change (`ar_domain.events.service.emit(session, topic, payload)`). `OutboxRelayWorkflow` (system-worker, every 2 s via a long-running loop with `continue_as_new` every 1,000 iterations) reads unpublished rows in order and dispatches them to in-process subscribers. There is no external broker in v1 ([ADR-0010](../02-architecture/adr/ADR-0010-streaming-and-events.md)).

Subscribers:
- **Webhook fan-out**: creates `webhook_deliveries` for `outbound_webhooks` subscribed to *public* topics and starts `WebhookDeliveryWorkflow`.
- **Notifications**: `NotificationFanoutWorkflow` creates `notifications` rows (and Slack/Teams/email DMs when the user enabled them).
- **SIEM streaming** (optional): when a tenant enables `settings.audit.siem`, audit inserts also emit the public topic `audit.event`, delivered through that tenant's outbound webhook ([spec 17 §1.2](../03-specs/17-audit-usage-metering.md#12-siem-streaming)). Bulk exports use `AuditExportWorkflow`.
- **Cache invalidation**: publishes `ar:invalidate:{kind}:{id}` on Valkey pub/sub (agents, tools, policies, model aliases, kill switches) so `mcp-gateway`, `model-gateway` and runtime caches drop entries within 1 s.

Envelope (`ar_contracts.events.DomainEvent`):

```json
{"id":"uuid","topic":"run.completed","tenantId":"uuid","occurredAt":"2026-10-20T04:12:33Z","version":1,"payload":{ }}
```

Webhook bodies use these camelCase names. The outbox columns stay `tenant_id` and `occurred_at`. Payload names in the tables are Python attributes; a public webhook serialises each one with the camelCase alias (`user_id` is `userId`). Internal topics may keep snake_case.

## Topics

| Topic | Public (webhooks) | Payload (`payload` fields) | Emitted by |
|---|---|---|---|
| `tenant.created` | no | `tenant_id, slug, plan_key` | identity |
| `tenant.suspended` | no | `tenant_id, reason` | identity |
| `user.provisioned` | yes | `user_id, email, source` | identity (SCIM/login) |
| `user.deprovisioned` | yes | `user_id` | identity |
| `agent.published` | yes | `agent_id, agent_version_id, version` | agents |
| `agent.disabled` / `agent.enabled` | yes | `agent_id, reason` | agents |
| `tool_server.review_requested` | no | `tool_server_id, tool_server_version_id, reason: new_version\|manifest_drift` | tools |
| `tool_server.review_decided` | no | `tool_server_version_id, decision` | tools |
| `tool.disabled` / `tool.enabled` | yes | `tool_id, qualified_name, reason` | tools |
| `model_alias.updated` | no | `alias, tenant_id` | models |
| `policy.activated` / `policy.disabled` | no | `policy_id, policy_version_id` (triggers OPA bundle rebuild) | policy |
| `skill.published` | no | `skill_id, skill_version_id, version` | skills |
| `run.start_requested` | no (internal) | `run_id` (consumed by `OutboxRelayWorkflow` to start `AgentRunWorkflow` if still `queued` after 5 s) | conversations |
| `run.started` | yes | `run_id, conversation_id, agent_id, trigger, user_id` | runs |
| `run.completed` | yes | `run_id, conversation_id, agent_id, trigger, status, usage, final_message_id` | runs |
| `run.failed` | yes | `run_id, error` | runs |
| `run.cancelled` | yes | `run_id, by` | runs |
| `run.budget_exceeded` | yes | `run_id, limit, usage` | runs |
| `conversation.shared` | no | `conversation_id, principal_type, principal_id` | conversations |
| `feedback.created` | yes | `message_id, run_id, agent_id, rating, reasons` | conversations |
| `approval.requested` | yes | `approval_id, run_id, tool_call_id, qualified_name, approver_user_ids[]` | approvals |
| `approval.decided` | yes | `approval_id, status, decided_by[]` | approvals |
| `routine.run_completed` | yes | `routine_id, run_id, status` | routines |
| `routine.paused` | yes | `routine_id, reason` | routines |
| `knowledge.ingestion_completed` | yes | `ingestion_job_id, source_id, status, stats` | knowledge |
| `document.deleted` | no | `document_id, collection_id` | knowledge |
| `knowledge.document_changed` | no | `document_id, collection_id, source_id, version_hash, change: created\|updated` (routine `file_arrival` triggers) | knowledge |
| `memory.fact_proposed` | no | `fact_id, scope, agent_id` (agent-scope review) | memory |
| `file.ready` | yes | `file_id, kind, conversation_id, run_id, status: ready\|quarantined` (emitted when `FileProcessWorkflow` finishes) | files |
| `quota.warning` / `quota.exceeded` | yes | `quota_id, metric, used, limit` | usage |
| `erasure.completed` | no | `user_id, request_id` | identity |
| `audit.event` | yes (only when SIEM streaming is enabled) | full `AuditEvent` | audit |
| `eval.completed` | yes | `eval_run_id, suite_id, agent_version_id, summary` | evals |
| `channel_integration.updated` | no | `integration_id` (cache invalidation for `channels`) | channels |

Public webhook deliveries are signed: header `X-AR-Signature: t=<unix>,v1=<hex HMAC-SHA256(secret, t + "." + body)>`, `X-AR-Event-Id`, `X-AR-Topic`. Retries with exponential backoff (10 s → 6 h, 12 attempts), then `dead`. Receivers must respond 2xx within 10 s and dedupe on `X-AR-Event-Id`.

### Topics added for records and sign-off

| Topic | Public (webhooks) | Payload (`payload` fields) | Emitted by |
|---|---|---|---|
| `review_item.requested` | yes | `review_item_id, queue_id, level, signer_user_ids[]` | approvals |
| `review_item.decided` | yes | `review_item_id, status, level` | approvals |
| `evidence.captured` | yes | `evidence_item_id, content_sha256, source_system` | records |
| `legal_hold.created` / `legal_hold.released` | no | `hold_id, matter, member_count` | records |
| `run_record.sealed` | no | `run_record_id, run_id` | runs |
| `binder.ready` | yes | `binder_id` | records |
| `agent_card.published` | yes | `agent_id, agent_version_id, card_hash` | agents |
| `ai_incident.opened` | yes | `incident_id, agent_id, severity` | agents |
| `pack.installed` | no | `pack_id, version` | agents |
| `run_record.replay_diverged` | yes | `run_record_id, replay_id, run_id` | runs |
