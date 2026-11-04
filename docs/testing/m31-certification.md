# M31 certification

Date: 2026-11-04. Model: `Qwen/Qwen3-32B` through DeepInfra (`https://api.deepinfra.com/v1/openai`). Embeddings: `BAAI/bge-m3` on the same base URL. The provider key was read from `AR_CERT_LLM_API_KEY` at runtime. This file does not contain it. Presence check: `present`.

The web UI for every browser step was `next build` then `next start` on port **18132**, proxying to the API on **18131**. Postgres, Valkey, and Temporal on 5432, 6379, and 7233 were already this project's compose services and were left running. Ports 3000, 8000, 8001, 8012, and 8013 were already this project's other API, gateway, workers, and web, so they were not reused. A private Temporal for this pass listened on **17233** and was not required for the in-process turns.

Database `m31_fresh` was created empty and migrated to `0031`. `information_schema` count for schema `grc` was 0. `make seed` then wrote 1 tenant, 4 users, and the built-in assistants (`assistant`, `helpdesk`, `builder`). Chat conversations after seed and before the pass: 0.

`m31_populated` is a dump of the already-migrated `agentic_runtime` database. `alembic upgrade head` on it was a no-op at `0031` and left 1 tenant and 5 agents.

## Commands

```bash
[ -n "$AR_CERT_LLM_API_KEY" ] && echo present || echo absent
docker exec agentic-runtime-postgres-1 psql -U ar_owner -d postgres -c "CREATE DATABASE m31_fresh OWNER ar_owner;"
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5432/m31_fresh' \
  uv run alembic -c libs/ar_domain/alembic.ini upgrade head
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5432/m31_fresh' \
  uv run python scripts/seed.py
# API and gateway. AR_WEB_HOST_PORT must match the browser origin or CSRF fails.
AR_DATABASE_URL='postgresql+asyncpg://ar_app:ar_app@127.0.0.1:5432/m31_fresh' \
  AR_PORT=18131 AR_TEMPORAL_ADDRESS=127.0.0.1:1 \
  AR_MODEL_GATEWAY_URL=http://127.0.0.1:18101 \
  AR_PUBLIC_URL=http://127.0.0.1:18132 AR_WEB_HOST_PORT=18132 \
  uv run ar-api
# from apps/web
API_PROXY_URL=http://127.0.0.1:18131 AR_NEXT_DIST=.next-m31 pnpm exec next build
API_PROXY_URL=http://127.0.0.1:18131 AR_NEXT_DIST=.next-m31 pnpm exec next start --port 18132
```

Live checks: `uv run python scripts/m31_proof.py` and `uv run python scripts/m31_followup.py`. UI: `node scripts/m31_ui.cjs` against `http://127.0.0.1:18132`.

## 1. First run and identity

`POST /api/v1/signup` returned **404** `signup is disabled`. Sign-in used dev login as `admin@dev.local` on the production page (the same cookie the Keycloak session uses). Conversation count before any certification message: **0**. OpenAPI paths containing `grc`: **0**.

The shell has no industry entry. `/grc` and `/grc/audit` render **Page not found** and "This page is no longer part of the product." Chat invites the first step: "What can we work on?" Seeded assistants are listed; that is the identity bootstrap, not sample threads.

Screens: `docs/testing/m31/flow-chat-empty.png`, `docs/testing/m31/flow-retired.png`, `docs/testing/m31/desktop-light-chat.png`, `docs/testing/m31/desktop-dark-chat.png`.

## 2. Model setup

The provider **DeepInfra M31** (`openai_compatible`, base URL `https://api.deepinfra.com/v1/openai`) was registered through the API and again through the Models form (**Customer DeepInfra**). `POST ...:test` returned `ok: true`, reply `pong`, latency **410 ms** (API) and **430 ms** (UI sample).

