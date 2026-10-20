# Spec 15: Routines and triggers (`ar_domain.routines`)

Endpoints served by `api` (including the public inbound webhook endpoint); orchestration by `system-worker` (`RoutineRunWorkflow`, `RoutinePollWorkflow`, queue `ar-system`); the agent work itself is a normal `AgentRunWorkflow` (trigger `routine`) on `ar-runtime`. Owns `routines`, `routine_events` ([schema §13](../04-data/schema.md#13-routines-ar_domainroutines)). Definition: [definition-schema §6](../05-contracts/definition-schema.md#6-routine-kind-routine). PRD: [08-routines](../01-prd/08-routines.md).

## 1. Concept

A routine = **trigger** (schedule or event) + **agent** + **instructions** + **delivery targets** + **budget**, running unattended **as its owner** (or a service account). Every routine run is recorded as a conversation of the owner (`channel='routine'`) so results, tool calls and artifacts are inspectable in the UI.

## 2. Triggers

| Type | Mechanism | Idempotency key |
|---|---|---|
| `schedule` | Temporal Schedule `routine-{routine_id}` (cron + IANA timezone, `jitter_s`, `catchup_window_s`, overlap policy from `concurrency_policy`: skip → `SKIP`, buffer_one → `BUFFER_ONE`, allow → `ALLOW_ALL`) whose action starts `RoutineRunWorkflow` | scheduled fire time (`TemporalScheduledStartTime`) |
| `webhook` | `POST /api/v1/hooks/routines/{token}` (public) | `idempotency_key_path` value, else `X-Idempotency-Key` header, else sha256(body) |
| `channel_event` | `channels` → `api` `POST /internal/v1/channels/events` → matching routines | `{integration_id}:{external_event_id}` |
| `email` | email integration inbound (IMAP poll in `channels`) → same internal endpoint with `event: email` | `Message-ID` |
| `file_arrival` | `knowledge_source` variant: outbox subscriber on `knowledge.document_changed`; `s3` variant: `RoutinePollWorkflow` every 60 s listing the prefix with a watermark | `{bucket}/{key}@{etag}` or `{document_id}@{version_hash}` |
| `db_change` | `RoutinePollWorkflow` every `poll_interval_s` running `poll_query` through `mcp-sql` guard rules with watermark on `updated_at` | `{id}@{updated_at}` |
| `manual` | `POST /api/v1/routines/{routine_id}:run` | request `Idempotency-Key` or random |

Event envelope `EventEnvelope {event_id, source, type, occurred_at, subject?, data (≤ 64 KiB, larger payloads stored as `files(kind='event_payload')`), headers?: {..} (allow-listed)}`. `event_filter` (JMESPath, evaluated with `jmespath` on the envelope) must be truthy to run (else `routine_events.status='filtered'`).

## 3. `RoutineRunWorkflow(routine_id, event_id?)`

Workflow id: `routine-{routine_id}-{event_id}` (event triggers) or Temporal schedule-generated id (schedules). Steps (activities on `ar-system`):

1. `accept_routine_event`: insert `routine_events` (unique `(routine_id, idempotency_key)` → `duplicate` ends the workflow); check routine `status='active'`; check daily cap (`max_runs_per_day`, Valkey counter `ar:routine:{id}:runs:{yyyymmdd}`) → `rate_limited`; check concurrency (`skip` → if an active run exists → `skipped_concurrency`; `buffer_one` → wait for the active run to finish, keeping at most one waiting event; `allow`); check quotas.
2. `prepare_routine_run`: verify the owner is `active` (else routine → `needs_review`, notify tenant admins) and has a valid delegation token ([spec 03 §5](03-secrets-credentials.md#5-delegation-tokens-keycloak-offline-tokens-and-token-exchange)) when tools need `token_exchange` (else `paused` with `owner_reauth_required`); create a conversation (owner, `channel='routine'`, title `"{routine.name} · {local date time}"`), the input message (routine instructions + event rendered as `<event source="..." trust="untrusted">…</event>`), and the run (`trigger='routine'`, `routine_id`, budget = routine budget ∩ tenant caps).
3. Start child workflow `AgentRunWorkflow` (`run-{run_id}`, task queue `ar-runtime`) and await it. The runtime's **delivery phase** (§4) executes inside that run.
4. `complete_routine_event`: `routine_events.status='started'`→ final, `run_id`, update `last_run_at`, `next_run_at` (from the schedule), `consecutive_failures` (reset on success; +1 on failure; at 5 → `paused` with `paused_reason='too_many_failures'` and notification `routine_failed`). Notification `routine_completed` to the owner if `delivery` contains only `conversation` (otherwise the delivery itself is the notification). Outbox `routine.run_completed` (always) and `routine.paused` (when paused automatically).

## 4. Delivery phase (in `AgentRunWorkflow` for `trigger='routine'`)

After the agent's final answer, the runtime constructs one tool call per delivery target (not model-generated) using the built-in `delivery` server tools (all `W2`, never exposed to models, entitled only for `trigger='routine'` runs whose target matches the routine's `delivery` config):

| Target | Tool | Arguments |
|---|---|---|
| `conversation` | none | (the run already lives in the owner's conversation) |
| `slack` | `delivery.slack_post` | `{integration_id, channel, thread_ts?, text: final_markdown, file_ids}` |
| `teams` | `delivery.teams_post` | `{integration_id, channel_id? , conversation_ref?, text, file_ids}` |
| `email` | `delivery.email_send` | `{integration_id?, to, cc, subject (template with {{routine.name}}, {{date}}), body_markdown, file_ids}` |
| `webhook` | `delivery.webhook_post` | `{url, payload: {routine_id, run_id, conversation_id, status, text, files: [{file_id, name, url (presigned 24 h)}]}}` signed with the target secret |
| `file` | none | artifacts only |

They pass through `execute_tool_call` → policy → standing approvals (`pre_approved: true` targets) or an approval for the owner (notification + inline approval in the routine conversation) → `mcp-gateway` executes via `channels` `POST /internal/v1/outbound` (Slack/Teams/email) or HTTP POST through the egress proxy (webhook). Delivery failures mark the run `completed` with a `warning` event and `runs.error = {code: "delivery_failed", ...}` partial info; they count as a routine failure.

## 5. Public API

Permissions: `routines:create` (own routines), `routines:manage_all`. The owner must be able to use the agent (visibility) and the routine runs with the owner's permissions; `run_as='service_account'` requires `routines:manage_all`.

#### GET /api/v1/routines
Query `q`, `status`, `owner=me`, `agent_id`, `trigger_type`. Item `Routine {id, name, description, owner, agent: {id, name}, trigger_type, trigger_summary ("Every Monday 09:00 IST"), status, paused_reason, last_run: {id, status, at}|null, next_run_at, consecutive_failures}`.

#### POST /api/v1/routines
Body `{name, description?, agent_id, agent_version_id?, instructions, trigger: RoutineTrigger, event_filter?, delivery: [DeliveryTarget], budget?, max_runs_per_day?, concurrency_policy?, run_as?, service_account_id?}`. Validation: cron parse (`croniter`), timezone valid, minimum interval 5 min (`AR_ROUTINE_MIN_INTERVAL_S=300`) unless `routines:manage_all`; delivery integrations exist and the owner has a linked channel identity for Slack/Teams DM targets; `pre_approved` targets require `approvals:grant_standing` (creates `standing_approvals` with `expires_at` = 90 days, renewed on routine edit). Webhook triggers return `{webhook_url, webhook_secret}` once in the response (`secret` stored as a secret ref `kind='webhook_secret'`). Creates the Temporal schedule / poller. Response `201 Routine` (+ `webhook` block).

#### GET /api/v1/routines/{routine_id}
Includes full config, standing approvals, schedule info (next 5 fire times).

#### PATCH /api/v1/routines/{routine_id}
Owner or `routines:manage_all`. Updates schedule/poller atomically; changing agent or delivery targets revokes and re-creates standing approvals (requires the permission again).

#### DELETE /api/v1/routines/{routine_id}
Deletes schedule/poller, revokes standing approvals; past runs/conversations remain.

#### POST /api/v1/routines/{routine_id}:run
Owner. Body `{input?: string (appended as event data), test?: false}`. `test=true` performs a run with delivery restricted to `conversation` (dry run). Response `202 {run_id, conversation_id}`.

#### POST /api/v1/routines/{routine_id}:pause
#### POST /api/v1/routines/{routine_id}:resume
Resume clears `consecutive_failures` and `paused_reason`; requires the owner to be active with a valid delegation token (else 409 `invalid_state` reason `owner_reauth_required`).

#### POST /api/v1/routines/{routine_id}:transfer
`routines:manage_all`. Body `{new_owner_user_id}`. Revokes standing approvals; routine → `needs_review` until the new owner resumes it.

#### POST /api/v1/routines/{routine_id}:rotate-webhook-secret
Owner. Returns the new secret once (old one valid for 24 h overlap: both accepted).

#### GET /api/v1/routines/{routine_id}/events
Items `RoutineEvent {id, source, status, received_at, run_id, envelope_preview}`.

#### POST /api/v1/routines:preview-schedule
Body `{cron, timezone}` → `{valid, description, next: [timestamp] (5)}`.

#### POST /api/v1/hooks/routines/{token}
**Public**, no session/CSRF. Headers `X-AR-Signature: t=<unix>,v1=<hex hmac_sha256(secret, t + "." + body)>` (tolerance 300 s). Body ≤ 1 MiB (JSON or form). Lookup via `routines.repository.find_by_webhook_token` (pre-tenant, [rls.md](../04-data/rls.md)). Responses: `202 {event_id}`, `401` bad signature, `404` unknown token, `409` duplicate (with original `event_id`), `429` rate limited (per routine 60/min). Never reveals routine details.

Runs of a routine: `GET /api/v1/runs?routine_id=…` ([spec 06](06-conversations-runs.md)).

## 6. `RoutinePollWorkflow(routine_id)`

Temporal Schedule `routine-poll-{routine_id}` (interval = `poll_interval_s` or 60 s); activity `poll_routine_source` loads the watermark (`trigger_config.watermark` persisted in `routines.trigger_config` under key `_state`), lists changes, and for each change performs §3 step 1 by starting `RoutineRunWorkflow` with a deterministic `event_id` = sha256 of the idempotency key. At most 20 events per poll (rest next poll).

## 7. Limits and config

| Item | Default |
|---|---|
| Routines per user | 50 |
| Routines per tenant | plan `max_routines` (default 500) |
| `AR_ROUTINE_MIN_INTERVAL_S` | `300` |
| Max consecutive failures before pause | 5 |
| Webhook body | 1 MiB |
| Webhook rate per routine | 60/min |

## 8. Metrics

`ar_routine_events_total{source,status}`, `ar_routine_runs_total{status}`, `ar_routine_delivery_total{target,result}`, `ar_routine_schedule_lag_seconds` (fire time vs run start), `ar_routines{status}`.

## 9. Test plan

- Unit: trigger validation, cron description, JMESPath filters, signature verification (timing-safe, tolerance), idempotency key derivation.
- Workflow tests: duplicate event; daily cap; skip/buffer_one/allow concurrency; owner inactive → needs_review; 5 failures → paused.
- Integration: schedule fires (time-skipping test server) → run → Slack delivery via `channels` stub with standing approval (no approval prompt) and without (approval created for owner); webhook end-to-end with signature; delegation token missing → paused with `owner_reauth_required`.
