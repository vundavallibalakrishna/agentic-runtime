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
| F16 | A | Only one chat model can be registered from the screen, and only the `reasoning` alias is pointed at it. There is no way to add an embedding, rerank or vision model, to edit or delete a provider or model, or to change `fast`, `vision`, `embed` or `rerank`, which stay on `fake-llm`. | `models-admin.tsx` `registerProvider` **Fixed** in M38b-T07c: the screen adds, edits, tests and removes providers, models of each kind and aliases. |
| F15 | B | Knowledge indexing used an embedding model nobody configured. With no embedding model registered, the code takes the first real provider and calls the model id `BAAI/bge-m3` on it. The document text went to that model, and the screen states "Embedding model BAAI/bge-m3". It works on this provider by coincidence. | `knowledge/live_embed.py` `resolve_embedding`; `run3/13-knowledge-indexed.png` **Fixed** in M38b-T07b: no model id is built in and no provider is picked. |
| F18 | C | The chat model picker offers `embed` and `rerank` as chat models and lists `reasoning` twice (React reports a duplicate key). | Browser console during run 3 **Fixed** in M38b-T07b: the pickers list chat aliases only, each once, and the API refuses a conversation pointed at another kind of alias. |

### The turn

| # | Sev | Finding | Evidence |
|---|---|---|---|
| F8 | A | **Fixed here.** With Temporal and Postgres both present, the worker could not save a finished turn: it had imported only some table modules, so the audit row's foreign key to `tenants` did not resolve. Twelve of twenty-nine table modules were registered. | Worker log `NoReferencedTableError … audit_events.tenant_id`; `db/registry.py`, `test_table_registry.py` |
| F9 | A | **Fixed here.** After that failed save, the retry found the finished turn in memory and reported "completed" without saving. The workflow ended as completed, the database still said `running`, and the chat waited without end. | `runs` row `running` with a completed workflow; `execute_chat_turn.py`, `test_turn_activity.py` |
| F11 | A | Fetching `https://example.com` was refused as "not on the egress allow list" after 39.7 s. The tool ran on the worker's event loop, so no heartbeat was sent for more than ten seconds, Temporal cancelled the turn, and three attempts failed together. The chat shows an empty answer and no error. The allow list is a field on each agent; there is no tenant setting for it. Seen again on 7 Nov with a tool that did nothing wrong: `documents.summarise` on an attached PDF took 20 s, the heartbeat stopped, the turn was cancelled and run three times, and the chat showed an empty answer after four minutes. Any tool call longer than about ten seconds ends a turn this way; the fix is to run tool work off the worker's event loop (M38-T09). | `tool_calls` row `egress_denied`, `latency_ms 39737`; worker log "Activity cancelled"; `run3/06-web-fetch-blank-failure.png` |
| F12 | B | The default redaction masks ordinary numbers in tool results. `print(7919*104729)` gave 829348951, the result reached the model as `[US_DRIVER_LICENSE]ORT]UMBER]E]`, and the model answered **828922111**. Overlapping matches are replaced one inside the other, which is why the placeholder is garbled. Redaction of tool results is on by default with every Presidio recogniser. Seen again on 6 Nov in a tool search result: the description "S3-compatible storage" reached the model as `[US_DRIVER_LICENSE]-compatible storage`. Seen again on 7 Nov on an attached CSV: the region names East and South reached the model as `[NRP]`, the order dates as `[DATE_TIME]`, and two rows of the file were fused into one, so a question about units was answered 35 where the file says 80. In a traceback `_agent.py` became `_[URL]`. On screen the two `[NRP]` lines of the answer are not drawn at all, so the person sees two of four totals (`run11-attachments/02-csv-total-by-region.png`). | `tool_calls.result_preview`; `pii/analyzer.py`, `security/guardrails.py` `apply_result_safety`; `run3/08-number-masked-then-invented.png` |
| F13 | A | A file attached in chat does not reach the agent. The message stores the file id, but the model called `documents.ingest` with an id it made up, and for the CSV it wrote its own file with invented rows and analysed that. The cause was not traced past `chat/service.py` passing attachment names to the prompt. **Fixed** in M38b-T08. Two causes: the prompt carried only the file's name, and a worker knew only the files that existed when it started, so an upload made later was unknown to the process that ran the turn. | `tool_calls` rows for both runs; `messages.content` holds the real `file_id` |
| F14 | A | File tools and code do not share a folder. `general.write_file` reported "Wrote /workspace/orders.csv" and `general.list_files` listed it, but Python got `FileNotFoundError: '/workspace/orders.csv'`. Code runs as a subprocess on the host, in a temporary folder, with the platform's own Python environment (the traceback path is the platform's `.venv`). There is no container. **Narrowed** in M38b-T08: the tools did share one folder; what failed was the path. `/workspace` exists only where code runs in a private root, and the file tools printed it everywhere. Tools now name files relative to the working folder, which works in code on every host. Still true: without a private root, code runs on the host with the platform's own interpreter and packages (`import pandas` worked although the tool says only the standard library is installed), and a traceback from such a package shows the platform's install path (M40). | `tool_calls` errors in the CSV run |
| F19 | B | The same failing Python was sent four times, and the run stopped at "max steps limit" (8) without an answer. | CSV run; tool review A5 and A12 |