`GET` list body has `hasApiKey: true` and no `apiKey` field. `encrypted_secrets` had 1 row and **0** plaintext hits for the key bytes. The UI row says **Key stored**. The API key input is empty after save. Screenshot: `docs/testing/m31/flow-model-stored.png`.

## 3. Builder and a multi-step run

The builder form created **Certification clerk** and opened chat (`docs/testing/m31/flow-builder-chat.png`).

A published repair agent was told to run `print(1/0)` and then `print(17*19)`. Run `01a1a7fe-b74b-70e2-8ef0-b1a67e9205be` completed. Summary: `323`. Tool trace:

| Call | Status | Result |
|---|---|---|
| `general.code` `print(1/0)` | failed | `ZeroDivisionError: division by zero` (950 ms) |
| `general.code` `print(17*19)` | succeeded | `323` (1349 ms) |

## 4. General tools

Same-run trace `01a1a802-1c0f-7228-9ce1-6d335e5ca0fe`. Summary quoted the file and the page title **Example Domain**.

| Tool | Result |
|---|---|
| `general.write_file` `/workspace/note.txt` content `workspace note alpha` | succeeded, `Wrote /workspace/note.txt` |
| `general.list_files` `/workspace` | `/workspace/note.txt` |
| `general.read_file` | `workspace note alpha` |
| `general.shell` `printf 'shell-ok\n'` | `exit 0` / `shell-ok` |
| `general.fetch` `https://example.com/` | title **Example Domain** |
| `general.http` GET `https://api.github.com/zen` | HTTP 200, body `Encourage flow.` |
| `general.code` `print(1/0)` then `print(17*19)` | failed, then `323` |

A first `general.fetch` of `https://www.gnu.org/licenses/gpl-3.0.txt` returned `upstream_error` ("The page could not be fetched"). `example.com` succeeded in the same tool.

`general.http` POST `https://httpbin.org/post` with `{"ok": true}` stopped at `waiting_approval`. Policy text: "A second person approves this write." The agent owner (`admin@dev.local`) received **422** `sod_violation`. `approver@dev.local` approved it. The run then completed. The tool preview contains `POST`, `HTTP 200`, and `"json": {"ok": true}`.

## 5. Documents

Uploaded `docs/architecture/agentic-runtime-architecture.pdf` (not written for this test). The library reports **43 pages**. Outline anchors include `p5-s5` heading **1. Executive Summary** and `p7-s10` heading **2. Requirements**.

Summary claims include the quote `MUST / SHOULD / MAY are used in the RFC 2119 sense for architectural requirements.` at anchor `p2-s1`, page 2, `model: true`.

Check of a passage on page 5: verdict `met`, citation anchor `p5-s5`, quote `This document defines a vendor-neutral reference architecture for a self-hosted agentic runtime environment`. The requirement "The organisation shall operate a colony on Mars" was `not_found`, citation `null`, reason "The document does not contain a passage that supports this."

Compare of GPL 3.0 against GPL 2.0 returned a `removed` change at `p1-s0` quoting `GNU GENERAL PUBLIC LICENSE`. A rewrite was `proposed`, then `accepted` after `:decide`.

The documents screen lists the PDF at 43 pages: `docs/testing/m31/mobile-light-documents.png`.

## 6. Knowledge, memory, and skills

Collection `m31-library-1793819805` used embedding model `BAAI/bge-m3` and indexed **1** chunk from a library file whose only warehouse code is `ND-1844-QUILL`.

Cited answer: `The warehouse code for the north dock is ND-1844-QUILL [1].`

An agent with no collection: `I do not have access to the documents or specific information about the warehouse code for the north dock.`

Skill `weekly-status` on "Write the weekly status note" produced a summary that begins `STATUS-OK`.

Memory before edit: `You can call me Captain Bala.` After the row was changed to `Call the user Captain Rivera`: `I should call you Captain Rivera, as per your preference.`

Screen: `docs/testing/m31/mobile-dark-knowledge.png`.

