# M21 checklist

## Parked pack

- [x] `AR_GRC_PACK_ENABLED` defaults to false in `.env.example`, settings and Helm values.
- [x] A dev sign-in has no GRC navigation item.
- [x] `/grc` renders the not-found page.
- [x] `packs/grc` is still in the tree and its unit tests pass without the flag.

## Workspace

- [x] Sign-in lands on Chat.
- [x] The composer lists agents and model aliases.
- [x] New agent → "Create and use" publishes an agent and opens chat.
- [x] The agent editor saves a name, instructions, model, tools, skills and limits.
- [x] Admin → Models can store an OpenAI-compatible endpoint. The key field is empty after save.

## Agent loop

- [x] The default assistant definition has `max_tool_calls` 8 and the control tools.
- [x] A real-provider turn emits `plan.updated`, `tool_call.failed`, `tool_call.completed`. The process audit log records `run.planned`, `tool.called`, `run.retried` and `run.checked`.
- [x] `control.propose_change` pauses on `waiting_approval`.

## Real model (Qwen/Qwen3-32B)

Recorded on 2026-10-28 against `https://api.deepinfra.com/v1/openai`. The key stayed in the environment. It was not printed, written to a file, or returned by the API (`hasApiKey` true, no key field).

| Check | Result | Evidence |
|---|---|---|
| Provider test | Pass | `ok` true, reply contained `pong`, about 1s |
| Chat answer | Pass | Run summary `Checkpoint saved: ready`. No `fake:` prefix |
| Plan, failed tool call, retry | Pass | `run_events` include `plan.updated`, `tool_call.failed`, `tool_call.started`, `tool_call.completed` |
| Approval | Pass | `control.propose_change` paused `waiting_approval`. A different person from the agent owner approved. Summary `Change saved.` Events include `tool_call.approval_required` and `tool_call.approval_resolved` |
| Agent used for that chat | Pass | Created through the API on the isolated database, instructions plus the control tools, then used in the two runs above. The browser form created "Desk note" on the fake-model walkthrough |

## Screens

Light and dark, desktop and mobile, under `docs/testing/m21/`. Walkthrough: `docs/testing/m21/walkthrough.webm`.
