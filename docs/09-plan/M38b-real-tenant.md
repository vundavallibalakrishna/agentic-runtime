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
  the eval gym and `make eval` stop building the demo tenant inside product packages.
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
- **T07d** Memory embeds its facts again by itself after the embedding model changes (today it is
  `scripts/reembed_memory.py`, OQ-102). A knowledge search with no rerank model shows how close each
  passage is, which needs the similarity from each retrieval backend. The rerank route becomes a setting
  of the model, in place of the one vendor-shaped address the call still tries.

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

**Tests:** `test_m38b_attachments.py`; `test_m38b_one_workspace.py`.

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

**Tests:** `test_m38b_redaction.py`.

## M38b-T10 A refused or failed tool call is quick and visible

**Depends on:** M38-T09 for the event loop. **Areas:** `tools/general.py`, `apps/web/src/components/chat/`,
tenant settings. **Finding:** F11.

**Do:**

- A host that is not allowed is refused before any network call, with a message that says where to allow it.
- The tenant has an allowed-hosts setting in the product; an agent may narrow it.
- A run that fails shows its error in the chat, with a retry.
- Whether a loopback address may be reached becomes a setting the install controls, not a rule tied to the
  environment name (T03a made the rule the same in every process; this makes it configurable).

**Done when:** a refused fetch answers in under a second, the model tells the user what to change, and a
failed run is never an empty bubble.

**Tests:** `test_m38b_egress.py`; Playwright `m38b-failed-run.spec.ts`.

## M38b-T12 What is remembered from a turn is decided by the tenant's model

**Depends on:** T07b. **Areas:** `memory/extract.py`, `memory/session.py`,
`services/system/src/ar_system/workflows/memory_extraction.py`. **Spec:** [memory](../03-specs/11-memory.md).
**Finding:** F31.

**Do:** after a turn, the tenant's model is asked what to remember and its answer is applied. The two
keyword patterns ("remember that …", "I prefer …") that decide it today are removed. With no model the turn
remembers nothing and says so in the trace. This is the first work sent to the `fast` alias that every agent
definition names; when it is, `fast` joins the aliases the Models screen lists (F36, OQ-104).

**Done when:** "My daughter's name is Mira" is remembered without the word "remember", on a real model.

**Tests:** `test_m38b_memory_extraction.py`.

## M38b-T11 The fresh run is kept as a check

**Depends on:** T03 to T10. **Areas:** `scripts/fresh_run/`, `docs/08-quality/testing-strategy.md`,
`docs/testing/m38b-checklist.md`.

**Do:** the run in the report becomes a script that builds an empty stack, seeds a tenant with a name of the
caller's choosing, drives the browser through sign-in, model setup and the flows in the report, and writes
screenshots and a pass or fail for each. It needs a real model key and runs before a release. It also covers
the flows the first run left out: memory, approvals, a knowledge question in chat, and a second user.

**Done when:** the script passes on `main` with a tenant that is not called `dev`.

**Tests:** the script itself; its result is recorded in `docs/testing/m38b-checklist.md`.
