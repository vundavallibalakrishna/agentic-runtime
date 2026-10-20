# M10 — Routines

Goal: unattended work. Users schedule agent tasks or trigger them from webhooks, channel events, emails, knowledge changes, S3 arrivals and database changes; results are delivered to the owner's conversation, Slack, Teams, email, webhooks or files, with approvals or standing approvals for delivery.

Exit criteria: a weekly routine (cron, `Asia/Kolkata`) runs the agent as its owner and posts to a Slack channel via a standing approval (Slack stubbed until M11); a webhook-triggered routine deduplicates repeated deliveries; five consecutive failures pause the routine and notify the owner.

---

### M10-T01 · Revision 0017 `routines` and routines API
- **Depends on:** M5-T04, M9-T01
- **Areas:** `ar_domain/routines/**`, migration 0017, `ar_api/routers/{routines.py,hooks.py}`
- **Spec:** [spec 15 §1–2, §5, §7](../03-specs/15-routines-triggers.md#5-public-api), [schema §13](../04-data/schema.md#13-routines-ar_domainroutines)
- **Do:** Tables of schema §13; `GET/POST /api/v1/routines`, `GET/PATCH/DELETE /api/v1/routines/{routine_id}`, `POST /api/v1/routines/{routine_id}:run`, `:pause`, `:resume`, `:transfer`, `:rotate-webhook-secret`, `GET /api/v1/routines/{routine_id}/events`, `POST /api/v1/routines:preview-schedule` (croniter next 10 runs in timezone); limits (`AR_ROUTINE_MIN_INTERVAL_S`, plan `max_routines`); owner suspension hook pauses routines; standing approvals for `pre_approved` delivery targets created on save (owner must hold `approvals:grant_standing` or be the approver).
- **Done when:** every endpoint matches spec 15; preview-schedule handles DST-free and DST zones.
- **Tests:** integration per endpoint; schedule preview unit tests.

### M10-T02 · `RoutineRunWorkflow` and Temporal Schedules
- **Depends on:** M10-T01
- **Areas:** `ar_system/workflows/routine_run.py`, `ar_domain/routines/schedules.py`
- **Spec:** [spec 15 §3](../03-specs/15-routines-triggers.md#3-routinerunworkflowroutine_id-event_id), [request-flows §6](../02-architecture/request-flows.md#6-routine-run-with-delivery)
- **Do:** Schedule create/update/pause/delete in sync with routine rows (`routine-{routine_id}`, overlap policy mapping, jitter, catch-up); activities `accept_routine_event`, `prepare_routine_run` (owner + delegation checks → `delegation_expired` pauses with `owner_reauth_required`), child `AgentRunWorkflow` with `trigger='routine'`, `complete_routine_event` (failure counting, auto-pause at 5); `routine.run_completed`, `routine.paused` events and notifications.
- **Done when:** schedule drift between DB and Temporal is repaired by a reconcile activity run hourly.
- **Tests:** Temporal tests (time-skipping weekly schedule, duplicate event, cap reached, delegation expired, auto-pause).

### M10-T03 · Event triggers and polling
- **Depends on:** M10-T02, M7-T04
- **Areas:** `ar_api/routers/hooks.py`, `ar_system/subscribers/routine_triggers.py`, `ar_system/workflows/routine_poll.py`, `ar_api/internal/channels_events.py`
- **Spec:** [spec 15 §2, §6](../03-specs/15-routines-triggers.md#2-triggers)
- **Do:** `POST /api/v1/hooks/routines/{token}` (HMAC signature verification with the routine webhook secret, idempotency key resolution, payload size limits, `files(kind='event_payload')`), `POST /internal/v1/channels/events` matching `channel_event`/`email` routines, `knowledge.document_changed` subscriber for `file_arrival`, `RoutinePollWorkflow` for `s3` and `db_change`; `event_filter` JMESPath evaluation; event envelope passed to the run as untrusted input.
- **Done when:** replaying a webhook with the same idempotency key produces one run.
- **Tests:** integration (signature, dedupe, filter); Temporal poll tests with watermarks.

### M10-T04 · Delivery phase and `delivery.*` tools
- **Depends on:** M10-T02
- **Areas:** `ar_runtime/activities/build_delivery_calls.py`, `ar_runtime/workflows/agent_run.py`, `ar_mcp_gateway/builtins/delivery.py`
- **Spec:** [spec 15 §4](../03-specs/15-routines-triggers.md#4-delivery-phase-in-agentrunworkflow-for-triggerroutine), [internal-apis §8](../05-contracts/internal-apis.md#8-channels-internal-endpoints-base-httpchannels8004)
- **Do:** `build_delivery_calls` after the final answer; `delivery.slack_post`, `delivery.teams_post`, `delivery.email_send`, `delivery.webhook_post` (W2, never offered to models, entitled only for `trigger='routine'`) executed through the normal pipeline (policy → standing approval or owner approval); channel deliveries call `channels` `POST /internal/v1/outbound` (stubbed by a fake channels server until M11-T02); webhook delivery signed; delivery outcomes in `routine_events.detail.deliveries`.
- **Done when:** a delivery without a standing approval waits for the owner's approval and then posts exactly once.
- **Tests:** Temporal tests with fake channels server; webhook signature test.

### M10-T05 · Web: routines
- **Depends on:** M10-T03, M10-T04
- **Areas:** `apps/web/src/app/(app)/routines/**`
- **Spec:** [spec 19 `/routines`](../03-specs/19-web-app.md)
- **Do:** Routines table, editor (agent, instructions, trigger builder with schedule preview, webhook URL + secret reveal/rotate, filters, delivery targets with pre-approval toggle, limits), detail with event/run history, pause/resume/run now/transfer.
- **Done when:** M10 exit scenario configurable through the UI.
- **Tests:** Vitest; Playwright create schedule routine → run now → see delivery; axe.
