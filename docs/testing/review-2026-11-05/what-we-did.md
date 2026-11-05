# What we did on 5 Nov 2026, and why

A one-page note for the owner. The long versions are the
[review and remediation plan](review-and-remediation-plan.md) and the [engineering handover](handover.md).

## Why we started

You asked for an honest end-to-end review before testing begins: is the platform truly agentic, will it
scale, does it capture cost and metrics everywhere, and is it free of hard-coding. The review read the code
against the specs rather than trusting the milestone log.

## What the review found

- **Agentic: real but thinner than the plan says.** One genuine tool-calling loop, real code/shell/file/fetch/
  HTTP tools, MCP and A2A exposure, approvals with separation of duties, documents and knowledge with
  citations. Around that core, the builder never called a model, evals never ran the agent, memory
  embeddings and tool search were fake vectors, the browser tool was an HTTP fetch, and keyword-scripted
  replies ran ahead of the real loop.
- **Scalable: no.** All product state lives in one in-process store written behind to Postgres, only the
  `dev` tenant is loaded, sessions and rate limits are per process, streaming across processes polls
  Postgres, a run is one five-minute Temporal activity, the sandbox is a host subprocess, and the Helm chart
  could not start a pod because the image needed an env var the chart never set.
- **Metrics and cost: not usable.** Usage was never written to the database, "cost" was the output-token
  count, prices were never applied, and most dashboards sat on placeholder metrics that always read zero.
- **Generic: mostly.** No customer names in code and the industry pack really is gone, but the assurance desk
  (evidence, holds, binders, AI register) was in core with no off switch, a Qwen3 name check lived in six
  places, and two settings reads leaked across tenants.

## What we changed (PR 49, branch `hardening/m32-remediation`)

| Change | Why |
|---|---|
| Settings are read for the calling tenant only | One tenant could switch off PII redaction for every tenant |
| Approvals no longer deadlock on a fresh seed | The owner could not approve and nobody else was eligible |
| No "fake:" echo outside dev; gateway returns 502 | A misconfigured alias silently answered with the prompt |
| Scripted replies and keyword tool triggers run only in dev/ci | They hijacked real agents in production |
| The builder drafts with the real model, repairs once, scripted last | Principle 2 promised a model-backed builder |
| Cost per model call from the model's prices; usage persisted and reloaded | "Where is the money going" had no answer |
| Prices and request options on the model row and API | Removes the Qwen3 name hack; cost needs prices |
| Assurance desk behind a tenant flag, off by default | Principle 3: no industry residue in core without a switch |
| Helm sets the app module and runs workers by console script | Pods either crashed or never polled Temporal |
| Review, handover, screenshots, open-question decisions OQ-78 to OQ-85 | So the next person starts from facts |

Verified on a live stack with Qwen3-32B: a five-tool-call turn, a costed turn (237 micros), the builder
producing a questionnaire agent, and 71 screenshots. Unit suite 764 passed; the four local failures also fail
on `main` on this laptop and are environmental.

## What we deliberately did not do yet

The expensive part is still ahead and is written up as Phases 2 to 4: retiring the in-memory store for the
repository layer, Valkey-backed sessions and streaming, one Temporal activity per step, real sandbox
isolation, evals that run the agent, the metrics catalogue and the analytics screens. Four decisions are
yours: assurance as flag or pack, the Phase 2 approach, the second model provider, and whether the MCP
gateway service stays.

## Things to know when you test

- Register prices with the model (Models → Advanced) or cost stays 0 by design.
- The chat pane stops showing tool progress after about 15 seconds of silence; the run trace page has it all.
- The default 16k token budget stops a six-step turn; raise it on the agent for long tool runs.
- Run `make seed` once on an existing database so the dev tenant gets the assurance flag.
