# M38b — A real tenant from an empty database

Goal: a customer's own tenant works from an empty database. A seed creates one tenant and its admin, the
admin signs in, configures every model in the product, and the basic AI flows work with a real model. The
product holds no built-in tenant, user, agent, provider or model name
([strict rules](../../AGENTS.md#strict-rules), [OQ-96](../open-questions.md)).

Source: [the fresh tenant run of 6 November 2026](../testing/fresh-tenant-2026-11-06/report.md). Finding
numbers (F1 to F22) are from that report. This milestone comes before the remaining M38a and M38 tasks,
because nothing else can be shown working until a real tenant starts. One pull request for each task. Paths
are under `libs/ar_domain/src/ar_domain/` unless they start with another top-level folder.

Each task is proved the same way: the run in the report is repeated on an empty database with a tenant that
is not called `dev`, and the flow the task names works in the browser with a real model.

## M38b-T00 The run, the rules and this plan

**Do:** the report and its screenshots, the strict rules in `AGENTS.md`, this file, the plan README row, and
OQ-96 to OQ-98.

## M38b-T01 A finished turn is always saved

**Depends on:** none. **Areas:** `db/registry.py`, `durable/bind.py`,
`services/runtime/src/ar_runtime/activities/execute_chat_turn.py`. **Findings:** F8, F9.

**Do:**

- One registry lists every module that maps a table. Each process loads it when its store attaches to the
  database, so a foreign key resolves in the API and in every worker alike.
- A retry of the turn activity that finds the turn already finished saves it before it reports it as done.

**Done when:** with Temporal and Postgres present, a turn answered by a real provider is stored and shown.

**Tests:** `test_table_registry.py` (the registry equals the table modules in the source tree, and every
foreign key resolves); `services/runtime/tests/unit/test_turn_activity.py` (a save that fails once is
repeated by the retry).

## M38b-T02 The seed creates a tenant and its admin, and nothing else

**Depends on:** T01. **Areas:** `bootstrap.py`, `identity/seed.py`, `identity/keycloak_admin.py`,
`scripts/seed_tenant.py`, `docs/07-ops/local-dev.md`. **Spec:** [deployment modes](../00-overview/deployment-modes.md).
**Findings:** F7, F22.

**Do:**

- `python -m ar_domain.bootstrap` creates the plans, the system roles, one tenant on plan `self_hosted` and
  its tenant admin. It no longer runs the dev seed, and it stops when no admin address is given.
- `scripts/seed_tenant.py` does the same and creates the tenant's organization and the admin's account in
  the identity provider. The password is read from standard input.
- The identity-provider client reads a new id from the `Location` header and reports a refused call.

**Done when:** on an empty database the script leaves one tenant, one user with the admin role, and no
provider, agent or example row. Running it twice changes nothing.

**Tests:** `test_seed_memory.py`; `tests/integration/test_migrations.py` (bootstrap on a real database);
`test_keycloak_admin.py`.

## M38b-T03 The tenant comes from the database

**Depends on:** T02. **Areas:** `durable/bind.py`, `durable/hydrate.py`, `chat/service.py`,
`tools/seed_tools.py`, `services/api/src/ar_api/auth/`, `services/api/src/ar_api/middleware/durable.py`,
worker store builders. **Spec:** [identity and tenancy](../03-specs/02-identity-tenancy.md).
**Findings:** F1, F5, and F2 for a process with a database. Decision: OQ-99.

**Do:**

- A process reads the tenant it serves from the `tenants` table: the one named by
  `AR_BOOTSTRAP_TENANT_SLUG`, or the only tenant when that is empty. It waits while there is none. The
  renaming of built-in ids onto database ids is deleted.
- A process with a database holds no demo tenant. The store's start-up seeding is split into the tool
  catalogue, which belongs to no tenant, and the demo tenant, which only a store without a database gets.
  A deployed API whose database is down serves nobody and tries again; it no longer falls back to the demo
  tenant.
- People, their names, status and roles are loaded from the database on attach, before each run and at
  sign-in. They were in memory only, and only for the four demo users, so policy and approvals saw no roles
  for a real person.
- Sign-in matches the token's organization against the tenant served and the address against that tenant's
  users. The session returns the tenant's own slug, name and plan.
- Serving several tenants from one process still needs the repository layer (the November review's largest
  gap). OQ-99 records it.

**Done when:** a tenant called `acme` with an admin at any address signs in, the header reads "Acme", and a
chat turn runs.

**Tests:** `test_m10_durable_paths.py` (tenant lookup, waiting, no demo tenant, a worker waits);
`tests/integration/test_m10_durable.py` and `test_m26_durable.py` on a real database (binding fields, roles
from rows, a connection started in one process and finished in the next);
`services/api/tests/unit/test_login_identity.py` (an organization that is not the tenant served is refused);
`test_routine_persistence.py`; `services/runtime/tests/unit/test_m38_worker_store.py`.

## M38b-T03a One loopback rule for every process

**Depends on:** T03. **Areas:** `libs/ar_common/src/ar_common/settings.py`, the API, `mcp-gateway` and the
three worker store builders. **Finding:** F23.

**Do:** the runtime, system and ingest workers built their store with `allow_loopback=True` in every
environment, while the API allowed loopback only in dev and CI. Tool calls run in the runtime worker, so in
production a tool could be pointed at a loopback address the API would have refused. Every process now asks
`loopback_allowed(env)`.

**Done when:** a worker built for production refuses loopback addresses.

**Tests:** `services/runtime/tests/unit/test_m38_worker_store.py`.

## M38b-T04a A tenant's default agents come from its seed

**Depends on:** T03. **Areas:** `bootstrap.py`, `agents/service.py`, `agents/builder.py`,
`bundles/export.py`, `chat/service.py`. **Finding:** F6. Decision: OQ-100.

**Do:**

- The bootstrap and `scripts/seed_tenant.py` write the tenant's `assistant` and `builder` agents, owned by
  its admin, and the built-in tool catalogue. They go through the store a process uses, so a process then
  loads the same rows.
- No request creates an agent as a side effect. Listing agents, exporting a bundle, starting a draft and
  starting a conversation created the defaults for whoever asked first, with that person as owner.
- `helpdesk` is an example of the demo tenant. A real tenant does not get it.

**Done when:** after the seed alone, a tenant holds `assistant` and `builder` owned by its admin, and after
sign-in, chat and a draft it holds nothing it did not create.

**Tests:** `test_m38b_default_agents.py`; `tests/integration/test_migrations.py` (bootstrap on a real
database, run twice).

## M38b-T04 Nothing is built in memory

**Depends on:** T04a. **Areas:** `chat/service.py` (`seed_platform`, `seed_demo_tenant`, `seed_showcase`),
`tools/seed_tools.py`, the `showcase.py` modules, `services/api/src/ar_api/auth/` (`dev_users.py`,
`memory_identity.py`), `services/mcp_gateway`, `services/sandbox_manager`, `libs/ar_testing`,
`apps/web/playwright.config.ts`. **Findings:** F2, F10. Overlaps M38a-T05 and M38a-T07, which this task
absorbs for the tenant, the users, the agents and the provider.

T03 took the demo tenant out of every process that has a database, and T04a made the seed the only source of
a tenant's default agents. What is left, one pull request for each:

- **T04b** (done) The browser tests start the API through a test harness that puts the demo tenant in. No
  product process seeds a demo tenant when it has no database: it waits and tries again.
- **T04c** (done) A product store starts with no tenant. Tests build the demo tenant with
  `ar_testing.demo` (`demo_store`, `demo_application`), and a test fails if product code calls the demo
  seeding. The eval gym and `make eval` are eval tooling that still build it themselves.
- **T04d** The fixed user catalogue, the memory identity and the test sign-in leave the API (with T05), and
  the eval gym and `make eval` stop building the demo tenant inside product packages. **The eval gym part is
  done (7 Nov 2026):** `build_world`/`run_suite`/`cli.main` take a seeded store, and the demo tenant is built
  by the tooling that runs the gym (`scripts/m33c_eval_gym.py` via `ar_testing.demo.demo_store`), not in the
  gym package; `python -m ar_domain.evals.gym` guides to the script. The fixed users and memory identity
  already left the API with T05b. **Done (7 Nov 2026):** the `ar_system.evals.cli` suite command also takes
  a seeded store, built by `scripts/run_suites.py` via `ar_testing`; `make eval` runs the wrapper, and the
  guard `test_no_product_code_builds_the_demo_tenant` now finds no demo-tenant building in any product
  package. The test sign-in moves with T05 (its path already exists only in the harness, T05a).
- **T04e** (done) A product store starts with no model provider, model or alias. The scripted provider and
  the aliases that pointed at it were built in every process, so a new tenant's Models screen listed
  `fake-llm` in production. They are part of the demo tenant now. `make dev` still gets `fake-llm` from the
  dev seed's database rows (T06).
- **T04f** The code that builds the demo tenant (`seed_demo_tenant`, `seed_showcase`, the fixtures in
  `tools/seed_tools.py` and the `showcase.py` modules) moves out of `ar_domain` into `ar_testing`. After
  T04c nothing in the product calls it, so this is a move with no change in behaviour.

**Done when:** no product code names a demo tenant or person, and the unit suite and the browser tests pass.

**Tests:** `test_m38b_empty_store.py`; the browser specs.

## M38b-T05 Sign-in shows only what is real

**Depends on:** T04c. **Areas:** `apps/web/src/app/(auth)/login/`, `apps/web/src/components/app-shell`,
`apps/web/e2e/`, `services/api/src/ar_api/auth/`, `services/api/tests/support/e2e_server.py`, `scripts/`.
**Findings:** F3, F4. One pull request for each part:

- **T05a** (done) The browser tests sign in through `/api/v1/test/sign-in`, a path that exists only in the
  browser-test harness. The 36 specs stop using the product's sign-in buttons and `dev-login`.
- **T05b** (done) The sign-in page has one button. The `dev-login` route, the fixed user catalogue and
  the memory identity are out of the API; the last two now live in `ar_testing`, plugged in by test setup.
  The smoke and proof scripts sign in through the identity provider with `scripts/sign_in.py`. The Users
  screen no longer shows four made-up people when its request fails, and the guest page no longer sends a
  fixed tenant.
- **T05c** (done) A visitor who is not signed in goes to the sign-in page. When the session check fails
  for any other reason, the page is replaced by an error with **Try again** and **Sign in again**; it used
  to stay up with "Internal Server Error" inside it.
- **T05d** The web server checks the session before it sends a workspace page, so nothing of the workspace
  reaches a browser that is not signed in. Depends on M38-T09: a first version of T05c waited for the
  session check before drawing the page, and the browser suite then failed whenever the API was busy with a
  tool call, because the API still runs tool calls on its event loop. A gate in front of every page needs an
  API that always answers quickly.

**Done when:** the product has one way to sign in, and an unauthenticated visitor sees only the sign-in page
or an error page, whatever the API returns.

**Tests:** `test_m38b_e2e_harness.py`; the browser specs; Playwright `m38b-sign-in.spec.ts` (axe-clean).

## M38b-T06 Migrating does not seed

**Depends on:** T04. **Areas:** `migrations/run.py`, `seed/`, `Makefile`, `deploy/helm/`. **Finding:** F7.

**Do:** `python -m ar_domain.migrations.run` only migrates. `make seed` calls the tenant seed with the values
in `.env`. The dev seed package is deleted once T04 has moved its last caller.

**Done when:** a Helm install on an empty database holds the tenant named in its values and nothing else.

**Tests:** `tests/integration/test_migrations.py`; `scripts/check_helm.py`.

**Done (7 Nov 2026).** `python -m ar_domain.migrations.run` only migrates; the dev seed it used to run
after migrating is gone (F7 remnant). Nothing in the standard flow called it to seed: `make migrate` and
the Helm `ar-migrate` job run `alembic upgrade head` directly, and `make seed` and the Helm bootstrap job
seed separately, so a Helm install already holds only the tenant named in its values. Deleting the dev
seed package rides with M38b-T04, which moves its last callers.

## M38b-T07 Every model is configured in the product

**Depends on:** T04e. **Areas:** `models/registry.py`, `chat/service.py`,
`services/api/src/ar_api/routers/m2.py`, `apps/web/src/components/models/`, `knowledge/live_embed.py`,
`memory/`. **Spec:** [model gateway](../03-specs/04-model-gateway.md). **Findings:** F15, F16, F18, F26 to
F29. One pull request for each part:

- **T07a** (done) Changes to providers, models and aliases are saved and reach every process. Renaming or
  deleting a provider and deleting a model changed one process's memory only. One loader makes a process's
  registry equal its tenant's database rows; it used to read every tenant's rows and never remove one.
  A provider's key can be replaced. Models can be edited and aliases removed. Removal goes from the outside
  in: an alias a published agent names, a model an alias points at, and a provider that still has models
  are refused with a message that says what to do. The store refuses loopback addresses unless the process
  that builds it allows them.
- **T07b** (done) Knowledge and memory embed with the model the tenant's `embed` alias points at. With none
  configured they refuse, with a message that names the Models screen. The built-in model id, the "first
  provider" guess and the vectors computed in the product's own process are removed: tests reach a
  stand-in embedding model over HTTP, registered like any model. A collection and a memory fact record the
  model that wrote their vectors. A model has an optional vector length. Without a rerank model, passages
  are returned unscored; nothing stands in for one (OQ-103). The test action works for an embedding or a
  rerank model, and a conversation can only be pointed at a chat alias.
- **T07c** (done) The Models screen lists providers, models and aliases, and each can be added, edited,
  tested and removed. A model has a kind (chat, embedding, rerank). The aliases the product calls are
  listed with whether each is set (OQ-104). No vendor address or model name is filled in by the form, and
  the "Local fake" kind is gone. One model can be tested by itself. What an alias sends by default is a
  setting, and only a chat alias starts with a temperature. Whether a model can read images is a setting of
  the model; the image tool no longer guesses it from vendor model names.
- **T07d** (done) Memory embeds its facts again by itself after the `embed` alias moves, beside the
  request that moved it; `scripts/reembed_memory.py` remains for a model that was down (OQ-102). A
  knowledge search with no rerank model shows how close each passage is: the dense search of each
  backend carries the cosine similarity on the hit, and the Knowledge screen shows it as a percentage.
  Where a rerank model is called, how the body is shaped and the lowest score that counts are the
  model's own settings (`requestOptions.rerank {path, body, min_score}`, Advanced mode); the
  vendor-shaped address the call tried is gone, and so are the bars written into the code, which
  dropped the right passage with every reranker the live provider hosts (F65).

**Done when:** an admin configures a chat model and an embedding model on an empty tenant using only the
screen, and a collection states the model that indexed it.

**Tests:** `test_m38b_model_registry.py` (unit and integration); `test_m38b_embeddings.py` (unit and
integration); `models-admin.test.tsx`; Playwright `m38b-models.spec.ts`.

## M38b-T08 An attached file reaches the agent

**Depends on:** T01. **Areas:** `chat/service.py`, `workspace/`, `tools/documents.py`, `tools/general.py`.
**Findings:** F13, F14.

**Do:**

- A file attached to a message is placed in the run's workspace, and the prompt names its path and id.
- The file tools and the code tool read and write the same folder, so a path one returns works in the other.

**Done when:** "Summarise the attached PDF" and "total the attached CSV by region" return answers taken from
the files.

**Tests:** `test_m38b_attachments.py` (unit and integration); `test_m38b_one_workspace.py`;
`test_m38b_code_output.py`.

**Done (7 Nov 2026).** The prompt names each attached file with its id and its path; the
file is at that path for every tool, in this turn and in later ones; a worker loads the conversation's
files before a turn (it knew only the files that existed when it started, which is why no tool could read
an upload); a conversation's working folder carries to its next turn; tools name a file by a path relative
to the working folder, which works in code on every host; a command that fails after naming `/workspace`
where it does not exist is told what to use; a wrong path is answered with what the folder holds; and
`general.code` shows the value of a script's last expression. Decision: OQ-107.

Two neighbouring defects spoiled the answers when this landed, and the task closed when they were fixed and
both chats were run again on the live tenant: redaction (F12, T09) and a long tool call cancelling the turn
(F11, M38-T09). With `orders.csv` attached the answer is the file's four totals with their region names, and
with `leave-policy.pdf` attached it is five points from the policy with its own numbers.

## M38b-T08a The chat shows what was attached

**Depends on:** T08. **Areas:** `apps/web/src/components/chat/`. **Finding:** F51.

**Do:**

- A sent message shows each attached file with its name, type and size, and opens it.
- More than one file can be attached to a message.

**Done when:** after sending two files with a message, both are shown on the message and after a reload.

**Tests:** `attachment-list.test.tsx`; `test_m38b_upload_rules.py`; `test_m38b_upload_limits_api.py`;
Playwright `m38b-attachments.spec.ts`.

**Done (7 Nov 2026).** Also needed, and done with it: the tenant settings for the allowed types and the
largest upload existed and were never read; the upload path used a list and a size written into the code,
and the composer a shorter list of its own, so a Markdown, Excel or Word file could not be attached in chat
although the tools read them. The composer now offers what the tenant allows (`GET /api/v1/files:limits`),
the product's default is every type it can read, and a file the browser gives no type is typed by its name.

## M38b-T09 Redaction does not change the facts

**Depends on:** none. **Areas:** `pii/analyzer.py`, `security/guardrails.py`, tenant settings, Settings
screen. **Spec:** [guardrails and privacy](../06-security/). **Finding:** F12. Decision: OQ-97.

**Do:**

- Tool results that the agent's own code produced are masked only by recognisers that are precise without
  context (a checksum or a fixed format). Number-shaped patterns need supporting context.
- Overlapping matches are merged into one placeholder.
- The entity list is a tenant setting with the safe default, shown in Settings.

**Done when:** a nine-digit result reaches the model unchanged, and an email address in a fetched page is
still masked.

**Tests:** `test_m38b_redaction.py`; `test_m38b_masking_api.py`; `masking-settings.test.tsx`; Playwright
`m38b-masking.spec.ts`.

**Done (7 Nov 2026).** The engine's scores were being ignored, so every weak guess was applied. A kind is
now masked when the tenant lists it and the match scores at least the tenant's bar; a weak pattern needs a
word nearby that names it; overlapping matches become one token. Names, places, dates and groups are off by
default. Also needed, and done with it: the engine was an optional extra that no image and no CI job
installed, so as shipped almost nothing was masked; Presidio and a small language model are now
dependencies and nothing is downloaded at run time (OQ-108). The kinds and the bar are on the Policies
screen and served by `GET /api/v1/tenant/masking`.

## M38b-T09a A masked value is shown as masked

**Depends on:** T09. **Areas:** `apps/web/src/components/chat/`. **Finding:** F12.

**Do:** the chat draws a masking token such as `[EMAIL_ADDRESS]` as a labelled mark, before the text is
read as Markdown. Today a line that starts with a token and a colon is read as a link definition and is not
drawn at all, so the person does not see part of the answer.

**Done when:** an answer with the line `- [EMAIL_ADDRESS]: primary contact` shows that line.

**Tests:** `masked.test.ts`; `markdown-view.test.tsx`.

**Done (7 Nov 2026).** Before the text reaches the Markdown parser, each token becomes inline code
(`apps/web/src/lib/masked.ts`), which Markdown never reads as a link definition and which shows the token
as the mark it is. A token that is Markdown link syntax, or already in code, is left alone.

## M38b-T10a Which hosts a tool may reach is the organisation's choice

**Depends on:** M38-T09 for the event loop. **Areas:** `tools/general.py`, `ar_common/settings.py`,
`identity/service.py`, `pii/analyzer.py`, `apps/web/src/components/policies/`. **Finding:** F11.
Decision: OQ-111.

**Do:**

- A host that is not allowed is refused before any network call, with a message that says where to allow it.
- The tenant has an allowed-hosts setting in the product; an agent may narrow it.
- Whether a loopback address may be reached becomes a setting the install controls, not a rule tied to the
  environment name (T03a made the rule the same in every process; this makes it configurable).

**Done when:** a refused fetch answers in under a second and the model tells the user what to change.

**Tests:** `test_m38b_egress.py`; `web-access.test.tsx`; Playwright `m38b-web-access.spec.ts`.

**Done (7 Nov 2026).** Also needed, and done with it: an agent's own list used to widen the organisation's;
the audit record of a settings change now says what changed, from what and to what; and the engine that
masks tool results is built when a process starts, so the first tool call after a restart is not the one
that waits (the first refusal took 4.7 s, now 78 ms).

## M38b-T10 A failed run is visible

**Depends on:** T10a. **Areas:** `apps/web/src/components/chat/`. **Finding:** F11.

**Do:** a run that fails shows its error in the chat, with a retry.

**Done when:** a failed run is never an empty bubble.

**Tests:** `test_m38b_failed_run.py`; `failed-reply.test.tsx`; Playwright `m38b-failed-run.spec.ts`.

**Done (7 Nov 2026).** The cause was on the server: five code paths each ended a failed run by marking the
reply it was making as completed, with the reason as its text, so the chat drew it as an answer from the
agent. One function now ends every failure; the reply is marked failed and carries the reason; the chat draws
it as a failure with **Try again**, after a reload too; and a later turn is not given it as an answer.

## M38b-T12 What is remembered from a turn is decided by the tenant's model

**Depends on:** T07b. **Areas:** `memory/extraction.py`, `memory/extract.py`, `memory/book.py`,
`durable/hydrate.py`, `durable/codec.py`, `chat/service.py`, `apps/web/src/components/memory/`,
`apps/web/src/lib/stream/`. **Spec:** [memory](../03-specs/11-memory.md). **Findings:** F31, F36, F39, F41,
F42, F43. Decision: OQ-105.

**Do:** after a turn, the tenant's model is asked what to remember and its answer is applied. The two
keyword patterns ("remember that …", "I prefer …") that decide it today are removed. With no model the turn
remembers nothing and says so in the log. This is the first work sent to the `fast` alias that every agent
definition names, so `fast` joins the aliases the Models screen lists (OQ-104).

**Done (6 Nov 2026).** Also needed, and done with it: the never-started extraction workflow is removed; a
fact saved in a worker is written to the database (the JSON encoder rejected the driver's id type, so no
memory from a live chat was ever saved); every process makes its memory and its tenant settings equal the
database before a turn, so the Memory screen shows what a worker saved and a deleted memory is forgotten
everywhere; a provider without a key is called at its own address; the chat screen reads a finished run
again for the "Memory updated" notice; and an administrator sets, on the Memory screen, whether the
organisation remembers from conversations and what it adds to the model's guidance.

**Done when:** "My daughter's name is Mira" is remembered without the word "remember", on a real model.

**Tests:** `test_m38b_memory_extraction.py` (unit and integration); `organisation-settings.test.tsx`;
`late.test.ts`; `scripts/memory_extraction_eval.py` against a real model.

## M38b-T13 Every accepted upload is kept, in the object store

**Depends on:** none. **Areas:** `chat/service.py` `upload`, `durability/store.py`, `durable/m35.py`,
`files/tables.py`. **Spec:** [files and artifacts](../03-specs/13-files-artifacts.md). **Finding:** F48.

**Do:**

- File bytes go to the object store the spec names, and the `files` table holds each file's row. Today the
  row and the bytes are one `file_blobs` row in Postgres and the `files` table is never written.
- Every upload the product accepts is kept. Today an upload over 8 MiB is accepted (the limit is 25 MiB),
  lives only in the memory of the process that received it, never reaches a worker and is lost on restart.
- A process reads a file's bytes when a tool needs them, not every file of the tenant when it starts.

**Done when:** a 20 MiB PDF attached in chat is read by the worker, and is still there after every process
restarts.

**Tests:** `test_m38b_file_store.py` (integration, with the object store).

**Done (7 Nov 2026).** The bytes are one object under the row's key in the S3 store the install names, put before the row exists; the row is in `files` through the write-behind; a worker learns a conversation's rows before the turn and fetches bytes when needed; a process never loads a tenant's files at start. The S3 client talks unsigned to a keyless store (the bundled SeaweedFS) and makes a missing bucket on first use. A file in `file_blobs` (revision 0033) is moved to the object store when its tenant is hydrated and dropped by a later revision (OQ-112). The upload body limit was two bugs found on the live tenant (F67): the API's 1 MiB JSON limit applied to the upload route, and the web proxy buffered to 10 MiB; both now carry the 25 MiB cap. The integration test runs against SeaweedFS in a container (`ar_testing.containers.s3_endpoint`).

## M38b-T14 A form starts empty

**Depends on:** none. **Areas:** `apps/web/src/components/`. **Findings:** F53, F64.

**Do:** no form in the product starts with a value the person did not type: a name, an address, a tool, a
message. A button that saves is disabled until what it needs is filled in.

**Done when:** the Policies, Tools, Import, Connections and Expose forms open with their text fields empty,
and the browser tests fill what they submit.

**Tests:** `tools-screen.test.tsx`; the existing browser tests for each screen.

**Done (7 Nov 2026).** The Policies form opened with `petstore.create_pet` and "Ask before creating a
pet."; the Tools form with `echo` and `memory://echo`; the import form with `imported`; the connection
form with `github`; the Expose panel with `Production` and "What is 2 + 2?". Choices among fixed kinds
(an effect, a transport, a period) keep a first value.

## M38b-T15 A conversation with no computer is not an error

**Depends on:** none. **Areas:** `sandboxes/service.py`, `apps/web/src/components/computer/`. **Finding:** F63.

**Do:** `GET /api/v1/conversations/{conversation_id}/sandbox` answers `{sandbox: Sandbox|null}` with `200`
when the conversation has no live computer, as [spec 12](../03-specs/12-sandbox-manager.md) already states;
a `404` is kept only for a conversation the caller cannot see. The workspace panel reads `.sandbox`. Today
the endpoint raises `404` whenever a conversation has no sandbox, which the browser logs as a failed
request on every chat.

**Done when:** opening a conversation makes no failed request in the browser console, and the panel still
shows a computer once one exists.

**Tests:** `test_m6_surface.py` (no sandbox returns a null sandbox, a live one is returned under `sandbox`).

**Done (7 Nov 2026).** The endpoint returns `{sandbox: None}` with `200` for a conversation with no
computer; proved on the live `acme` tenant: opening a chat logs no `404` for `.../sandbox`.

## M38b-T16 No region or industry in a default

**Depends on:** none. **Areas:** `ar_contracts/tenants.py`, `usage/quotas.py`, `usage/service.py`,
`routines/schedule.py`, `policy/logic.py`, `apps/web/src/components/routines/`, `apps/web/src/app/(app)/grc/`.
**Finding:** F55.

**Do:** no default a new tenant, user or form receives names a place or an industry (strict rules 3 and 7).
The tenant and user default timezone become `UTC` and the default locale `en`; the usage and quota
fallbacks for an unknown zone become `UTC`; the schedule label drops its hardcoded `IST` and reads the
offset (so a half-hour zone is `UTC+5:30`); the policy time helper offers only `UTC` and the tenant's own
configured timezone (as `local`), not a built-in list of cities. The retired pack's `/grc` "page not found"
stub is removed; an unknown path uses the app's own not-found.

**Done when:** a new tenant's default timezone is `UTC` and locale `en`, and `/grc` is the app's ordinary
not-found with no special route.

**Tests:** `test_m10_routines.py`, `test_m12_usage.py` (updated for the new fallback and label).

**Done (7 Nov 2026).** Defaults and fallbacks are `UTC`/`en`; the policy helper offers `UTC` and the
tenant's `local` zone; the `/grc` route is deleted. Proved on the live tenant: `/grc` returns the app's
not-found, and a new tenant's settings read `UTC`/`en`.

## M38b-T17 A failed screen looks finished

**Depends on:** none. **Areas:** `apps/web/src/components/common/management-layout.tsx`,
`apps/web/src/components/knowledge/`, `apps/web/src/components/memory/`. **Finding:** F30.

**Do:** an error on a management screen is a finished state, not a line of plain text with a bare link. A
shared `ErrorState` (a bordered card with a warning icon, the message, and a **Try again** button) replaces
the unstyled `<p>` on the Knowledge and Memory screens. It uses the design-system tokens, so light and dark
are both finished.

**Done when:** a failed load on the Knowledge or Memory screen shows the card with a working **Try again**,
and the component is available for other screens to adopt.

**Tests:** the existing web tests; the Knowledge error is proved live by forcing the list to fail.

**Done (7 Nov 2026).** `ErrorState` replaces the bare error on both screens; proved on the live `acme`
tenant by failing the knowledge list (`run21-error-state/01-knowledge-error-state.png`).

## M38b-T18 No behaviour follows the environment's name

**Depends on:** none. **Areas:** `ar_common/settings.py`, `ar_common/sandboxkit.py`, `api/main.py`,
`sandbox_manager/drivers/base.py`, `sandbox_manager/egress.py`, `sandboxes/runtime.py`, and the dev/test
config. **Finding:** F60.

**Do:** three behaviours keyed on `AR_ENV` become settings of the install, each with the safe production
value as its default (strict rule 6). `AR_EGRESS_ALLOW_WILDCARD` (default off) decides whether `*` is
honoured in a sandbox egress allowlist; `AR_SANDBOX_ALLOW_UNISOLATED` (default off) decides whether the
docker or host driver may run; `AR_FILES_SCANNER` (default `clamav`) is the upload scanner. The helpers sit
beside `loopback_allowed`. The dev stack and the test run set the relaxed values in their own config, so
effective behaviour is unchanged, but nothing reads the environment's name to decide.

**Done when:** no code chooses egress, sandbox isolation or virus scanning from `AR_ENV`; each is a setting
with a safe default; the suites pass with the dev/test config setting the relaxed values.

**Tests:** `test_m6_driver.py` (driver refused unless allowed); the egress and upload tests under the dev
config.

**Done (7 Nov 2026).** The three settings exist with safe defaults; the dev stack and test harnesses set
`AR_EGRESS_ALLOW_WILDCARD=true`, `AR_SANDBOX_ALLOW_UNISOLATED=true`, `AR_FILES_SCANNER=none`. No code reads
`AR_ENV` for these.

## M38b-T19 A failure the answer already explains gets no extra notice

**Depends on:** none. **Areas:** `tools/agent_loop.py`. **Finding:** F59.

**Do:** when a tool call fails but the run still answers, the line "A tool call failed and was not
recovered." is added only when the answer does not already tell the person a tool did not do its job. The
words that count as acknowledging a failure are broadened beyond `fail`/`error`/`could not` to the common
refusal phrasings (`blocked`, `refused`, `denied`, `not permitted`, `unavailable`, …), because a refused
fetch on the live tenant was reported as "blocked" and still got the notice. A structured marker the UI
renders is the longer-term form ([OQ-113](../open-questions.md)).

**Done when:** an answer that already explains a tool was blocked does not also carry the notice.

**Tests:** `test_m21_loop.py` (a blocked-fetch answer gets no extra notice).

**Done (7 Nov 2026).** The acknowledgement list is broadened; proved on the live `acme` tenant by a fetch
the egress rules refuse.

## M38b-T20 A recalled memory is handed over as known

**Depends on:** none. **Areas:** `memory/format.py`. **Finding:** F34.

**Do:** the recalled-memory section begins with a product-authored line that tells the model the facts are
things the person has shared and may be used directly, and that it should not say it has no record or no
access to the person's information. The facts stay wrapped as `user_data`. Before this, the block was bare
XML and the model sometimes disclaimed having the fact before using it.

**Done when:** asked about a recalled fact, the agent uses it without claiming it has no access to the
person's records.

**Tests:** `test_m38b_memory_framing.py`.

**Done (7 Nov 2026).** The block carries the framing line; proved on the live `acme` tenant with the
recalled peanut-allergy fact.

## M38b-T11 The fresh run is kept as a check

**Depends on:** T03 to T10. **Areas:** `scripts/fresh_run/`, `docs/08-quality/testing-strategy.md`,
`docs/testing/m38b-checklist.md`.

**Do:** the run in the report becomes a script that builds an empty stack, seeds a tenant with a name of the
caller's choosing, drives the browser through sign-in, model setup and the flows in the report, and writes
screenshots and a pass or fail for each. It needs a real model key and runs before a release. It also covers
the flows the first run left out: memory, approvals, a knowledge question in chat, and a second user.

**Done when:** the script passes on `main` with a tenant that is not called `dev`.

**Tests:** the script itself; its result is recorded in `docs/testing/m38b-checklist.md`.

**Done (7 Nov 2026).** `scripts/fresh_run/fresh_run.mjs` drives a seeded tenant through
sign-in, model setup, a chat answer, a knowledge search, a knowledge question in chat,
memory recall and a second user, writing a pass/fail and a screenshot per step and exiting
non-zero on any failure; `seed_and_run.sh` wires the seed and the gate into one command.
Everything is configuration and no secret is in the repo. Run on the live `acme` tenant
(slug not `dev`) against real DeepInfra models: sign-in, chat, knowledge search and memory
recall pass; knowledge-in-chat skips on the known tool-choice gap (F66/M39), and the
already-configured and no-second-user steps skip (`run24-fresh-run-gate/`). The checklist
is `docs/testing/m38b-checklist.md`.