## 7. Connectors

GitHub read of `octocat/Hello-World` README succeeded. Text: `Hello World!`

`connectors.github_create_issue` on `vundavallibalakrishna/agentic-runtime` waited for approval. The production UI, signed in as `approver@dev.local`, clicked **Approve** (HTTP 200). The run completed and GitHub issue **41** is open: `https://github.com/vundavallibalakrishna/agentic-runtime/issues/41` titled `M31 certification probe`.

The catalog labels Slack, Teams, calendars, drives, Jira, Notion, Salesforce, Zendesk, HubSpot, Okta, Entra, AWS, Azure, and GCP as `not_live`. The UI badge is **Not live-tested**. Email is `live` from an earlier local SMTP proof, not from a customer mailbox in this pass. S3 is `public` (provider API, not AWS). Screenshot: `docs/testing/m31/flow-connectors.png`.

## 8. Orchestration

Parent `lead2-1793820072` called `red2-1793820072` and `blue2-1793820072` in parallel. Both children `completed`. Parent summary: `RED and BLUE`. Limits on that definition: `maxDepth` 2, `maxParallel` 2, `childTimeoutS` 90, `maxCostMicros` 5,000,000, `maxTokens` 16000. An earlier parent with `maxTokens` 4000 finished `budget_exceeded` ("Stopped because the max tokens limit was reached") after both children had already completed.

Self-approval: the tool result was `You cannot ask the requester to approve their own request.`

Inbox question `Which colour?` was answered `blue`. The run summary was `blue`. A later question `Still there?` stayed `waiting_input` across an API restart and then completed after the answer `yes`.

Schedule `*/5 * * * *` ticked in process. Run summary: `PING`. Signed webhook first response **202**, the same body again **409**.

Wall-clock Temporal firing was not observed. See [OQ-67](../open-questions.md).

## 9. External surface

Agent slug `m31-exposed-1793819805`. Key created in the API and, separately, in the Expose tab (`Certification UI`, prefix `6718a23abe86`, 30/min). After reload the full secret is not on the page. Screenshot: `docs/testing/m31/flow-expose-prefix.png`.

| Check | Observed |
|---|---|
| REST `What is 2 + 2?` | `output` `4`, status `completed` |
| Idempotent replay | HTTP 200, same run id, header `idempotent-replayed: true` |
| Stream | HTTP 200, `content-type: text/event-stream; charset=utf-8`, `data: {"text":"5"}` |
| No key | **401** |
| Revoked key | **401** |
| `rateLimitRpm` 2 | **200, 200, 429** |
| MCP `tools/list` | `agent_m31_exposed_1793819805` |
| MCP `tools/call` `5 + 5` | text `10` |
| A2A `message/send` `3 + 3` | artifact `6` |

## 10. Durability and migrations

`m31_fresh` migrated empty to `0031` with no `grc` schema. `m31_populated` (copy of a database already at `0031`) upgraded as a no-op and kept its tenant and agent rows.

Run `01a1a81f-b27f-7209-a733-539532f8c065` was `running` when the API process was killed. After restart it was `failed` with `interrupted`: "The API restarted while this run was working. It was marked failed and was not resumed."

Run `01a1a81f-aa03-7194-ae84-649593ce2234` stayed `waiting_input`. The inbox still had 1 question. After the answer it `completed`.

Still present after restart: 4 library documents, 1 knowledge collection, 1 memory row, 1 agent API key.

## 11. Visual sweep

Production server. Playwright Chromium. Desktop 1440×900 and mobile 390×844, light and dark. Each shot was taken after the heading was visible and no busy skeleton remained.

