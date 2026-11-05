# M35 — Durability, Temporal clock, jobs

Depends on M28, M29, M31 and M34a. This milestone keeps long jobs usable across a process restart, lets a schedule fire from Temporal's clock, bounds the chat cache, and finishes the A2A JSON-RPC methods that were returning `-32601` except gRPC and `tasks/resubscribe`.

Parallel work owns analytics and DuckDB (M34b), the connector catalog (M36) and the browser tool (M37). This milestone does not change those.

## M35-T01 Durability, schedules, cache, A2A and job progress

**Spec:** [OQ-59](../open-questions.md), [OQ-64](../open-questions.md), [OQ-67](../open-questions.md), [OQ-68](../open-questions.md), [a2a](../agent-api/a2a.md).

**Do:**

- Register each cron with a per-fire Temporal workflow id. Prove a fire from a Temporal dev server without calling `:tick`. The time-skipping server cannot create schedules, so the proof uses a one-second interval on the production action. Keep `:tick` when Temporal is not connected. A one-minute cron and a private cluster were not watched.
- Store file bytes and workspace files that fit the cap (8 MB per file, 2 MB per workspace file, 8 MB per workspace) in Postgres revision `0033`. Restore them when the temp directory is gone, including onto the next run after an interrupted one.
- Evict finished chat messages, runs and events past a cap. Keep the conversation stub and any active run. Reload trimmed messages when Postgres is bound.
- A2A `tasks/list` pages with `pageSize` and `pageToken`. Push config set, get, delete and list store a webhook and POST the task when it is saved or canceled. `tasks/resubscribe` and gRPC stay `-32601`.
- OCR, spreadsheet queries and database queries record progress. The chat card shows the fraction. A restart marks a running job interrupted.

**Done when:** the unit tests cover eviction, restore, A2A pagination and push, the Temporal dev server fires the schedule action without `:tick`, and [m35-checklist](../testing/m35-checklist.md) labels the one-minute cron and the private cluster as not watched.

**Tests:** `libs/ar_domain/tests/unit/test_m35_durability.py`, `services/system/tests/unit/test_m10_routine_workflow.py`.

## Out of scope

DuckDB, the connector catalog, browser automation, gRPC, and rate-limit windows that survive a restart.
