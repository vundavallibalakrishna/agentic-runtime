# M20 certification report

**Verdict: certified with conditions.**

The platform signed a user in, stored a DeepInfra API key as a secret, and answered through `Qwen/Qwen3-32B` on the model gateway. The same browser session opened the product and GRC screens in light and dark, at desktop and mobile width. Conditions are the gaps below that were not run, or that the UI cannot perform.

## Environment

| Item | Value |
|---|---|
| Date | 2026-10-28 |
| Start | `make up`, `make migrate`, `alembic -c packs/grc/alembic.ini upgrade head`, `make seed`, `honcho start -f Procfile.dev` |
| Web | `http://localhost:13000` |
| API | `http://127.0.0.1:18000` |
| Model gateway | `http://localhost:18001` |
| Postgres / Valkey / Temporal | host ports 15432 / 16379 / 17233 |
| Login | Dev sign-in as `admin@dev.local` |
| Provider | OpenAI-compatible, base URL `https://api.deepinfra.com/v1/openai` |
| Chat model | `Qwen/Qwen3-32B` |
| Key | Pasted in **Admin → Models**. Stored encrypted. `hasApiKey` is true. The value is not in this report, the screenshots, or the API response. |

Host ports were moved off 5432, 6379, 7233, 8000, 8001 and 8013. An existing compose volume for this project was dropped with `make reset-db` so the dev tenant id matched the seed. Other compose projects were not stopped.

## Scenario results

| Scenario | Result | What happened | Evidence |
|---|---|---|---|
| Sign-in | Pass | Dev admin reaches Chat. | `docs/testing/m20/desktop-light-login.png` |
| Register the model | Pass | Advanced form stores the key, tests the provider, and shows `Sample: pong` in about 1.6s. The key field is empty afterwards. | `docs/testing/m20/desktop-light-models-registered.png` |
| Chat | Pass | Assistant text stored and shown as `pong` for "Reply with exactly the word pong and nothing else." No `fake:` prefix. | `docs/testing/m20/desktop-light-chat-pong.png` |
| A normal question | Pass | "In one sentence, what is a control test?" completed in about 2s with a definition of a control test. | API conversation after the UI run |
| Knowledge upload | Pass | Collection "Visitor policy" accepted `m20-access-policy.txt` and showed it indexed. | `docs/testing/m20/desktop-light-knowledge-uploaded.png` |
| Agent builder | Pass with a note | Draft preview renders and validation reports no blocking errors. The persona repeats the instruction and adds a stock follow-up line. | `docs/testing/m20/desktop-light-builder.png` |
| Tools | Not completed | The default assistant has `max_tool_calls` 0, so a ticket sentence is answered by the model with no tool call. Desk returns "Connect an account to use this tool." | API check during the run |
| Approvals | Not completed | The approvals inbox was empty. No approve or deny was clicked. | `docs/testing/m20/desktop-light-approvals.png` |
| Product screens | Pass as viewed | Chat, agents, tools, connections, knowledge, memory, skills, routines, reviews, runs, models, users, policies, channels, evals, usage, quotas, computers, assurance, health, profile. | `docs/testing/m20/desktop-light-*.png`, `desktop-dark-*`, `mobile-light-*`, `mobile-dark-*` |
| GRC catalogues | Pass as viewed | Frameworks, controls, evidence, tests, findings, and connectors render. Demo catalogues come from the dev pack install. | `docs/testing/m20/desktop-dark-grc.png` and the matching tab shots |
| GRC workflows | Pass as viewed, create not available | Vendors shows Northwind from `install_dev`. Questionnaires, policies, risks, regulatory, incidents, exceptions, and ethics open. There is no create form. | `docs/testing/m20/desktop-dark-grc_workflows_vendors.png` |
| GRC audit | Pass as viewed | Requests, reviews, reports, inspections, privacy, and resilience open on the dev seed. | `docs/testing/m20/desktop-dark-grc_audit.png` and the section shots |
| Light, dark, desktop, mobile | Pass | No clipped primary heading, no unreadable contrast on the sampled screens, empty panels use the shared empty state. | The four prefixes under `docs/testing/m20/` |
| Walkthrough | Pass | Login, model form, chat answer, knowledge upload, builder, then the route sweep. | `docs/testing/m20/walkthrough.webm` |

## Defects fixed

| Defect | Fix | Test |
|---|---|---|
| The gateway always forwarded chat to fake-llm, so an operator's provider was ignored. | `POST /v1/chat/completions` calls a registered non-fake upstream model. The API key is encrypted in the secret store and is not returned. Chat sends that upstream model and a longer timeout. | `services/model_gateway/tests/unit/test_upstream.py`, `libs/ar_domain/tests/unit/test_m20_provider.py` |
| Models admin could only register a fake provider. | Advanced mode selects OpenAI-compatible, base URL, upstream model, and a write-only key, then points `reasoning` at it. | `apps/web/src/components/models/models-admin.test.tsx` |
| `/healthz` flushed the process cache and returned 500 when that flush hit a foreign key. | Probe paths no longer bind or flush. | `services/api/tests/unit/test_m13_memory_mode.py` |

## Model limits (Qwen3-32B)

These are not platform defects.

- Asked "File a ticket: the lobby printer is jammed" on the default assistant, the model replied that it had filed the ticket. No tool call was recorded. The assistant budget also disallows tool calls, so the platform did not correct the claim.
- The builder preview is thin: it echoes the sentence and adds one stock line. The screen itself did not error.
- The one-sentence control-test answer was coherent. No broader quality suite was run.

## Conditions (not certified as done)

- **OQ-54, high.** Workflow and audit screens do not create vendors, risks, policies, questionnaires, incidents, exceptions, ethics cases, PBC requests, or inspections. Demo rows are from `install_dev`.
- **OQ-53, medium.** Breaker, semaphore, alias traffic split, and mid-stream fallback are not on the live chat path. Embeddings and rerank stay on the seeded fake aliases. Knowledge upload indexed the file; this run did not prove semantic retrieval through a real embedding model.
- **OQ-48.** The 24 hour soak, live Slack, live Teams, and a customer IdP were not run.
- **OQ-49 to OQ-52.** GRC HTTP rows stay on the process store. `make migrate` does not upgrade schema `grc`.
- **Approvals.** No approval was granted or rejected.
- **Tool connection.** Desk stops at "Connect an account" until a tickets connection exists. That connection was not created in the browser.

## Layout

Sampled light and dark shots at 1440px and 390px. Sidebar, tables, and GRC tabs stay inside the viewport. The models table uses horizontal scrolling rather than overlapping columns. The Next.js dev badge sits over the corner in `next dev`; it is not part of the production UI. No contrast failure stood out on the sampled dark screens. Empty states use the shared panel.
