# Fresh-pass report — 5 Nov 2026 (Asia/Calcutta)

Live wipe + seed + functional matrix on Bala's Mac against project Postgres only.
Model: `Qwen/Qwen3-32B` via DeepInfra (`openai_compatible`, base `https://api.deepinfra.com/v1/openai`).
Embeddings: `BAAI/bge-m3` on the same base URL.
HEAD: `c94fee92c018c4fa3ff430c7a5556093883f5374` (ff-only to `origin/main`, M31).

## Safety

- Host Postgres **5432** (`jaiho-postgresql`), Redis 6379, Temporal 7233, apps on **8000** / **8013**: left running.
- Project compose Postgres **5433** (`agentic-runtime-postgres-1`), Valkey **6380**, Temporal **7234**, Qdrant **6333**, OPA **8181**: used for this pass.
- Cert processes: model gateway **18101**, API **18131**, web **18132** (`next start` from `apps/web`, `.next-fresh` build).
- API key loaded only from `.secrets/deepinfra_api_key` into `AR_CERT_LLM_API_KEY`. Never written to docs, screenshots, evidence JSON, or commits. Key scan of evidence + screenshots: **0 hits**.
- `.secrets/` is untracked (`git status` shows `?? .secrets/`). Do **not** `git add` it. Rotate the DeepInfra key that was pasted in chat earlier.

## DB wipe proof

1. `git pull --ff-only origin main` → `c94fee9…`.
2. Project volume for Postgres was recreated once (PG18 layout); only `agentic-runtime_pgdata`.
3. `make reset-db` inside compose Postgres on **5433** (not 5432).
4. After seed: alembic **0031**, **1** tenant, **4** users (`admin@dev.local`, `approver@dev.local`, …), built-in assistants, conversations start at **0** (grew during the pass). No `grc` OpenAPI paths.

## Model

| Check | Result |
|---|---|
| Provider `:test` pong | **PASS** — reply `pong`, latency **953 ms** |
| `hasApiKey` | **PASS** — `true`; API never returns plaintext key (`apiKeyField` false; DB secret rows 1, plaintext hits 0) |
| Alias | `qwenfresh` → `Qwen/Qwen3-32B` |

## Matrix

