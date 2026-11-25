# Known differences

Where the product does not yet do what an older document or the contract says. These
notes describe what it does today.

| What | Today |
|---|---|
| The callback for a run started with `callbackUrl` | Carries `{"runId", "status"}` only. Fetch the reply with `GET /v1/agents/<slug>/runs/$RUN_ID`. |
| Citations on the event stream | `citation.added` is sent for attached documents, not for knowledge bases. Read citations from `content` on the reply. |
| `message.completed` on the event stream | Carries `messageId`, `text` and `answeredModel`, not the content parts. |
| Stream event names | The stream sends the run's events (`message.delta`, …) and a final `done`. There is no `delta` event. |
| `"stream": true` on `/v1` | The events are sent after the turn has finished, not while it runs. |
| `wait` on `POST /api/v1/runs` | Accepted and not used. |
| A citation's `sourceKind` | Can be `document`, with `anchor`, `page` and `fileId`, which the published schema does not list. |
| Rate limits on service-account keys | None of their own; the workspace's limits apply. Agent keys have a per-key rate and monthly quota. |
| "Last used" on a service-account key | Not recorded yet; it shows as never used. |
