<!-- Generated from AGENTS.md by scripts/sync_agent_docs.py. Edit AGENTS.md, then run make gen. -->

# AGENTS.md — Agentic Runtime

Agentic Runtime is a self-hosted platform on which a company builds, governs and runs AI agents on its own infrastructure and models. Balakrishna Vundavalli designed and built it and owns its product decisions. The platform exists and was certified end to end in M31 ([report](docs/testing/m31-certification.md)). Work now hardens and extends it, so read the code before assuming what a spec says is how it behaves.

These are the instructions for anyone changing this repository, person or coding agent. This file is complete on its own: it imports nothing, and instructions from any folder above this repository do not apply here. `CLAUDE.md` is generated from it, so edit this file and run `make gen`. When anything here conflicts with a lower-level document, this file wins for *process*; the specs win for *behaviour*.

## Non-negotiable principles

Full text: [docs/00-overview/principles.md](docs/00-overview/principles.md). The goals are **CLEAN CODE**, **CUSTOMISABLE**, **EXTENSIBLE**, **SIMPLE UI/UX**, **OUTSTANDING PRESENTATION**.

1. **camelCase on the wire.** Public JSON (REST, SSE, webhooks, definition files the UI shows) uses camelCase properties. Python stays snake_case via `ar_contracts.api_model.ApiModel` (`alias_generator=to_camel`, `populate_by_name=True`, `serialize_by_alias=True`). Database columns and env vars are unchanged. CI runs `scripts/check_public_camel_case.py`.
2. **Demo-grade UI.** The primary create-agent path is a natural-language instruction handled by the built-in `builder` agent, with a reviewable preview and a form/YAML escape hatch. Empty, loading, and error states are mandatory. Bar: [ux-quality](docs/08-quality/ux-quality.md). Visual design follows [design-system](docs/08-quality/design-system.md): tokens in `apps/web/src/app/globals.css`, no new hex colours in feature code, light and dark both finished, theme defaults to the system preference.
3. **Agnostic core.** Core has no industry in it. Records-as-a-product (the evidence vault, legal holds, binders, the AI register, guest packets, and the questionnaire product) ships only as an optional signed pack. Four-eyes and the security audit log stay in core. New capabilities are packs or connector plugins ([extension-framework](docs/05-contracts/extension-framework.md)). Decisions: [ADR-0028](docs/02-architecture/adr/ADR-0028-agnostic-core.md) and the [production plan](docs/09-plan/agnostic-production-plan.md).
4. **The product is the generic platform.** A customer connects a model, builds agents, and gives them tools, connectors, skills and files.
5. **Defaults.** A tenant works after secrets and identity. Every other setting has a default. Settings UI has Simple and Advanced modes.
6. **North star.** A corporate assistant with its own computer, in the customer's environment, able to automate any work ([vision](docs/00-overview/vision.md)).

## Strict rules

The owner set these on 6 November 2026 after a run on an empty database showed how much of the product still leaned on built-in data ([report](docs/testing/fresh-tenant-2026-11-06/report.md), [OQ-96](docs/open-questions.md)). They are strict: a change that breaks one is not merged, and none of them is traded for speed. Where existing code breaks one, [M38b](docs/09-plan/M38b-real-tenant.md) and [M38a](docs/09-plan/M38a-one-model-path.md) remove it; new code never adds to it.