| Area | Result | Evidence |
|---|---|---|
| Identity: signup disabled | **PASS** | `POST /api/v1/signup` → **404** `signup is disabled` |
| Empty chat / no GRC routes | **PASS** | conversationCount 0 at start; OpenAPI `grc` paths **0**; UI `/grc` → Page not found |
| Model sealed | **PASS** | see above |
| Builder + repair (ZeroDivision → 323) | **PASS** | `tools-live.json` repair summary `323`, 2 tool calls, run `01a1aab0-dab4-704d-8f78-5fa9f0b1ddbe`. Canary `general.code` fail=ZeroDivisionError, ok=`323` |
| `general.write_file` / `list_files` / `read_file` | **PASS** (agent run) | Follow-up multi-tool run wrote `workspace note alpha`, listed, read back. Note: per-call `:test` sandboxes do **not** share files (list/read after isolated write can look empty) |
| `general.shell` | **PASS** | canary `fresh-shell`; follow-up `shell-ok` |
| `general.fetch` example.com | **PASS** | Title `Example Domain` |
| `general.http` GET github zen | **PASS** | HTTP 200 (recheck after OPA healthy) |
| `general.http` POST httpbin + SoD | **PASS** (after policy activate) | Default W2 is `approvers.mode=requester`, which deadlocks with agent-owner SoD (owner **422**/`403`, approver **403**). After step-up + activate of users-mode policy "Fresh HTTP approval": owner cannot decide, `approver@dev.local` **200**, run completed, body contains `"ok": true`. Run `01a1aabb-fc5c-75d1-8404-4de61fc289d4` |
| Documents (43-page PDF) | **PASS** | architecture PDF 43 pages; summarise/check/compare/rewrite accept recorded |
| Knowledge `bge-m3` | **PASS** | cited answer contains `ND-1844-QUILL [1]`; detached run declines inventing the code |
| Memory edit | **PASS** | before `Captain Bala` → after preference `Captain Rivera` |
| Skill `weekly-status` | **PASS** | summary begins `STATUS-OK` |
| GitHub read | **PASS** | README `Hello World!` |
| GitHub create issue | **PASS** | Issue **[#43](https://github.com/vundavallibalakrishna/agentic-runtime/issues/43)** `Fresh-pass probe Nov 5` after users-mode policy + approver decide. Run `01a1aabc-1611-7317-bd1a-296aa9b0e250` |
| Other connectors | **SKIP / not live-tested** | Catalog labels: email `live`, s3 `public`, github `live`; slack/teams/gcal/m365/gdrive/sharepoint/jira/confluence/notion/servicenow/salesforce/zendesk/hubspot/okta/entra/aws/azure/gcp → `not_live` (no credentials) |
| Orchestration parallel children | **PASS** | Follow-up summary `RED and BLUE`; children completed |
| Self-approval denied | **PARTIAL** | Inbox question path answered `blue`. Dedicated self-approval denial via `agents_ask` kind=approval was not cleanly captured this pass (`denied` empty when first inbox item was a question) |
| Inbox question | **PASS** | `Which colour?` → answered `blue` |
| Webhook 202 then 409 | **PASS** | orchestration evidence |
| Schedule in-process `:tick` | **PASS** | cron `*/5 * * * *`, tick run summary `PING` |
| Temporal wall-clock fire | **SKIP** | **OQ-67** — not proven |
| External REST `/v1` sync | **PASS** | output `4` |
| Idempotent replay | **PASS** | 200, same id, `idempotent-replayed: true` |
| SSE stream | **PASS** | `text/event-stream`, sample delta `5` |
| Missing / revoked key | **PASS** | both **401** |
| Rate limit | **PASS** | `200, 200, 429` |
| MCP tools/list + call | **PASS** | tool listed; call `5+5` → `10` |
| A2A message/send | **PASS** | artifact `6` |
| Durability: kill mid-run → interrupted | **PASS** | run `01a1aabf-1c39-73ba-b23a-0d45e9307bae` → `failed` / `interrupted`: "The API restarted while this run was working…" |
| Durability: waiting_input survives | **PASS** | ask run stayed `waiting_input` across restart; inbox question `Still there?` answered `yes` → completed |
| Library / knowledge / memory / key after restart | **PASS** | 4 docs, 1 knowledge collection, 1 memory row, provider `hasApiKey` true |
| Soak | **SKIP** | optional; not run this pass (time) |
| UI screenshots | **PASS** | `docs/testing/fresh-pass/` desktop light+dark + flow shots (chat, models key-stored, expose, approvals, retired). Mobile matrix skipped for time |

## Defects / product notes found (not fixed in a PR)

1. **Default W2 approver rule is `mode: requester`**, which conflicts with agent-owner SoD: the requester/owner cannot approve, and a second user is not eligible → deadlock until a users/group policy is activated (needs step-up). M31 worked because a users-mode policy was active; a fresh seed alone does not.
2. **Policy activate requires step-up** (`POST /api/v1/auth/step-up` with `confirmed: true` in non-prod).
3. **OPA must load the API policy bundle** on the cert API port; an OPA pointed at a stale port serves `policy_unavailable` and denies tools. Fixed during this pass by recreating OPA with `AR_PORT=18131`.
4. **First tool call can block the event loop** while spaCy `en_core_web_lg` downloads (seen earlier in the pass).
5. Occasional agent replies prefixed `fake:` with **zero tool calls** when the model path degrades — treat as a gateway/alias fallback smell; direct `:test` and the recorded repair/files runs used the real model.
6. **OQ-67** Temporal wall-clock schedule fire still unproven.
7. **OQ-68** cache growth / no eviction — not re-measured.
8. **OQ-66 / OQ-59 / OQ-64** unchanged from M31.

## Artifacts

- Report: `docs/testing/fresh-pass-report.md` (this file)
- Screenshots: `docs/testing/fresh-pass/*.png`, `ui.json`
- Raw evidence (local tmp, not for commit): `/tmp/fresh-pass-proof/` (`evidence.json`, `followup.json`, `durability.json`, `tools-live.json`, `tools-canary.json`, `approval-live.json`)
- Logs: `/tmp/fresh-pass-logs/`
- Local helper scripts (untracked, no secrets): `scripts/fresh_pass_proof.py`, `scripts/fresh_pass_followup.py`

## Teardown

Cert API / web / gateway processes are stopped after this report. Compose project deps on 5433/6380/7234 left up. Host jaiho/8000/8013 untouched.