### Smaller

| # | Sev | Finding |
|---|---|---|
| F17 | C | The agent drafted from "Create an agent called Contract Reviewer that…" is named "Create an agent called contract reviewer that reads". The draft itself has the persona "Contract Reviewer". |
| F20 | C | Restarting the API signs everyone out, because sessions are held in process memory (already OQ-59). |
| F21 | C | With no telemetry collector, every process logs an export failure every few seconds. `durable_memory reason=database_unavailable` is logged when the database is up and the tenant is missing. |
| F22 | C | The Keycloak admin client read the new id from the response body. Keycloak returns it in the `Location` header, so a created user was never added to its organisation. Nothing called it. **Fixed here** with the seed script. |
| F23 | B | Read in code on 6 Nov while doing M38b-T03: the runtime, system and ingest workers build their store with `allow_loopback=True` in every environment. The API allows loopback only in dev and CI. Tool calls run in the runtime worker. **Fixed** in M38b-T03a: every process asks one rule. |
| F26 | A | Read in code on 6 Nov, then proved: renaming or deleting a provider and deleting a model through the API changed one process's memory only. Nothing was written to the database, so the row came back after a restart and the workers kept using it. **Fixed** in M38b-T07a. |
| F27 | B | The loader each process runs before a turn read every tenant's providers, models and aliases, with no tenant filter, and never removed a row. **Fixed** in M38b-T07a: one loader, scoped to the tenant served, that makes the registry equal the database. |
| F28 | B | A provider's key could not be replaced: there was no way to send a new key, and saving one failed on the stored key's unique name. **Fixed** in M38b-T07a; the old key is deleted in the same transaction. |
| F29 | B | The store allowed loopback addresses unless told otherwise, so any code that built it without saying so was permissive; `sandbox-manager` did, in every environment. **Fixed** in M38b-T07a: refused by default. |
| F30 | C | An error on the Knowledge or Memory screen is plain unstyled text pressed against the next heading, with **Try again** as a bare link. The words are right; the presentation is not at the bar. | `run7-embeddings/01-…`, `02-…`; `knowledge-screen.tsx` |
| F31 | B | What the assistant remembers from a turn is decided by two keyword patterns ("remember that …", "I prefer …"), not by a model. No code asks a model what to remember. | `memory/extract.py` `heuristic_ops`; `memory/session.py`; M38b-T12 **Fixed** in M38b-T12: one call to the tenant's model after the answer decides it. |
| F32 | B | With no rerank model, knowledge search scored passages by shared words. On the live tenant "When I am ill, do I still get my salary?" found nothing in a policy that covers sick pay, and "What is the wifi password?" was reported answerable from the leave policy. **Fixed** in M38b-T07b: unscored passages are returned in search order (OQ-103). | Live run 7 |
| F33 | B | Tool search still ranks the catalogue with vectors made from a hash of the text, which carry no meaning. On 22 requests the right tool was among the first twelve of the tenant's 156 for one request. **Fixed** in M38a-T06: tools are ranked by the tenant's embedding model and by shared words, and the stored hash vectors are emptied. | `tools/search.py`; `run10-tool-search/` |
| F34 | C | With the memory "Ada is allergic to peanuts" recalled ("Using 1 memories"), one of two answers said "I don't have access to your medical or dietary records" before mentioning peanuts as an example. The other used the fact directly. The wording that hands a memory to the model needs a look. | `run7-embeddings/06-chat-recalls-the-memory.png` |
| F35 | A | Creating a collection, adding a document and saving a memory left no row in `audit_events`; only the model registry changes and sign-ins are there. This is the gap the November review already names: changes made through the process store are audited in memory and not saved. | Live run 7, `audit_events`; review phase on the repository layer |
| F36 | C | Every agent definition names a `fast` alias, and the definition spec says titles, compaction and memory extraction use it. No code sends work to it. The Models screen therefore does not list it (OQ-104). | `agents/defaults.py`; `docs/05-contracts/definition-schema.md`; M38b-T12 **Fixed** in M38b-T12: memory extraction is sent to it, and the Models screen lists it. |
| F37 | C | When the identity provider refused the seed's admin call, the seed said only "status 403". The provider had said "HTTPS required": its admin realm refuses plain HTTP from an address it treats as external. **Fixed** in M38b-T07c: the seed repeats the provider's own reason. | Seeding a second tenant for run 8 |
| F38 | B | The image tool decided whether a model can read images from vendor model names written into the code, and its setup message named a vendor and a model. **Fixed** in M38b-T07c: it is a setting of the model ("This model can read images"), and the message names the Models screen. | `documents/vision.py` |
| F39 | B | A provider registered without an API key, such as a model server on the tenant's own network, was not called at its address for chat: the call went to the gateway address or the scripted server's. **Fixed** in M38b-T12. | `chat/service.py` `_completion_url_for` |
| F40 | C | One of three identical requests for birthday gift ideas was refused by the default assistant ("I can't help with choosing a birthday gift…"). The others answered. Answer quality across runs is not yet measured. | `run9-memory-extraction`; M42 |
| F41 | A | A memory the person deleted on the Memory screen stayed in the worker's copy and went on being recalled until the worker restarted, and a memory a worker saved did not appear on the Memory screen. Each process kept its own copy and only ever added to it. **Fixed** in M38b-T12 for memory: every process makes its copy equal the database before a turn and before each memory request. | Live run 9; `durable/hydrate.py` |
| F42 | B | A tenant setting changed in the product did not reach a worker until it restarted: settings were read once, when the process attached. **Fixed** in M38b-T12: they are read again before each turn. | `durable/hydrate.py` `reload_run` |
| F43 | A | Nothing the assistant remembered from a live chat was ever saved. A fact made in a worker carries the database driver's id type in its source reference, and the JSON encoder rejected it, so the save failed for the whole turn's memory. Found with the first real extraction. **Fixed** in M38b-T12 in the shared encoder. | Live run 9; `durable/codec.py` `as_json` |
| F44 | B | When a conversation is too long, the summary that replaces its older turns is built by rules (ids and citation marks are kept), not written by a model. | `memory/compaction.py` `summarise`; M38-T14 |
| F45 | B | `control.search` ranks every tool the tenant has, not the tools the agent is granted, so it can name a tool the agent cannot call: on the live tenant its first answer for "read text from photo" was `files.read`, which the assistant is not bound to. Separately, a chat turn sends the model every tool the agent is bound to, whatever their number; the narrowing the runtime spec describes for agents with more than 30 tools is not on the chat path. | `tools/handlers.py` `searchable_tools`; `tools/agent_loop.py` `resolve_catalog` call; spec 07 §8; M39-T04 |
| F46 | C | The first tool call in a process after it starts was recorded at 5.1 s, and the next at 3.3 s. Timed on its own, that first search takes under 10 ms and a later one about 1.6 s. Where the rest goes was not measured. | `tool_calls.latency_ms`; M38b-T10 |
| F47 | C | The chat shows a tool call as the bare tool name under the heading **Plan**, with no arguments and no result. | `run10-tool-search/02-second-search.png`; M42 |
| F48 | B | An upload over 8 MiB is accepted (the limit is 25 MiB) but kept only in the memory of the process that received it: it never reaches a worker and is lost on restart. File bytes and each file's details are one `file_blobs` row in Postgres; the `files` table is never written and nothing goes to the object store the spec names. A process loads every file of the tenant into memory when it starts. | `durability/store.py` `_MAX_BLOB`, `remember_blob`; `files/logic.py` `MAX_UPLOAD_BYTES`; `SELECT count(*) FROM files` is 0 on the live database; M38b-T13 |
| F49 | B | When a script printed nothing, the model stated four totals it had not computed (East $2,500 and so on; the file says 1,042.50). The script ended in `totals.to_string()` and the code tool showed only what was printed. **Fixed** in M38b-T08 for the cause: the last expression's value is shown and an empty result says so. The model's readiness to state a number it was not given is the same weakness as F34. | `tool_calls` rows of conversation `01a1b21d…`; `tools/general.py` `showing_last_value` |
| F50 | C | The model took six tool calls for one sum: it tried a command that is not installed, then guessed a column name three times before looking at the columns. Nothing tells it what is installed, and the attachment line does not say what the file holds. | `tool_calls` rows of `run11-attachments`; M39-T01 |
| F51 | B | A sent message does not show its attachment: after sending, nothing on the message says a file came with it. Only one file can be attached to a message. | `apps/web/src/components/chat/chat-screen.tsx`; `run11-attachments/02-csv-total-by-region.png`; M38b-T08a |

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

