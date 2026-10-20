# PRD 08 — Routines

Routines run an agent unattended on a schedule or in response to events and deliver the result to a conversation, Slack, Teams, email, a webhook or files. Spec: [spec 15](../03-specs/15-routines-triggers.md), [definition-schema §6](../05-contracts/definition-schema.md#6-routine-kind-routine). Plan: [M10](../09-plan/M10-routines.md).

### US-RTN-01 · Schedule a recurring task (P0)
As a **member**, I want to ask an agent to do something every Monday at 9:00 (e.g. "summarise last week's incidents") so that I get it without asking.
- `POST /api/v1/routines` with agent, instructions, `trigger.type=schedule` (5-field cron, IANA timezone, jitter, catch-up window); `POST /api/v1/routines:preview-schedule` shows the next 5 fire times in my timezone; interval below `AR_ROUTINE_MIN_INTERVAL_S` is rejected.
- Runs are Temporal Schedules firing `RoutineRunWorkflow`; each run is recorded as a conversation of the owner.
- Spec: spec 15 §2–3, §5. Plan: M10-T01, M10-T02, M10-T05.

### US-RTN-02 · Trigger from events (P0 webhook/manual; P1 others)
As a **builder**, I want routines triggered by a webhook, a Slack/Teams message or mention, an email, a new file, or a database change.
- Webhook: `POST /api/v1/hooks/routines/{token}` verified by HMAC secret (shown once, rotatable), idempotent by key; `event_filter` (JMESPath) decides whether to run.
- Channel, email, file-arrival and db-change triggers per `RoutineTrigger` variants; polling triggers use `RoutinePollWorkflow` with `poll_interval_s ≥ 60`.
- Spec: spec 15 §2, §6. Plan: M10-T03.

### US-RTN-03 · Deliver results where I work (P0)
As a **member**, I want the routine's output posted to a Slack channel, Teams channel, email, webhook or as files.
- Delivery targets per spec; delivery uses `delivery.*` tools in the delivery phase; with `pre_approved: true` (owner holds `approvals:grant_standing`) a standing approval scoped to exactly that target is created; otherwise each delivery is approval-gated to the owner.
- Spec: spec 15 §4, [spec 09](../03-specs/09-policy-approvals.md). Plan: M10-T04.

### US-RTN-04 · Safe unattended execution (P0)
As a **tenant admin**, I want unattended runs to be bounded and safe.
- Each routine has a budget, `max_runs_per_day` and `concurrency_policy` (`skip`, `buffer_one`, `allow`); W2/W3 actions still require approval (the routine owner is the approver for W2 by default); runs execute as the owner (or a service account with `run_as: service_account`).
- If the owner is no longer active the routine goes to `needs_review` and tenant admins are notified; a missing delegation token pauses it with `owner_reauth_required`; 5 consecutive failures pause it with `too_many_failures` (outbox `routine.paused`, notification `routine_failed`).
- Spec: spec 15 §3, §7. Plan: M10-T02.

### US-RTN-05 · Manage my routines (P0)
As a **member**, I want to see, edit, pause, resume, run now, and delete my routines and see their history.
- List with next run, last status; `:run`, `:pause`, `:resume`; history from `GET /api/v1/routines/{routine_id}/events` linked to run conversations.
- Spec: spec 15 §5. Plan: M10-T01, M10-T05.

### US-RTN-06 · Transfer ownership (P1)
As a **tenant admin**, I want to transfer routines when an employee leaves.
- `POST /api/v1/routines/{routine_id}:transfer` to another user (who must be able to use the agent); erasure of a user is refused while they own active routines unless transferred or deleted.
- Spec: spec 15 §5, [data-protection §4](../06-security/data-protection.md#4-erasure-completeness). Plan: M10-T01, M14-T02.

### US-RTN-07 · Turn a chat request into a routine (P1)
As a **member**, I want to turn a message I sent into a routine without retyping it.
- A **Make this a routine** action on my message opens the routine form prefilled with the conversation's agent and the message text as instructions; nothing is created until I save (`POST /api/v1/routines`).
- Spec: spec 15 §5, [spec 19 §3](../03-specs/19-web-app.md#3-pages). Plan: M10-T05.
