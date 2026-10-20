# Spec 20: Domain events, notifications and outbound webhooks (`ar_domain.events`)

Endpoints served by `api`; relay and fan-out on `system-worker` (`OutboxRelayWorkflow`, `NotificationFanoutWorkflow`, `WebhookDeliveryWorkflow`, queue `ar-system`). Owns `outbox_events`, `outbound_webhooks`, `webhook_deliveries`, `notifications`, `idempotency_keys` ([schema §17](../04-data/schema.md#17-events-webhooks-notifications-idempotency-ar_domainevents)). Topic catalogue and envelope: [domain-events.md](../05-contracts/domain-events.md). Decision: [ADR-0010](../02-architecture/adr/ADR-0010-streaming-and-events.md).

## 1. Outbox

- `events.service.emit(session, topic, payload, tenant_id)` inserts into `outbox_events` in the caller's transaction. Payload ≤ 64 KiB (larger data referenced by id).
- `OutboxRelayWorkflow` (singleton, id `outbox-relay`, started by the `migrate` Job's post-step and by `system-worker` startup with `WorkflowIDConflictPolicy.USE_EXISTING`): loop: activity `relay_outbox_batch` selects up to 500 unpublished rows `ORDER BY created_at, id FOR UPDATE SKIP LOCKED` (as `ar_platform`), dispatches each to subscribers (below), sets `published_at`; sleeps 1 s when the batch was empty (`workflow.sleep`), `continue_as_new` every 1,000 iterations. Throughput target 2,000 events/s.
- Dispatch is at-least-once; subscribers are idempotent (keys below). A subscriber failure increments `attempts` and leaves the row unpublished for retry (max 20 attempts then logged as `dead` in `payload._relay_error` and published to stop blocking; alert `ARQueueDepthOutbox`).

### 1.1 Subscribers (in `ar_system.subscribers`)

| Subscriber | Topics | Action | Idempotency |
|---|---|---|---|
| `start_run` | `run.start_requested` | if run still `queued` after 5 s → `start_workflow(run-{id})` | workflow id |
| `webhooks` | all public topics | for each active `outbound_webhooks` of the tenant subscribed to the topic → insert `webhook_deliveries` + start `WebhookDeliveryWorkflow` (`whd-{delivery_id}`) | unique `(webhook_id, outbox_event_id)` |
| `notifications` | `approval.requested`, `approval.decided`, `routine.paused`, `routine.run_completed`, `tool_server.review_requested`, `tool_server.review_decided`, `quota.warning`, `knowledge.ingestion_completed` (failed only), `conversation.shared`, `file.ready` (quarantined only), `memory.fact_proposed`, `eval.completed`, `erasure.completed`, `run.completed` (only when `runs.notify_on_complete`) | start `NotificationFanoutWorkflow` (`notify-{outbox_event_id}`) | workflow id |
| `memory_extraction` | `run.completed` | start `MemoryExtractionWorkflow` ([spec 11](11-memory.md)) | `memx-{run_id}` |
| `routine_triggers` | `knowledge.document_changed` | match `file_arrival` routines → start `RoutineRunWorkflow` | routine event idempotency key |
| `opa_bundle` | `policy.activated`, `policy.disabled` | rebuild bundle cache in Valkey `ar:opa:bundle` | revision hash |
| `cache_invalidation` | `agent.*`, `tool.*`, `tool_server.*`, `model_alias.updated`, `policy.*`, `channel_integration.updated` | `PUBLISH ar:invalidate:{kind}:{id}` | n/a |
| `api_callbacks` | `run.completed`, `run.failed`, `run.cancelled`, `run.budget_exceeded` | if `runs.callback_url` is set (from `POST /api/v1/runs`) → `webhook_deliveries` row with `webhook_id = NULL`, `target_url = callback_url`, signed with the tenant run-callback secret (§3.2), delivered by `WebhookDeliveryWorkflow` | unique `(outbox_event_id, target_url)` |

Kill switches and other latency-critical invalidations also publish directly (not only via the outbox) for < 1 s propagation.

## 2. Notifications

### 2.1 `NotificationFanoutWorkflow(outbox_event_id)`
1. `resolve_recipients` per topic (e.g. eligible approvers for `approval.requested`, routine owner for routine events, tool owners/reviewers, tenant admins for quota warnings).
2. `create_notifications`: rows in `notifications` (kind mapping in §2.3), then `PUBLISH ar:notif:{user_id}` for live SSE.
3. `deliver_external` per recipient according to `users.settings.notifications` (`email`, `slack`, `teams` booleans; defaults: approvals → all enabled channels; others → in-app + email):
   - email: SMTP via `AR_SMTP_*` (platform mailer, Jinja2 templates in `ar_system/templates/email/*.html.j2` with inline CSS), plain-text alternative, `List-Unsubscribe` link to `/settings/notifications`.
   - Slack/Teams DM: `channels` `POST /internal/v1/notify` (requires a `channel_identities` link; approval notifications include action buttons).
4. Approval reminders: child timer at 50 % of TTL sends a reminder if still pending.

### 2.2 API
#### GET /api/v1/notifications
Caller's notifications. Query `unread=true`, cursor. Item `Notification {id, kind, title, body, link, data, read_at, created_at}`. Header `X-Unread-Count`.
#### POST /api/v1/notifications/{notification_id}:read
#### POST /api/v1/notifications:read-all
#### GET /api/v1/notifications/events
SSE; events `notification.created {Notification}` and `notification.count {unread}`; backed by Valkey pub/sub `ar:notif:{user_id}`; heartbeat every 15 s.

### 2.3 Kind mapping

| Topic | Notification kind | Link |
|---|---|---|
| `approval.requested` | `approval_requested` | `/approvals/{approval_id}` |
| `approval.decided` | `approval_decided` | `/chat/{conversation_id}` |
| `routine.paused` | `routine_paused` | `/routines/{routine_id}` |
| `routine.run_completed` (failed) | `routine_failed` | `/runs/{run_id}` |
| `routine.run_completed` (succeeded, conversation-only delivery) | `routine_completed` | `/chat/{conversation_id}` |
| `tool_server.review_requested` | `tool_review_requested` | `/tools/{tool_server_id}` |
| `tool_server.review_decided` | `tool_review_decided` | `/tools/{tool_server_id}` |
| `quota.warning` | `quota_warning` | `/admin/quotas` |
| `knowledge.ingestion_completed` (failed/partially) | `ingestion_failed` | `/knowledge/{collection_id}` |
| `conversation.shared` | `conversation_shared` | `/chat/{conversation_id}` |
| `file.ready` (quarantined) | `file_quarantined` | `/files` |
| `memory.fact_proposed` | `memory_review_requested` | `/agents/{agent_id}/edit?tab=memory` |
| `eval.completed` | `eval_completed` | `/agents/{agent_id}/evals?run={eval_run_id}` |
| export completion (`AuditExportWorkflow`, `ErasureWorkflow` export mode) | `export_ready` | `/files` |
| credential refresh failure (from `mcp-gateway`, direct `notifications.service.create`) | `credential_required` | `/connections?provider={slug}` |
| platform/system notices | `system` | as provided |
| run completion for long background API runs (opt-in `notify: true` on `POST /api/v1/runs`) | `run_completed` | `/runs/{run_id}` |

## 3. Outbound webhooks

Permission `webhooks:manage`.

#### GET /api/v1/webhooks
Item `Webhook {id, name, url, topics, status, created_at, last_delivery: {status, at, status_code}|null}`.
#### POST /api/v1/webhooks
Body `{name, url (https; SSRF guard: resolved IP not in `AR_EGRESS_DENY_CIDRS` unless single-tenant `AR_WEBHOOK_ALLOW_PRIVATE=true`), topics: [public topic] (≥ 1)}`. Generates the signing secret (stored as secret ref `kind='webhook_secret'`) and returns it **once** in `secret`.
#### GET /api/v1/webhooks/{webhook_id}
#### PATCH /api/v1/webhooks/{webhook_id}
`{name?, url?, topics?, status?: active|disabled}`.
#### DELETE /api/v1/webhooks/{webhook_id}
#### POST /api/v1/webhooks/{webhook_id}:rotate-secret
New secret returned once; old accepted by signature verification on the receiver side during their rollover (both signatures sent as `v1=` entries for 24 h).
#### POST /api/v1/webhooks/{webhook_id}:test
Sends a `webhook.test` event synchronously; returns `{status_code, latency_ms, error?}`.
#### GET /api/v1/webhooks/{webhook_id}/deliveries
Items `{id, topic, status, attempts, last_status_code, last_error, created_at, next_attempt_at}`.
#### POST /api/v1/webhooks/{webhook_id}/deliveries/{delivery_id}:redeliver

### 3.1 Run callback secret

`POST /api/v1/runs` callbacks are signed with a per-tenant secret (secret ref name `__run_callback_secret__`, created by `TenantProvisioningWorkflow`).

#### POST /api/v1/tenant/run-callback-secret:rotate
`tenant:manage`. Returns the new secret once; the previous secret keeps signing as a second `v1=` entry for 24 h. Step-up required for session principals ([authn-authz §5](../06-security/authn-authz.md#5-step-up-authentication)).

### 3.2 `WebhookDeliveryWorkflow(delivery_id)`
POST JSON envelope with headers (`X-AR-Signature`, `X-AR-Event-Id`, `X-AR-Topic`, `User-Agent: agentic-runtime-webhooks/1`), timeout 10 s, via the egress proxy; 2xx = success; 410 → disable webhook; other failures retry with backoff 10 s, 30 s, 1 m, 5 m, 15 m, 30 m, 1 h, 2 h, 4 h, 6 h, 6 h, 6 h (12 attempts) then `dead`; 3 consecutive `dead` deliveries → webhook `status='failing'` + notification to its creator.

## 4. Idempotency keys (used by `api` middleware)

`Idempotency-Key` header on POST/PATCH/DELETE: key (≤ 255 chars) scoped to `(tenant_id, principal_id)`; first request stores `request_hash` (sha256 of method + path + body) and, on completion, `status_code` + `response_body` (≤ 1 MiB; larger responses store only status). Replays with the same hash return the stored response with header `Idempotent-Replayed: true`; different hash → 409 `idempotency_key_reused`; concurrent in-flight duplicate → 409 `conflict`. Expiry 24 h (swept by retention).

## 5. Configuration

| Variable | Default |
|---|---|
| `AR_SMTP_HOST` / `AR_SMTP_PORT` | `localhost` / `1025` (Mailpit in dev) |
| `AR_SMTP_USERNAME` / `AR_SMTP_PASSWORD` | |
| `AR_SMTP_FROM` | `Agentic Runtime <no-reply@localhost>` |
| `AR_SMTP_STARTTLS` | `false` (dev) |
| `AR_OUTBOX_BATCH_SIZE` | `500` |
| `AR_WEBHOOK_ALLOW_PRIVATE` | `false` |

## 6. Metrics

`ar_outbox_lag_seconds`, `ar_outbox_relayed_total{topic}`, `ar_outbox_subscriber_errors_total{subscriber}`, `ar_notifications_created_total{kind}`, `ar_notifications_delivered_total{channel,result}`, `ar_webhook_deliveries_total{result}`, `ar_webhook_delivery_seconds`.

## 7. Test plan

- Unit: recipient resolution per topic, kind mapping, signature generation (vectors), backoff schedule.
- Integration: outbox row committed with business change and rolled back with it; relay at-least-once with idempotent subscribers (kill worker mid-batch); webhook delivery to a local receiver with retries and `dead`; SSE notification arrives < 1 s after an approval request; email via Mailpit API assertions; idempotency middleware replay/conflict cases.
