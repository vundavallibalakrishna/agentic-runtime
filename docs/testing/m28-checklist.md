# M28 checklist

Proof date: 2026-11-04. Chat model: Qwen/Qwen3-32B through DeepInfra (`https://api.deepinfra.com/v1/openai`). The provider key was read from `AR_CERT_LLM_API_KEY` and is not in this file. The API listened on `18128`. Postgres was a private pgvector container on `55432`. Ports 5432, 8000, 8001 and 8013 were not used.

## Real model

- [x] (a) Parent `lead1793804130` called `red1793804130` and `blue1793804130` in parallel. The parent finished `RED and BLUE.` The children finished `RED` and `BLUE`, both `completed`.
- [x] (b) The parent finished `RECOVERED because the child failed.` The slow child was limited by `childTimeoutS` of 1 second.
- [x] (c) A self-calling agent stopped with `budget_exceeded`: "Stopped because the max cost micros limit was reached."
- [x] (d) Schedule tick produced a run whose summary was `PING`. A signed webhook returned 202 and the run summary was `HOOK`. The same body sent again returned 409.
- [x] (e) A run paused at `waiting_input`. The inbox answer `blue` resumed it. The summary was `blue`.
- [x] (f) Run `01a1a70f-039e-7666-b450-ec592705b3d1` was `running` when the API process was killed. After restart it was `failed` with code `interrupted`: "The API restarted while this run was working. It was marked failed and was not resumed."

## Durability

- [x] Tool calls, approvals, policies, sandbox rows and human questions are flushed by `save_runtime_rows` and loaded again. A new process binds to Postgres and reconciles `running` rows.

## Screens

Playwright captures schedules, inbox, runs and the agent editor in light and dark at desktop and mobile widths. Walkthrough: `docs/testing/m28/walkthrough.webm`.

## Still process-local

Uploaded file bytes, builder sessions, the temp workspace directory, standing approvals, review queues, rate-limit buckets and SSE subscribers. See OQ-59.
