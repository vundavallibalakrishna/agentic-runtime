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
- **T04c** The demo tenant, its people, fixtures and showcase move to `ar_testing`. `ChatService()` starts
  with no tenant, and tests that need the demo tenant build it with the helper.
- **T04d** The fixed user catalogue and the memory identity leave the API (with T05).
- **T04e** `mcp-gateway` and `sandbox-manager` stop building a store with a demo tenant. The scripted
  provider, its models and the platform aliases are not built in memory (with M38a-T07).

**Done when:** no product code names a demo tenant or person, and the unit suite and the browser tests pass.

**Tests:** `test_m38b_empty_store.py`; the browser specs.

## M38b-T05 Sign-in shows only what is real

**Depends on:** T03. **Areas:** `apps/web/src/app/(auth)/login/`, `apps/web/src/components/app-shell`,
`services/api/src/ar_api/auth/routes.py`. **Findings:** F3, F4.

**Do:**

- The sign-in page has no list of users and no password hint. The `dev-login` route is removed.
- When the session check fails for any reason other than "not signed in", the visitor sees an error page
  with a retry, never the workspace.

**Done when:** an unauthenticated visitor sees only the sign-in page or an error page, whatever the API returns.

**Tests:** Playwright `m38b-sign-in.spec.ts` (axe-clean); `test_m38b_sign_in.py`.

## M38b-T06 Migrating does not seed

**Depends on:** T04. **Areas:** `migrations/run.py`, `seed/`, `Makefile`, `deploy/helm/`. **Finding:** F7.

**Do:** `python -m ar_domain.migrations.run` only migrates. `make seed` calls the tenant seed with the values
in `.env`. The dev seed package is deleted once T04 has moved its last caller.

**Done when:** a Helm install on an empty database holds the tenant named in its values and nothing else.

**Tests:** `tests/integration/test_migrations.py`; `scripts/check_helm.py`.

## M38b-T07 Every model is configured in the product

**Depends on:** T04. **Areas:** `apps/web/src/components/models/`, `models/`, `knowledge/live_embed.py`,
`memory/`. **Spec:** [model gateway](../03-specs/04-model-gateway.md). **Findings:** F15, F16, F18.

**Do:**

- The Models screen lists providers, models and aliases, and each can be added, edited, tested and removed.
  A model has a kind (chat, embedding, rerank, vision, image) and its limits. No vendor address or model
  name is filled in by the form.
- Knowledge and memory embed with the model the tenant's `embed` alias points at. With none configured they
  refuse, with a message that names the Models screen. The built-in model id and the "first provider" guess
  are removed.
- The chat model picker lists chat aliases only, once each.

**Done when:** an admin configures a chat model and an embedding model on an empty tenant using only the
screen, and a collection states the model that indexed it.

**Tests:** `test_m38b_embedding_setting.py`; `models-admin.test.tsx`; Playwright `m38b-models.spec.ts`.

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

## M38b-T11 The fresh run is kept as a check

**Depends on:** T03 to T10. **Areas:** `scripts/fresh_run/`, `docs/08-quality/testing-strategy.md`,
`docs/testing/m38b-checklist.md`.

**Do:** the run in the report becomes a script that builds an empty stack, seeds a tenant with a name of the
caller's choosing, drives the browser through sign-in, model setup and the flows in the report, and writes
screenshots and a pass or fail for each. It needs a real model key and runs before a release. It also covers
the flows the first run left out: memory, approvals, a knowledge question in chat, and a second user.

**Done when:** the script passes on `main` with a tenant that is not called `dev`.

**Tests:** the script itself; its result is recorded in `docs/testing/m38b-checklist.md`.
