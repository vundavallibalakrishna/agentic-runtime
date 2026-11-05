# M35 checklist

Revision `0033` adds `file_blobs`, `workspace_files`, `job_progress` and `a2a_push_configs`. Each has `tenant_id`, row level security and grants.

## What is proven here

| Check | Result |
|---|---|
| File bytes under 8 MB survive dropping the process blob cache | `read_blob` returns the durable copy |
| Workspace file under the cap is readable after the temp directory is deleted | `general.read_file` returns the same text |
| The next run in a conversation can see files from an interrupted run | A workspace job says the files were restored |
| Chat cache drops old messages and keeps an active run | Unit test with a cap of 1 message |
| Trimmed messages reload when a database engine is bound | Fake sync engine returns the row |
| PDF extraction reports each page | Two blank pages call the progress callback `(1, 2)` then `(2, 2)` |
| A running job becomes interrupted on restart | `job.progressed` is audited |
| A2A `tasks/list` | Page size 2, then the next page, and another key sees no tasks |
| A2A push config | Set, get and delete. Cancel POSTs the task with the client token. The token is not in the audit detail |
| `tasks/resubscribe` | JSON-RPC `-32601` |
| Temporal schedule | Dev server (`start_local`) fires the production schedule action with `source=schedule` on a one-second interval. The test does not call `:tick`. The time-skipping server cannot create schedules |
| Schedule workflow id | `routine-fire-{id}-{{.ScheduledTime.Unix}}` |

## Not observed on a private cluster

A one-minute cron (`* * * * *`) was not waited out. A long-running Temporal frontend was not watched. The automated fire uses a one-second interval because the time-skipping test server does not implement `CreateSchedule`. `scripts/m35_schedule_clock.py` prints the operator steps and, when `AR_TEMPORAL_ADDRESS` is set, only lists `routine-*` schedules. It does not create one and it does not call `:tick`.

`POST /api/v1/routines/{routine_id}:tick` remains the in-process fallback when Temporal is not connected.

gRPC and `tasks/resubscribe` are still not implemented.

Bodies over the cap stay on the temp directory only. Builder sessions, standing approvals, review queues, rate-limit buckets and SSE subscribers stay process-local.

## Operator steps for a private Temporal cluster

1. Start Postgres, the API, `ar-system` and `ar-runtime`.
2. Set `AR_TEMPORAL_ADDRESS` to a frontend you control. Compose publishes Temporal on `AR_TEMPORAL_HOST_PORT` (default 7233).
3. Create a schedule with cron `*/1 * * * *` and leave it active.
4. Do not call `:tick`.
5. After the next minute, the routine event source is `schedule` and a run exists.
6. Stop the API while an OCR job is running. Start it again. The job status is `interrupted` and workspace files under the cap are still readable.

## How to test visually

1. `make bootstrap && make dev` (or the compose profiles you already use). Dev login is `admin@dev.local`.
2. Open chat and ask the assistant to OCR a multi-page PDF or query a spreadsheet.
3. The tool card shows `name. N of M` and a progress bar using the existing foreground colour. An interrupted job says the saved files are still available.
4. Open the same conversation after a restart. The jobs list above the transcript shows the last fraction when the conversation payload includes `jobs`.

## Commands

```bash
uv run pytest libs/ar_domain/tests/unit/test_m35_durability.py
uv run pytest services/system/tests/unit/test_m10_routine_workflow.py -k schedule_fires
uv run python scripts/m35_schedule_clock.py
```
