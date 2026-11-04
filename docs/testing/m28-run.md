# M28 run guide

Use ports that are not already taken. Do not stop Postgres, Temporal, Redis, or the apps on 8000, 8001, and 8013.

```bash
cp .env.example .env
# Point AR_PORT, AR_WEB_HOST_PORT and AR_PG_HOST_PORT at a free block.
make ports-check
make up
make migrate
make seed
honcho start -f Procfile.dev
```


Sign in with dev sign-in as `admin@dev.local`.

## Agents

Open an agent. Under Can call agents, select the agents it may use. Turn on Can ask a person when a run should be allowed to pause. Save the draft and publish.

## Runs

Send a message that asks the parent to call the children. Open Runs. The row shows status, duration, and cost. Open the run. The tree lists each child. Open a step to read it. Refresh while the status is running; the page keeps updating.

## Schedules

Open Schedules. Create a cron schedule and set the time zone. If a run is still going, leave Skip selected. Run now starts one run. Pause and enable it. Create a webhook trigger, copy the secret from the banner (it is not shown again), and POST the same signed body twice. The second response is 409 and there is still one run. A skipped fire says the previous run is still going.

## Inbox

When a run asks a question, open Inbox. Send one of the options. The run leaves the inbox and the trace contains the answer. An approval is not offered to the person who requested it.

## Restart

Stop the API process and start it again. A run that was `running` is failed with `interrupted`. A run that was waiting for an answer is still waiting. Answer it; the run continues.