1. **No mocking.** The running product contains no mock, stub or stand-in for a model, a service, a tool or a person. A unit test may use the stand-in from `ar_testing`, registered from the test's own setup; nothing in `ar_domain`, a service, a connector or the web app knows it exists.
2. **No fake services.** The product, every end-to-end check and every visual check run against real services: the database, the object store, the workflow engine and a real model endpoint. When one is missing the product says so in words the user can act on. It does not fall back to something that pretends to work.
3. **No static data.** Nothing a customer sees, and nothing the product decides on, is written into code or the UI: no built-in tenant, user, agent, provider, model name, vendor address, example row or prepared answer. Data comes from the database, from a setting the customer controls, or from a real service. A seed creates one tenant, its admin and the two agents every tenant has, and nothing else (`scripts/seed_tenant.py`). No request creates a default as a side effect.
4. **Real data end to end.** A feature is working when it works from an empty database, through sign-in and the screens, with a real model. That run is the proof; a passing unit test is not.
5. **Fix the architecture, not the symptom.** A defect is fixed where it is caused, for every caller. No special case for one tenant, one path, one string or one test. If an existing path is not good enough, re-architect it in place and remove the old path in the same change. Do not land a patch beside it. If the right fix is larger than the task, record it in [open-questions](docs/open-questions.md) and plan it; do not land the patch.
6. **No shortcuts and no bypasses.** No environment switch that changes what the product does, no skip flag, no result reported before it is saved. Sign-in is the product's own userid/password check; there is no bypass around it and no second, hidden way in.
7. **No industry-specific rules, code or configuration.** Nothing in core, in a default or in a setting assumes an industry. Such a capability is a pack or a connector the customer installs (principle 3).
8. **Fully customisable.** Every model, prompt, limit, threshold, feature flag, label, URL, policy, role and tool grant a customer may need to change comes from a setting, tenant configuration or a pack, with a sensible default, and can be changed in the product without a code change. Code does not hard-code a vendor, a model id or a tenant.
9. **Reuse before build.** Before writing code, search the tree for an existing or half-built implementation and extend it. If it is not good enough, re-architect it in place so it is scalable, and remove the old path in the same change. Never add a second tool, renderer, store, event stream, schema or endpoint for something that exists. Every pull request description has a short reuse report.
10. **Grounded status claims.** A feature is called missing, partial or done only with evidence: file paths and symbols checked, tests run, or a live run. No claim from memory, a spec or a plan alone.
11. **Research or ask when unsure.** When the right design is unclear, research current practice from primary sources (official docs, well-known implementations, papers) and record the choice and links in an ADR or [open-questions](docs/open-questions.md). For a product decision, ask the owner rather than guess.
12. **Scalable and stateless by default.** No process-local production state. Anything shared lives in Postgres, Valkey or the object store. Design every feature for N replicas.
13. **Batched delivery.** One pull request per milestone contains all of its stories. Run the full CI suite locally, including the web end-to-end job on a production Next build and the kind jobs, before the first push. Push once. If CI fails, fix every failure in one commit. Do not push a fix at a time.
14. **Backward-compatible contracts.** Public API, SSE events and content-part changes are additive and versioned. Generated clients come from `make gen`.
15. **Security and observability by default.** Tenant isolation, authorisation, audit, secrets via `SecretStore`, and metrics and traces without content, on every new path. The never-skip rules below are the checklist. Do not restate them here.

## What is in the repository

| Path | What |
|---|---|
| `apps/web` | Next.js app: every user and admin screen, no business logic |
| `services/api` | FastAPI: public REST and SSE, sessions, `/v1` agent API, MCP and A2A exposure |
| `services/runtime`, `services/system`, `services/ingest` | Temporal workers: agent runs; routines and housekeeping; knowledge ingestion |
| `services/model_gateway`, `services/mcp_gateway` | The model endpoint behind aliases; the tool-call choke point |
| `services/sandbox_manager`, `services/sandbox_agent` | Sandbox allocation; the process inside a sandbox |
| `services/channels`, `services/fake_llm` | Slack, Teams and email; the scripted model for development and tests |
| `libs/ar_domain` | All business logic and the Alembic migrations |
| `libs/ar_common`, `ar_contracts`, `ar_connector_sdk`, `ar_testing`, `ar_client` | Shared basics; cross-process models; connector SDK; test fixtures; generated Python client |
| `connectors/`, `policies/`, `deploy/`, `evals/` | MCP connector servers; OPA Rego; Compose and Helm; golden and red-team suites |
| `docs/` | Specs, plan, decisions and test evidence |

The canonical list of deployables and modules is [service-decomposition](docs/02-architecture/service-decomposition.md). How the running system fits together: [docs/architecture/README.md](docs/architecture/README.md). Stack and exact versions: [docs/stack.md](docs/stack.md).

## Where the code and the specs differ

The specs say how the platform should behave. The [November 2026 review](docs/testing/review-2026-11-05/review-and-remediation-plan.md) found where the code does not yet do that, and its phases are the open work. The largest gap: the product paths built in M21–M31 run on the process-local `ChatService` store (`libs/ar_domain/src/ar_domain/chat/service.py`) with write-behind to Postgres, not on the repository and row-level-security layer. That limits durable mode to one API replica and the `dev` tenant, and those paths do not yet meet never-skip rules 1 and 3 below.

So:

