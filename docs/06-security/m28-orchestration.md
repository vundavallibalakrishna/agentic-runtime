# M28 orchestration

## Webhook signing

A webhook trigger uses the routine path `POST /api/v1/hooks/routines/{token}`. The signing secret is returned only on create and on rotate. Later reads show the URL and not the secret. The header is `X-AR-Signature: t=<unix>,v1=<hmac-sha256>`. The same body, or the same idempotency key, returns 409 and does not start a second run.

## Approval authority

A human step of kind `approval` cannot be assigned to the person who requested it, and that person cannot answer it. The inbox does not list a person's own approval requests. Tool approvals keep the existing segregation rule: the agent owner cannot approve a call their agent made. A question (not an approval) is answered by the assignee, who may be the person who started the run.

## Budgets

Child tokens and cost roll into the parent run. The child's own limits are the minimum of its definition and the parent's remaining steps, tokens, cost, wall clock, and tool calls. Fan-out is `subagents.maxParallel`, capped at 8. Depth is `subagents.maxDepth`, capped by `AR_MAX_DEPTH` and the column check (0 through 3). A slug already on the agent chain is a cycle. Calling the current agent is allowed only when `allowSelfClone` is true, and it still spends depth and budget.

## Child timeout

`subagents.childTimeoutS` defaults to 45 seconds and is capped at 600. When it elapses, the child run is cancelled and stored as failed with `child_timeout`. It is not retried. The parent receives the error and may continue, recover, or stop. The time spent waiting counts against the parent's wall-clock budget.

## Retries

A model provider error is retried twice, with 0.2s and then 0.4s of backoff, and then the run fails. A duplicate webhook is not a retry; it is ignored.

## Restart

Before a model call, a durable API writes the run as `running`. If that process stops, the next process marks the run failed with `interrupted`. It does not replay the provider call. A run in `waiting_input` or `waiting_approval` stays paused. The checkpoint and the human question are Postgres rows (revision 0029), so an answer after restart resumes the run.

## What was tested

Unit tests cover parallel children, a failed child, depth-limited recursion, a one-second timeout, a human answer, self-approval denial, skip and queue, webhook idempotency, and interrupted runs. The real-model proof is recorded in [m28-checklist](../testing/m28-checklist.md).

## Still process-local

Uploaded file bytes, builder sessions, the local workspace directory under the temp path (the reference is durable; the bytes are not), standing approvals, review queues, rate-limit buckets, and SSE subscribers. See [OQ-59](../open-questions.md).
