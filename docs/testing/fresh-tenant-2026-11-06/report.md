# Fresh tenant run, 6 November 2026

The owner asked for the product to be run from an empty database: seed one tenant and its admin with a
script, sign in, configure the model in the product, and try the basic AI flows in a browser, with no mock,
no fake service and no built-in data.

**Result: the product does not work for a tenant a customer would create.** It runs only when the tenant's
slug is `dev` and a user `admin@dev.local` exists. With those two names in place, sign-in, registering a
model, plain chat, running Python and drafting an agent work with a real model. Reading an attached file,
fetching a web page, exact numbers in tool results and choosing an embedding model do not.

Two defects that stopped every real chat turn were fixed during the run (M38b-T01). The rest are planned in
[M38b](../../09-plan/M38b-real-tenant.md).

## What was run

| Part | What |
|---|---|
| Code | `main` at `dbf8826`, plus the seed script and the two fixes named below |
| Mode | `AR_ENV=prod`, `AR_DEPLOYMENT_MODE=single_tenant`. `fake-llm` was not started |
| Services | A separate Compose project with empty volumes: Postgres, Valkey, Temporal, Keycloak, SeaweedFS, OpenBao, OPA, Squid, Mailpit. All eleven app processes |
| Model | DeepInfra, `Qwen/Qwen3-32B`, registered in the Models screen. The key was typed into the password field |
| Seed | `scripts/seed_tenant.py`: plans, system roles, one tenant, one admin, and the admin's account in Keycloak |
| Browser | Chromium driven by Playwright through the real sign-in page. Screenshots are in this folder |

Three stacks were built, each from an empty database:

| Run | Tenant slug | Admin | Outcome |
|---|---|---|---|
| 1 | `acme` | `ada@acme.example` | Keycloak accepts the password. The product answers "This organisation is not set up on this server" |
| 2 | `dev` | `ada@acme.example` | Every API request returns 500 |
| 3 | `dev` | `admin@dev.local` | Sign-in works. The flows below were tested on this run |

## Flows on run 3

| Flow | Result | Evidence |
|---|---|---|
| Sign in with single sign-on and a password | Works | `run3/01-signed-in.png` |
| Chat before a model is configured | Works: "The model alias 'reasoning' is not connected to a registered model. Open Models…" | `run3/03-chat-before-any-model.png` |
| Register a provider and test it | Works: "pong (969 ms)", key stored and not shown again | `run3/04-provider-registered.png` |
| First chat with the real model | **Failed, then fixed.** The run stayed "working" with no answer. After the fix it answers in 5 s | F8, F9, `run3/05-first-real-answer.png` |
| Run Python | Works for the sum of squares (6 s) | `run3/07-python-tool.png` |
| Exact numbers from a tool | **Fails.** The tool printed 829348951; the model reported 828922111 | F12, `run3/08-number-masked-then-invented.png` |
| Fetch a web page | **Fails.** Denied after 40 s, the run dies, the chat shows an empty answer | F11, `run3/06-web-fetch-blank-failure.png` |
| Ask about an attached PDF | **Fails.** "…could not be found in the document" | F13, `run3/09-attached-pdf-not-read.png` |
| Analyse an attached CSV | **Fails.** The model wrote its own `orders.csv` with invented rows, then hit the step limit | F13, F14, `run3/10-attached-csv-step-limit.png` |
| Draft an agent from a sentence | Works (8 s), with one naming defect | F17, `run3/11-builder-draft.png`, `run3/12-agent-editor.png` |
| Knowledge: create a collection, add a PDF | Indexed in 4 s, with a model nobody configured | F15, `run3/13-knowledge-indexed.png` |

Not tested in this run: memory, approvals, routines and schedules, skills, connectors, channels,
evaluations, image tools, OCR, web search, a second user, and a knowledge question asked in chat.

## Findings

Severity: **A** stops a customer; **B** gives a wrong or unsafe result; **C** is a visible defect.
Each finding was seen in the run unless it says "read in code".