- Do not describe a spec'd behaviour as working until you have checked the code or run it.
- Do not widen a gap. New code follows the never-skip rules, and a change that cannot says why in its pull request and in [open-questions](docs/open-questions.md).
- Check [progress.md](docs/09-plan/progress.md) and [open-questions](docs/open-questions.md) for what has landed since the review. M35, for example, made file bytes durable and capped the chat cache, while sessions and rate limits stay in process memory (OQ-59).

## Read before changing code

1. [README.md](README.md), then [principles](docs/00-overview/principles.md) and the [glossary](docs/00-overview/glossary.md).
2. [Service decomposition](docs/02-architecture/service-decomposition.md), [request flows](docs/02-architecture/request-flows.md), [tenancy and isolation](docs/02-architecture/tenancy-isolation.md).
3. The coding standards for [Python](docs/08-quality/coding-standards-python.md) and [TypeScript](docs/08-quality/coding-standards-typescript.md), and the [testing strategy](docs/08-quality/testing-strategy.md).
4. For the change itself: the [component spec](docs/03-specs/) it touches, [API conventions](docs/05-contracts/api-conventions.md) for an endpoint, [RLS](docs/04-data/rls.md) for a table, and any [security document](docs/06-security/) it touches.

## How work is picked and tracked

1. The owner's request comes first. Without one, take the next stage in the [agnostic production plan](docs/09-plan/agnostic-production-plan.md): the lowest-numbered stage whose dependencies are done. Future work is tracked by those stages, not by new M-numbers. M41-M43 have landed; [progress.md](docs/09-plan/progress.md) records the shas.
2. Earlier milestone files record how the platform was built. Use them as history and do not re-implement a task marked `done` in [progress.md](docs/09-plan/progress.md).
3. Do not open a new M-number. A change belongs to the stage it implements. Milestone files stay as history; never renumber a task that is already there.
4. Record the stage result in [progress.md](docs/09-plan/progress.md) with the commit sha. One stage per pull request unless the stage says otherwise.
5. A pull request that changes a screen includes **How to test visually**, as defined in the plan's [Visual test](docs/09-plan/README.md#visual-test) section: exact start commands, seeded login and data, and a numbered click-through with expected results.

## Running and checking

```bash
make bootstrap   # toolchains, dependencies, dev keys
make dev         # dependencies, migrations, seed and every process; AUTO_PORTS=1 moves busy ports
make check       # lint, typecheck, unit tests
make test        # unit and integration, OPA and web tests
make test-e2e    # Playwright against a running stack
make gen         # regenerate OpenAPI, schemas, clients and CLAUDE.md; CI fails on any diff
```

`make dev` still seeds the `dev` tenant. Sign in on the login form with email `admin@dev.local` and password `dev-password`; the product signs people in itself (no external identity provider). A clean tenant comes from `scripts/seed_tenant.py`, which sets the admin's password. Details: [local-dev](docs/07-ops/local-dev.md).

Things that catch people out:

- **Several agents may share a checkout.** Work in your own git worktree under `.claude/worktrees/<name>`, on a fresh branch from `origin/main`, with your own ports and database. Never use a bare `git stash`: the stash stack is shared.
- **`.env` leaks into unit tests.** `pydantic-settings` reads it, so `AR_OPA_URL` can point a test at a shared OPA, and a dev tenant seeded before a flag existed needs `make seed` again. Rule this out before blaming your change.
- **Next.js rewrites tracked files.** `next build` with `AR_NEXT_DIST` rewrites `apps/web/next-env.d.ts`, and `next dev` manages `apps/web/AGENTS.md`. Do not commit those changes by accident.
- **This Next.js differs from older versions.** Read `apps/web/node_modules/next/dist/docs/` before writing web code.

## Conventions