Then open the web app, choose **Continue with SSO**, and sign in.

Two things to know when repeating it. One process serves one tenant: with more than one tenant in the
database, start the processes with `AR_BOOTSTRAP_TENANT_SLUG=<slug>`. And the local identity provider's
admin realm refuses plain HTTP from an address it treats as external ("HTTPS required"); the seed now
repeats that reason, and on a local stack the realm's `sslRequired` can be set to `NONE` from inside the
container.

## Since the run

| Date | Task | What changed | Proof |
|---|---|---|---|
| 6 Nov 2026 | M38b-T03 | F1 and F5 are fixed, and F2 no longer applies to a process with a database. A fourth empty stack was seeded with tenant `acme` and admin `ada@acme.example`. The API and the three workers logged `durable_bound tenant=acme`, sign-in worked, the header read "Acme", a provider was registered, and a chat turn ran Python and finished. The tenant held `assistant`, `helpdesk` and `builder`, created when the admin first opened the product, and no `revenue-analyst`. | `run4-acme/01-acme-signed-in.png` |
| 6 Nov 2026 | M38b-T04a | F6 is fixed. On a fifth empty stack the seed alone left `assistant` and `builder`, both owned by `ada@acme.example`, 14 tool servers, no provider and no conversation; a second run of the seed changed nothing. After sign-in, a registered provider, a chat turn and a builder draft, the tenant held those two agents and the draft. | `agents` table before and after |
| 6 Nov 2026 | M38b-T04b | No process falls back to a demo tenant. An API or worker without its database, or without a tenant in it, waits and tries again in every environment. The browser tests start the API through a harness that puts the demo tenant in. | `test_m13_memory_mode.py`, `test_m38b_e2e_harness.py`; `m2-chat.spec.ts` passed through the harness |
| 6 Nov 2026 | M38b-T04c | A product store starts with no tenant: the API, the workers, `mcp-gateway` and `sandbox-manager` build none. Unit tests and the browser-test harness put the demo tenant in through `ar_testing.demo`, and a test fails if product code calls the demo seeding. | `test_m38b_empty_store.py` |
| 6 Nov 2026 | M38b-T05b | F4 is fixed: the sign-in page has one button and the product has one way in. Found and fixed with it: the Users screen showed four made-up people when its request failed (F24), the guest page sent the fixed tenant `dev` (F25), and the Users page header said "the four accounts created by the dev seed". | `run6-sign-in/01-sign-in-page.png`; on the live stack `dev-login` answered 401 and `scripts/sign_in.py` signed `ada@acme.example` in with the session returning tenant Acme; `test_oidc_login.py` |
| 6 Nov 2026 | M38b-T05c | F3 is narrowed. A failed session check now replaces the page with "We could not check your sign-in", **Try again** and **Sign in again**. The page frame is still drawn while the check runs, as before; checking on the web server before any page is sent is M38b-T05d, which needs the API to stop running tool calls on its event loop (M38-T09). | `app-shell.test.tsx`; `e2e/m38b-sign-in.spec.ts` (axe-clean) |
| 6 Nov 2026 | M38b-T04e | F10 is fixed at its source: no process builds the `fake-llm` provider, its models or the aliases that pointed at it. A new tenant's Models screen lists only what its admin registered. | `test_m38b_empty_store.py`; the live Models screen |
| 6 Nov 2026 | M38b-T07a | F26 to F29 are fixed. On the live stack, through the API as the signed-in admin: a provider was renamed, a second provider and model were added and removed (the provider was refused while it still had a model), and the database then held one provider, one model, one stored key and an audit row for each step. Chat still answered after the rename. | `tests/integration/test_m38b_model_registry.py` on a real Postgres; the `model_providers`, `models`, `secret_refs` and `audit_events` tables |
| 6 Nov 2026 | M38b-T07b | F15, F18 and F32 are fixed. On the live `acme` tenant, as the signed-in admin and with a real model: with no embedding model, **Create collection** and **Remember this** answered "No embedding model is set. An administrator sets one on the Models screen…" (409). The admin then registered an embedding model on the existing provider and pointed `embed` at it through the API, and the alias test returned a vector of 1024 numbers. A collection was created and states its model; two documents were indexed into 7 chunks; four questions that share no key word with the handbook each ranked the right section first; a memory was saved and found by a question in other words; and the assistant answered a lunch question from that memory. The database holds the model's id on the collection and on the fact, and 1024-number vectors. The registry and the collection survived a restart of every process. New findings: F30, F31, F33, F34, F35. | `test_m38b_embeddings.py` (unit and integration); `run7-embeddings/01-…` to `06-…` |
| 6 Nov 2026 | M38b-T07c | F16, F37 and F38 are fixed. Two more tenants were seeded in the same database (`globex`, then `initech`), each empty: two default agents, no provider. On `initech`, signed in as its admin, using only the Models screen: the page listed the four names the product calls, two marked "Not set, needed", and an empty form. The admin added a provider (address and key typed in), added a chat model in the dialog that opens next and left "Use this model for: Answers" ticked, tested Answers ("It answered. pong"), added an embedding model the same way and tested it ("Returned a vector of 1024 numbers."). In Advanced mode the admin renamed the provider, was refused when removing a provider that still has models and a model an alias points at (each with its reason in the dialog), changed the temperature the answers alias sends (it was 0.2), and added and tested an alias of their own. Chat then answered, and a new knowledge collection read "Embedding model BAAI/bge-m3 · 6 chunks" and found the right passage. The database has an audit row for each registry change. New finding: F36. | `test_m38b_models_api.py`; `models-admin.test.tsx`; Playwright `m38b-models.spec.ts`; `run8-models-screen/01-…` to `10-…` |
| 6 Nov 2026 | M38b-T12 | F31, F36, F39, F41, F42 and F43 are fixed. The extraction prompt was checked against the real model on 19 exchanges and kept what a careful reader would keep in all 19 (`scripts/memory_extraction_eval.py`). On the live `acme` tenant, in the browser: a fact a worker had saved from an earlier chat was on the Memory screen; deleting it there made the assistant answer "I do not have any information about your family"; "My sister Odile runs our Lyon warehouse. Suggest two questions…" was answered, and a few seconds later the chat showed "Memory updated: Sister is called Odile and manages the Lyon warehouse" with **Undo**, and the Memory screen listed it; with the organisation's guidance set to "Never keep anything about pets or animals", "My dog Bruno keeps barking at night" was answered and nothing was kept. The extraction call is in the usage records under its own key. New findings: F40, F44. | `test_m38b_memory_extraction.py` (unit and integration); `run9-memory-extraction/01-…` to `04-…` |
| 6 Nov 2026 | M38a-T06 | F33 is fixed. Tools are ranked by meaning, with the model the tenant's `embed` alias names, plus the words the request shares with the tool's name and description; with no embedding model the ranking is by words and the result says so. Checked against the live `acme` tenant's real embedding model on 22 requests (`scripts/tool_search_eval.py`): among the assistant's 27 tools the right one came first for 11, in the first five for 20 and in the first twelve for all 22 (with hash vectors: 2, 4 and 9); among all 156 tools the tenant can search, first for 7, first five for 17, first twelve for 19 (with hash vectors: 0, 1 and 1). Six other ways of combining the two scores were measured on the same requests and none was clearly better, so the simplest stayed. Found while proving it: the provider took between 3 and 37 seconds to embed the 156 descriptions, and the first version did that inside the first search. Now a search never waits for it: in a fresh process the first search answered in under 10 ms ranked by words while the catalogue was embedded on its own thread (13.6 s), and the next took 1.6 s ranked by meaning. In the browser, as the signed-in admin, the assistant was asked to use its tool search twice right after a restart and named `documents.ocr` both times (`run10-tool-search/`). The database held hash vectors for all 156 tools; revision 0034 emptied them (156 rows, 0 vectors after). F45, F46 and F47 were found on the way. Decision: OQ-106. |
| 7 Nov 2026 | M38b-T08 | F13 is fixed and F14 is narrowed; the task stays open until T09 and M38-T09 let the two chats answer correctly. On the live `acme` tenant, as the signed-in admin with the real model (`run11-attachments/`): with `orders.csv` attached, the assistant opened `inputs/orders.csv` at its first try and its totals are the file's (North 817.0, East 1,042.5, South 420.5, West 522.5), where before the fix it asked for `attached_csv_file.csv` and gave up. A second message in the same conversation, with nothing attached, read the same file. With `leave-policy.pdf` attached, the assistant passed the real file id and then the real path to `documents.ingest`, and `documents.summarise` returned the policy's own sentences. Four defects were found by running it and fixed in the same change: a worker did not know a file uploaded after it started; the model wrote to `/workspace/...` from Python, which does not exist on this host, until the step limit; it gave up after one wrong path; and it invented totals when its script printed nothing (F49). What still spoils the answers is not in this task: redaction (F12) hid two region names and corrupted the file text, so the follow-up answer was wrong, and the PDF turn was cancelled by the heartbeat (F11). F48, F50 and F51 were found on the way. Decision: OQ-107. |

Still open: the code that builds the demo tenant still sits in the product packages, although only test
setup and the eval tooling call it (M38b-T04d and T04f).
