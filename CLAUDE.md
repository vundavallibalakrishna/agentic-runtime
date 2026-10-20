<!-- Generated from AGENTS.md by scripts/sync_agent_docs.py. Edit AGENTS.md, then run make gen. -->

# AGENTS.md — instructions for implementers

You are building **Agentic Runtime** from this specification. Follow this file exactly. When anything here conflicts with a lower-level document, this file wins for *process*; the specs win for *behaviour*.

## Non-negotiable principles

Full text: [docs/00-overview/principles.md](docs/00-overview/principles.md). The goals are **CLEAN CODE**, **CUSTOMISABLE**, **EXTENSIBLE**, **SIMPLE UI/UX**, **OUTSTANDING PRESENTATION**.

1. **camelCase on the wire.** Public JSON (REST, SSE, webhooks, definition files the UI shows) uses camelCase properties. Python stays snake_case via `ar_contracts.api_model.ApiModel` (`alias_generator=to_camel`, `populate_by_name=True`, `serialize_by_alias=True`). Database columns and env vars are unchanged. CI runs `scripts/check_public_camel_case.py`. Apply this on M1 response models ([M1-T16](docs/09-plan/M01-foundation.md)); do not wait.
2. **Demo-grade UI.** The primary create-agent path is a natural-language instruction handled by the built-in `builder` agent, with a reviewable preview and a form/YAML escape hatch. Empty, loading, and error states are mandatory. Bar: [ux-quality](docs/08-quality/ux-quality.md).
3. **No industry in core.** Evidence, sign-off, segregation of duties, legal hold, retention, the AI register, external participants, and binders are generic. GRC words live only under `docs/10-grc-pack/` and `packs/grc`. New capabilities are packs or connector plugins ([extension-framework](docs/05-contracts/extension-framework.md)).
4. **The GRC pack answers the client's GRC ask.** Coverage and deliberate cuts: [use-cases](docs/10-grc-pack/use-cases.md).
5. **Defaults.** A tenant works after secrets and identity. Every other setting has a default. Settings UI has Simple and Advanced modes.
6. **North star.** A corporate assistant with its own computer, in the customer's environment, able to automate any work ([vision](docs/00-overview/vision.md)).

## Read order

Before your first task, read in this order (≈ 1 hour):
1. [README.md](README.md) — what the product is.
2. [docs/00-overview/vision.md](docs/00-overview/vision.md), [principles](docs/00-overview/principles.md), [glossary](docs/00-overview/glossary.md), [scope](docs/00-overview/scope.md), [deployment-modes](docs/00-overview/deployment-modes.md).
3. [docs/02-architecture/system-context.md](docs/02-architecture/system-context.md), [service-decomposition.md](docs/02-architecture/service-decomposition.md), [request-flows.md](docs/02-architecture/request-flows.md), [tenancy-isolation.md](docs/02-architecture/tenancy-isolation.md), the [ADR index](docs/02-architecture/adr/README.md).
4. [docs/stack.md](docs/stack.md) and [docs/08-quality/coding-standards-python.md](docs/08-quality/coding-standards-python.md), [coding-standards-typescript.md](docs/08-quality/coding-standards-typescript.md), [testing-strategy.md](docs/08-quality/testing-strategy.md).
5. [docs/05-contracts/api-conventions.md](docs/05-contracts/api-conventions.md) and [docs/04-data/rls.md](docs/04-data/rls.md).
6. [docs/09-plan/README.md](docs/09-plan/README.md).

For each task, additionally read every document in the task's **Spec** line, the relevant [PRD](docs/01-prd/README.md) stories, and the security documents it touches ([docs/06-security](docs/06-security/)).

## How to pick the next task