- **Names are fixed**: services, packages, tables, columns, endpoints, events, permissions, audit actions, metrics and env vars are exactly as written in the specs. Do not rename, pluralise differently or add synonyms. If you need a new name, add it to the owning spec and to the relevant catalogue in the same PR ([environments §3](docs/07-ops/environments.md#3-variable-catalogue), [audit §3](docs/06-security/audit.md#3-catalogue), [authn-authz §3](docs/06-security/authn-authz.md#3-permission-catalogue), [domain-events](docs/05-contracts/domain-events.md), [stream-events](docs/05-contracts/stream-events.md), [api-catalogue](docs/05-contracts/api-catalogue.md)).
- **Layering**: services never import each other; DB access only through `ar_domain` repositories inside a unit of work with tenant context ([coding-standards-python §2–3](docs/08-quality/coding-standards-python.md#2-ruff-and-lint-configuration)).
- **No test doubles in product code**: a fake model, a scripted or keyword-triggered answer, and a demo fixture never live in `ar_domain` or a service, gated or not. A test stand-in lives in `ar_testing` and is registered from test or dev setup as an ordinary provider. A test that needs a tenant builds the demo tenant with `ar_testing.demo`; a product store starts with none ([OQ-94](docs/open-questions.md), [M38a](docs/09-plan/M38a-one-model-path.md)).
- **Contracts first**: cross-process models live in `ar_contracts`; the OpenAPI document and TS client are generated (`make gen`), never hand-written.
- **Commits**: Conventional Commits, with the task id in the body (`Task: M4-T03`) when the change belongs to a task. CI checks the pull request title.
- **Docs move with code**: if the work reveals a spec gap, update the spec in the same PR and, if it is a decision, add an entry to [open-questions](docs/open-questions.md) with the default you applied.
- **No guessing**: when a spec is silent, apply the default in open-questions; if none exists, choose the safest option (deny, fail closed, smallest scope), document it in open-questions, and continue.

## Never-skip rules

1. **Tenant isolation**: every tenant-owned table has `tenant_id` + RLS; every query runs with `app.tenant_id` set; every new endpoint has a cross-tenant test that expects 404 ([tenancy-isolation §5](docs/02-architecture/tenancy-isolation.md#5-mandatory-isolation-tests)).
2. **Authorisation** on every endpoint via the permission named in the spec; no unguarded routes except the explicit public allowlist.
3. **Audit** every state change in the same transaction ([audit](docs/06-security/audit.md)).
4. **All tool calls through `mcp-gateway`** with policy evaluation; never call tools directly from the runtime; never put credentials into model context, tool arguments, sandboxes, logs or traces.
5. **Untrusted content** (tool results, documents, web pages, emails, channel messages from others) only enters prompts through `ar_common.wrapping` ([prompt-injection §3](docs/06-security/prompt-injection.md#3-untrusted-content-wrapping)).
6. **No content in telemetry** (prompts, messages, arguments, results, secrets).
7. **Secrets** only via `SecretStore`; never logged, never returned by APIs after creation.
8. **Migrations** follow [migrations §2](docs/04-data/migrations.md#2-rules-never-skip): expand/contract, RLS and grants in the same revision, tested up and down.
9. **Workflows are deterministic; activities idempotent**.
10. **Tests**: every task ships the tests listed in its **Tests** line; no skipped or `xfail` tests without an issue and an open-questions entry.
11. **Generated code is regenerated, not edited** (`make gen`).
12. **No placeholder markers** (to-do, to-be-decided, fix-me notes) in code or docs; open items go to open-questions with a default (the CI `docs` job greps for them).

## Definition of done

A change is done when **all** of the following hold:
- [ ] Every bullet of the task's **Do** is implemented and every **Done when** criterion is demonstrably met.
- [ ] The task's **Tests** exist and pass; `make check` and `make test` pass locally; all required CI jobs are green ([ci-cd §2](docs/07-ops/ci-cd.md#2-jobs)).
- [ ] Never-skip rules above are satisfied (isolation test, permission, audit, wrapping, telemetry hygiene, secrets).
- [ ] New endpoints appear in `openapi.json`, the generated clients, and match the [api-catalogue](docs/05-contracts/api-catalogue.md); new env vars, audit actions, permissions, events and metrics are in their catalogues.
- [ ] UI work: loading/empty/error states, permission gating, i18n strings, axe-clean Playwright test.
- [ ] Coverage gates met ([testing-strategy §8](docs/08-quality/testing-strategy.md#8-coverage-and-gates)); performance-sensitive paths within [budgets](docs/08-quality/performance-budgets.md).
- [ ] Docs updated (spec deviations fixed in the spec; decisions in open-questions).
- [ ] `docs/09-plan/progress.md` updated with `done` and the commit sha.

## When you are blocked

- A dependency (service, model endpoint) is unavailable locally → start the real one (`make up`, a real model endpoint). A unit or integration test may use testcontainers and the stand-ins in `ar_testing`. A run of the product never does (strict rules 1 and 2).
- A version pin does not resolve → choose the nearest stable release, update [stack.md](docs/stack.md), and note it in OQ-15.
- Two documents disagree → the more specific spec wins over overview/plan text; fix the other document in the same PR and log it in open-questions.