### The tenant is built into the code

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F1 | A | The API attaches to the database only for the tenant whose slug is `dev`. Any other tenant leaves it serving memory, and sign-in rejects the organisation. | API log `durable_waiting_for_seed`, then `oidc_organization_rejected organization=acme`; `durable/bind.py` `_lookup` (`WHERE slug = 'dev'`), `auth/complete.py` `profile_for`; `run1-acme/02-tenant-acme-rejected.png` |
| F2 | A | The API needs a user `admin@dev.local`. Each process builds a demo tenant in memory, owned by a fixed user id, and writes it to the database on the first request. Without that user the write breaks a foreign key and every request returns 500. | `ForeignKeyViolationError … fk_agents_owner_user_id_users` in `durable/flush.py` `_agents`; `chat/service.py` `seed_demo` |
| F3 | B | When the session check returns 500, a visitor who is not signed in is shown the workspace, with "Internal Server Error", in place of the sign-in page. No data is returned, but the shell is. | `run2/01-workspace-shown-without-sign-in.png` |
| F4 | C | In production mode the sign-in page lists four `@dev.local` users and prints their password. The buttons return 404. | `run1-acme/01-sign-in-page-production-mode.png`; `apps/web/src/app/(auth)/login/page.tsx` |
| F5 | C | The header and the session say the tenant is "Dev" on plan "enterprise". The tenant row says "Acme" on `self_hosted`. | `run3/01-signed-in.png`; `auth/routes.py` `session` |
| F6 | B | A new tenant receives agents it did not create: `helpdesk` and `revenue-analyst` beside `assistant` and `builder`. All four were written to the database on the first sign-in. | `agents` table after sign-in; `run3/12-agent-editor.png` lists them |
| F7 | B | The production bootstrap job (`python -m ar_domain.bootstrap`) ran the dev seed first: the `dev` tenant, four users, the `fake-llm` provider, three agents and a policy. **Fixed here** (M38b-T02). `python -m ar_domain.migrations.run` still runs the dev seed after migrating (read in code). | `bootstrap.py` before this change; `migrations/run.py` |

### Models

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F10 | B | The Models screen of a new tenant in production mode lists a platform provider `fake-llm` at `http://127.0.0.1:8099/v1` with three models and five aliases. The form opens with the name "Local fake". Choosing OpenAI-compatible fills in DeepInfra's address and `Qwen/Qwen3-32B`. | `run3/02-models-first-look.png`; `models-admin.tsx` |
| F16 | A | Only one chat model can be registered from the screen, and only the `reasoning` alias is pointed at it. There is no way to add an embedding, rerank or vision model, to edit or delete a provider or model, or to change `fast`, `vision`, `embed` or `rerank`, which stay on `fake-llm`. | `models-admin.tsx` `registerProvider` |
| F15 | B | Knowledge indexing used an embedding model nobody configured. With no embedding model registered, the code takes the first real provider and calls the model id `BAAI/bge-m3` on it. The document text went to that model, and the screen states "Embedding model BAAI/bge-m3". It works on this provider by coincidence. | `knowledge/live_embed.py` `resolve_embedding`; `run3/13-knowledge-indexed.png` |
| F18 | C | The chat model picker offers `embed` and `rerank` as chat models and lists `reasoning` twice (React reports a duplicate key). | Browser console during run 3 |