1. Open `docs/09-plan/progress.md` (created by M0-T01). Tasks marked `done` are complete.
2. Take the **lowest-numbered milestone** that has unfinished tasks; within it, the lowest-numbered task whose **Depends on** tasks are all `done`. Never start a task with unfinished dependencies; never skip ahead to a later milestone while an earlier one is unfinished (milestone exit criteria are implicit dependencies). Two exceptions: M13-T07 waits for M14-T08 and is not an M13 exit task. M16 may start after M14-T13 while M15 is unfinished. Do not implement guest tables or records tables in M1; those land in M14. Do apply camelCase ([M1-T16](docs/09-plan/M01-foundation.md)) while writing M1 API models.
3. Mark it `in_progress` in `progress.md` (`M2-T05 | in_progress | - | <date>`), do the work, then mark it `done` with the commit sha. One task per pull request unless a task explicitly says otherwise.
4. If a task is too big for one PR, split it as `M{n}-T{nn}a`, `…b` in the milestone file (never renumber existing tasks) and record the split in `progress.md`.
5. At the end of a milestone, run the milestone's exit criteria and demo script ([plan README](docs/09-plan/README.md#vertical-slices-and-demo-checkpoints)) and record the result in `progress.md`.

## Conventions

- **Names are fixed**: services, packages, tables, columns, endpoints, events, permissions, audit actions, metrics and env vars are exactly as written in the specs. Do not rename, pluralise differently or add synonyms. If you need a new name, add it to the owning spec and to the relevant catalogue in the same PR ([environments §3](docs/07-ops/environments.md#3-variable-catalogue), [audit §3](docs/06-security/audit.md#3-catalogue), [authn-authz §3](docs/06-security/authn-authz.md#3-permission-catalogue), [domain-events](docs/05-contracts/domain-events.md), [stream-events](docs/05-contracts/stream-events.md), [api-catalogue](docs/05-contracts/api-catalogue.md)).
- **Layering**: services never import each other; DB access only through `ar_domain` repositories inside a unit of work with tenant context ([coding-standards-python §2–3](docs/08-quality/coding-standards-python.md#2-ruff-and-lint-configuration)).
- **Contracts first**: cross-process models live in `ar_contracts`; the OpenAPI document and TS client are generated (`make gen`), never hand-written.
- **Commits**: Conventional Commits with the task id in the body (`Task: M4-T03`).
- **Docs move with code**: if implementation reveals a spec gap, update the spec in the same PR and, if it is a decision, add an entry to [open-questions](docs/open-questions.md) with the default you applied.
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

A task is done when **all** of the following hold:
- [ ] Every bullet of the task's **Do** is implemented and every **Done when** criterion is demonstrably met.
- [ ] The task's **Tests** exist and pass; `make check` and `make test` pass locally; all required CI jobs are green ([ci-cd §2](docs/07-ops/ci-cd.md#2-jobs)).
- [ ] Never-skip rules above are satisfied (isolation test, permission, audit, wrapping, telemetry hygiene, secrets).
- [ ] New endpoints appear in `openapi.json`, the generated clients, and match the [api-catalogue](docs/05-contracts/api-catalogue.md); new env vars, audit actions, permissions, events and metrics are in their catalogues.
- [ ] UI work: loading/empty/error states, permission gating, i18n strings, axe-clean Playwright test.
- [ ] Coverage gates met ([testing-strategy §8](docs/08-quality/testing-strategy.md#8-coverage-and-gates)); performance-sensitive paths within [budgets](docs/08-quality/performance-budgets.md).
- [ ] Docs updated (spec deviations fixed in the spec; decisions in open-questions).
- [ ] `docs/09-plan/progress.md` updated with `done` and the commit sha.

## When you are blocked

- A dependency (service, model endpoint) is unavailable locally → use `fake-llm`, testcontainers or the test MCP servers from `ar_testing`.
- A version pin does not resolve → follow M0-T02 (choose the nearest stable release, update stack.md, note it in OQ-15).
- Two documents disagree → the more specific spec wins over overview/plan text; fix the other document in the same PR and log it in open-questions.