| Screen | Files |
|---|---|
| Chat | `desktop-light-chat.png`, `desktop-dark-chat.png`, `mobile-light-chat.png`, `mobile-dark-chat.png` |
| Builder | `*-builder.png` |
| Agents | `*-agents.png` |
| Documents | `*-documents.png` |
| Knowledge | `*-knowledge.png` |
| Memory | `*-memory.png` |
| Skills | `*-skills.png` |
| Connectors | `*-connectors.png` |
| Runs | `*-runs.png` |
| Approvals | `*-approvals.png`, `flow-approval-pending.png`, `flow-approval-decided.png` |
| Schedules | `*-schedules.png` |
| Inbox | `*-inbox.png` |
| Settings | `*-settings.png` |
| Models | `*-models.png`, `flow-model-stored.png` |
| Expose | `flow-expose-prefix.png` |
| Retired route | `*-retired.png`, `flow-retired.png` |

Prefix the theme files with `docs/testing/m31/`. Walkthrough: `docs/testing/m31/walkthrough.webm`. Approval click: `docs/testing/m31/approval.webm`.

## 12. Soak

`scripts/m31_soak.py` for **20.01 minutes**, 4 workers, public `/v1` on an agent whose alias is `qwenm31`. The key limit was 600 requests per minute. A 429 waits 2 seconds before the next attempt.

| Measure | Value |
|---|---|
| Calls | 6,821 |
| HTTP 200 | 5,911 |
| HTTP 429 | 910 (854 on opening a conversation, 56 on sending a message) |
| Error rate | 13.34%, all of them 429 |
| Throughput | 340.9 requests/minute, 295 successful/minute |
| p50 / p95 / p99 | 0.401 s / 0.949 s / 1.927 s |
| API RSS | 342,548 KB at the first sample, 467,276 KB at the last, max 467,276 KB |
| Postgres connections on `m31_fresh` | start 7, end 8, max 8 |

No pool exhaustion. The 429s are the per-key minute window, which was already shown to return 429 at a limit of 2. RSS rose by about 125 MB across the window while the process kept every new conversation in its cache. It did not run away, and the connection count stayed flat. See [OQ-68](../open-questions.md).

## 13. Walkthrough

`docs/testing/m31/walkthrough.webm` is the production UI: sign-in, models with **Key stored** and sample `pong`, the builder, connectors, the Expose tab with a prefix and no secret after reload, and `/grc/audit`. `docs/testing/m31/approval.webm` is the approver inbox going from two pending writes to **Nothing is waiting for you.**

## Defect fixed in this pass

A tool-console call stored a `tool_calls` row whose run had no agent, so the insert violated `fk_tool_calls_run_id_runs`. The failed row stayed in memory and the next flush of any request, including document upload and agent create, returned 500. The console run now points at a real agent version. A tool call whose run is not in `runs`, and an approval link whose approval row is not in `approvals`, are skipped instead of aborting the transaction.

## What the platform does, and what it does not

| Does today | Does not |
|---|---|
| Chat-first agents on a customer OpenAI-compatible model | Public self-signup (`OQ-65`) |
| Sandboxed code and shell, files, fetch, HTTP with approval | Web search until a search key is set |
| Documents with page anchors, propose-then-accept rewrites | Unattended Temporal cron on a private cluster in this pass (`OQ-67`) |
| Knowledge with `bge-m3`, memory, skills | A2A push, gRPC, and task-list pagination (`OQ-64`) |
| GitHub issue create live; other connectors labelled when not live | A customer mailbox, Slack workspace, or cloud account in this pass |
| `/v1` REST, SSE, idempotency, 401, 429, MCP, A2A | Rate-limit windows that survive a process restart (`OQ-64`) |
| Restart marks `running` as `interrupted` and keeps waiting questions | File bytes and the temp workspace directory (`OQ-59`) |

## Soak numbers

Window **20.01 min**. 6,821 calls, 5,911 succeeded, error rate **13.34%** (910 responses were 429). p50 **0.401 s**, p95 **0.949 s**, p99 **1.927 s**. RSS **335 MB → 456 MB**. Connections **7 → 8** (max 8).