### The turn

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F8 | A | **Fixed here.** With Temporal and Postgres both present, the worker could not save a finished turn: it had imported only some table modules, so the audit row's foreign key to `tenants` did not resolve. Twelve of twenty-nine table modules were registered. | Worker log `NoReferencedTableError … audit_events.tenant_id`; `db/registry.py`, `test_table_registry.py` |
| F9 | A | **Fixed here.** After that failed save, the retry found the finished turn in memory and reported "completed" without saving. The workflow ended as completed, the database still said `running`, and the chat waited without end. | `runs` row `running` with a completed workflow; `execute_chat_turn.py`, `test_turn_activity.py` |
| F11 | A | Fetching `https://example.com` was refused as "not on the egress allow list" after 39.7 s. The tool ran on the worker's event loop, so no heartbeat was sent for more than ten seconds, Temporal cancelled the turn, and three attempts failed together. The chat shows an empty answer and no error. The allow list is a field on each agent; there is no tenant setting for it. | `tool_calls` row `egress_denied`, `latency_ms 39737`; worker log "Activity cancelled"; `run3/06-web-fetch-blank-failure.png` |
| F12 | B | The default redaction masks ordinary numbers in tool results. `print(7919*104729)` gave 829348951, the result reached the model as `[US_DRIVER_LICENSE]ORT]UMBER]E]`, and the model answered **828922111**. Overlapping matches are replaced one inside the other, which is why the placeholder is garbled. Redaction of tool results is on by default with every Presidio recogniser. | `tool_calls.result_preview`; `pii/analyzer.py`, `security/guardrails.py` `apply_result_safety`; `run3/08-number-masked-then-invented.png` |
| F13 | A | A file attached in chat does not reach the agent. The message stores the file id, but the model called `documents.ingest` with an id it made up, and for the CSV it wrote its own file with invented rows and analysed that. The cause was not traced past `chat/service.py` passing attachment names to the prompt. | `tool_calls` rows for both runs; `messages.content` holds the real `file_id` |
| F14 | A | File tools and code do not share a folder. `general.write_file` reported "Wrote /workspace/orders.csv" and `general.list_files` listed it, but Python got `FileNotFoundError: '/workspace/orders.csv'`. Code runs as a subprocess on the host, in a temporary folder, with the platform's own Python environment (the traceback path is the platform's `.venv`). There is no container. | `tool_calls` errors in the CSV run |
| F19 | B | The same failing Python was sent four times, and the run stopped at "max steps limit" (8) without an answer. | CSV run; tool review A5 and A12 |

### Smaller

| # | Sev | Finding |
|---|---|---|
| F17 | C | The agent drafted from "Create an agent called Contract Reviewer that…" is named "Create an agent called contract reviewer that reads". The draft itself has the persona "Contract Reviewer". |
| F20 | C | Restarting the API signs everyone out, because sessions are held in process memory (already OQ-59). |
| F21 | C | With no telemetry collector, every process logs an export failure every few seconds. `durable_memory reason=database_unavailable` is logged when the database is up and the tenant is missing. |
| F22 | C | The Keycloak admin client read the new id from the response body. Keycloak returns it in the `Location` header, so a created user was never added to its organisation. Nothing called it. **Fixed here** with the seed script. |

## What was fixed during the run

- **Every process registers the whole schema, and a finished turn is always saved** (F8, F9). M38b-T01.
- **The bootstrap creates a tenant and its admin and nothing else, and `scripts/seed_tenant.py` also creates
  the sign-in account** (F7, F22). M38b-T02.

Nothing else was changed, and nothing was patched to get a flow past a defect. Run 3 used the names `dev`
and `admin@dev.local` because they are the only ones the code accepts; that is F1 and F2, not a workaround
to keep.

## How to repeat it

```bash
# 1. An empty stack on its own ports and volumes (.env with AR_ENV=prod and private host ports)
docker compose -p ar-fresh -f compose.yaml --profile deps up -d --wait
make migrate

# 2. One tenant and its admin. The admin's password is read from standard input.
KC_BOOTSTRAP_ADMIN_USERNAME=admin KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
  uv run python scripts/seed_tenant.py --slug acme --name "Acme" \
  --admin-email ada@acme.example --admin-name "Ada Lovelace" < password-file

# 3. Every process except fake-llm
grep -v '^fake-llm' Procfile.dev > /tmp/Procfile.real && uv run honcho start -f /tmp/Procfile.real
```

Then open the web app, choose **Continue with SSO**, and sign in. Until M38b-T03 and T04 land, step 2 has to
use `--slug dev --admin-email admin@dev.local` for the product to start.
