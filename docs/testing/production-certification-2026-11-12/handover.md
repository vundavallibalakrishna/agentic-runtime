# Handover: what to develop and what to test before production certification

Written 12 November 2026 for whoever takes this work next, person or coding agent. It lists what must be built and what must be tested before Agentic Runtime can be certified for production. Speed is out of scope: the owner treats the model as replaceable.

The target the owner set: a working platform with no known issue, on which any agent can be built. That means two things. Every rule in [AGENTS.md](../../../AGENTS.md) holds in the running product. Every capability is proven on the real product, with a real database and a real model, not by a unit test.

## Where things stand

- The platform is **not certified**. The certification report says so: [report](../production-certification-2026-11-11/report.md).
- Pull request 179 is merged into `main` (commit `bd3f4edf`).
- Pull request 180 is open on branch `fix/document-answers` with all 21 checks passing. It is not merged. Merging is the owner's decision.
- Last live results:
  - Document flows: 47 of 47 checks ([report](../../../packs/examples/grc-flows/report-2026-11-12.md)).
  - Built-in tools: 67 of 81 pass, 11 blocked on setup, none fail.
  - Certification flows: 13 of 14 in one full run, the fourteenth after its fix.
- Open items already recorded: [OQ-131 to OQ-136](../../open-questions.md).

## How to read this document

Each item says how sure the finding is.

- **Checked**: the author read the code or ran it.
- **Reported**: a read-only research pass found it in the code and gave a path and line. Nobody ran it. Confirm it before you fix it.

Strict rule 10 applies: do not call anything done, missing or broken without checking the code or running it.

## Part 1. What to develop

Do these in order. Groups A and B need nothing from the owner.

### A. Rule breaks in the product code

These break the strict rules on shared state, tenant isolation, audit and static data. Fix them first, because everything else is tested on top of them.

| # | Finding | Where | Level |
|---|---|---|---|
| A1 | Secrets, webhooks, notifications and platform tenants and plans are held in the API process's memory in every environment. The secret store has no tenant filter, so a list returns every tenant's entries. Data is lost on restart and differs between replicas. | `services/api/src/ar_api/main.py:426`, `services/api/src/ar_api/secrets_runtime.py` | Checked |
| A2 | The routes over those stores write no audit record. | `routers/secrets.py`, `webhooks.py`, `platform_tenants.py`, `platform_plans.py` | Reported |
| A3 | The channels screen sends fixed values: Slack signing secret `demo-signing-secret`, Teams app id `app`, email username `agent`. A real Slack integration cannot verify its requests. | `apps/web/src/components/channels/channels-screen.tsx:98` | Checked |
| A4 | Three routes write to the long-lived process store, not the request's database unit, so named secrets and push subscriptions are never saved. | `routers/secrets.py:111`, `routers/notifications.py:57` and `:74` | Reported |
| A5 | A run that waits on a person resumes as a background task in the API process. The Temporal resume is not built: `ApprovalWaitWorkflow` is registered and never started. | `chat/service.py:1777`, OQ-133 | Reported |
| A6 | Eval runs execute as a background task in the API process, and their later writes look unsaved in production mode. | `evals/book.py:270` | Reported, not run |
| A7 | `POST /api/v1/runs/{id}:resume` marks the run running and starts nothing. | `routers/m2.py:1030` | Reported |
| A8 | Browser sign-ins have no table and are lost after each request. | `sandboxes/browser_auth.py:35`, OQ-119 | Reported |
| A9 | Quota counters fall back to process memory when Valkey errors. | `usage/quotas.py:205` | Reported |
| A10 | The development seed has no environment check. It creates tenant `dev`, users with a fixed password and a fake model provider. | `libs/ar_domain/src/ar_domain/seed/__init__.py:15` | Reported |
| A11 | A provider of kind `fake` can be created in any environment. The Helm chart does not refuse `fakeLlm.enabled` in production. | `chat/service.py:548`, `deploy/helm/agentic-runtime/values.yaml:328` | Reported |
| A12 | A model name `fake-chat` is fixed in token counting, and a model fallback uses the demo tenant id when no tenant is given. | `memory/compaction.py:135`, `chat/service.py:2177` | Reported |
| A13 | Staging differs from production: staging serves the API documents without sign-in, and a malformed session key is fatal only in production. | `services/api/src/ar_api/main.py:282` and `:372` | Reported |
| A14 | The `@expose` permission marker has no checker. An automated scan found 74 of 470 routes without `require_permission`; most use another guard, and the notification routes have only sign-in. | `services/api/src/ar_api/deps.py:26` | Reported |
| A15 | The row-level-security test does not check that security is forced, though the data spec says it does. | `libs/ar_domain/tests/integration/test_rls.py:28`, `docs/04-data/rls.md` | Reported |

What done looks like for group A: each store is a table with `tenant_id`, row-level security and an audit write, read through a repository; nothing a customer sees is fixed in code; staging and production run the same code paths; a test fails when a route has no permission.

### B. Known defects

From the certification report's open list and OQ-132 to OQ-136. All are recorded there with their evidence.

1. A Valkey timeout on the session read returns HTTP 500.
2. Rows filled in after they are assigned lose writes. The tree has not been swept for other cases.
3. `sandboxes/service.py` and `identity/data_rights.py` write file bytes into process memory.
4. Running the tenant seed by hand in staging mode stops with an error unless `AR_BOOTSTRAP_WRITER=1`.
5. Deleting the last file in a turn does not stick.
6. The tool detail API shows camelCase parameter names where the tools take snake_case.
7. A refused boot is logged as `temporal_unavailable` and retried without end.
8. The data connection address defaults to `memory://warehouse`.
9. A knowledge document created through a collection reads back as `pending`.
10. In dev mode a turn longer than about a minute shows as stuck.
11. A replayed tool call returns a preview and no structured result.
12. Eval conversations appear in the recent chats of the person who started the eval.
13. A long tool shows no card in chat until it ends, because `tool_call.started` is stored when the step commits (OQ-136).
14. The document library has no delete (OQ-134).
15. Sums written between dollar signs show as plain text, and the chat column is squeezed at narrow widths.
16. Sandbox, from OQ-132: suspend does not stop a container; the docker driver does not confine the network and a clicked link is not checked against the allowed hosts; the whole run folder is copied into the container on each call and deletions there are not carried back; the sandbox manager routes carry no service token; the computer panel lists a host folder, so it shows no files for a container.
17. `scripts/eval_run.py` is a contract check with a stubbed model, not a real evaluation.
18. Research matches by words and its report is not written by the model.

Already fixed, though the certification report still lists it: built-in tool text now follows the running release (pull request 180, `refresh_builtins`). Update the report when you next touch it.

### C. Not built

- Temporal approval resume (item A5).
- Sandbox suspend and restore: the agent's snapshot and restore endpoints are not called.
- Document library delete (item B14).
- A2A push.
- A web end-to-end suite that runs on the real product (see Part 2, section 1).
- Stages 15 to 20 in [next-milestones](../../09-plan/next-milestones/README.md) have no progress row. They are future features, not certification blockers, unless the owner says otherwise.

## Part 2. What to test

A capability counts as proven only when it runs from an empty database, through sign-in and the screens, with a real model (strict rule 4).

### 1. The screens on the real product

All 45 specs in `apps/web/e2e/` run on a demo tenant with no database and a scripted model (`apps/web/playwright.config.ts:21`). The only screen testing on the real product so far was done by hand in a browser. Build a suite that signs in on a production-mode stack and walks every screen, then keep it in CI.

The by-hand method that works today is in the [certification report](../production-certification-2026-11-11/report.md), section "Using the app as a person".

### 2. Capabilities with no live proof

| Capability | Proof today | What a live proof needs |
|---|---|---|
| Inbound Slack, Teams and email | Scripted model, Slack stubbed | Real workspaces and a mailbox |
| Connectors, 20 of 22, and their OAuth flows | Unit or contract | A real account or token for each |
| 11 blocked built-in tools | Not run | See the setup list below |
| Packs and the extension framework | Unit tests | Install a signed pack on the running product |
| Sign-in with a real identity provider | Mock provider | A real provider |
| Routines triggered by polling or a channel | Not run | A source to poll and a channel |
| Red-team suite, 150 cases in `evals/gym/redteam/cases.yaml` | Stubbed model only | One run against the real model |
| Cross-tenant isolation | Integration test | Two tenants on the running product, each trying to read the other's data |
| Cloud OCR engines | Not run | Provider keys |

### 3. Capabilities to run again on the production-mode path

These were run live before the current worker and per-request database path existed: sub-agents and orchestration, schedule and webhook triggers, human input, and REST, MCP and A2A exposure. Run them again on a production-mode stack.

### 4. Cluster and operations

Nothing here has run on a real cluster.

- A Helm install with two API replicas, then the full certification on it. The production plan's exit test is this run.
- The Kubernetes sandbox driver with gVisor isolation. It is covered by unit tests only.
- An upgrade from one chart release to the next. No job does this.
- A live point-in-time restore drill. The existing proof is a contract test.
- The runbooks in `docs/07-ops/runbooks.md`. No job exercises them.
- `gitleaks`, `pip-audit` and the nightly supply-chain step, which today only prints versions.

### 5. Regression runs that must stay green

- `scripts/tool_certification.py`: every built-in tool and the 14 flows. Run the whole script again; it was not re-run after the last image fix.
- `packs/examples/grc-flows/scripts/grc_proof.py`: the eight document flows.
- `scripts/certify_live.sh`: never run in full.
- The capability matrix (`docs/09-plan/capability-matrix.md`) still labels chat and every built-in tool as unit-proven. Regenerate it from recorded live runs once they exist.

## Part 3. What the owner must supply

Nothing in sections 2 and 4 of Part 2 can finish without these.

- A web search provider key, for `general.search` and research.
- A vision model on the `vision` alias, for `image.ask`.
- The hosts to allow, for `general.fetch`, `general.http` and the browser tools.
- A test page with a form, a file input and a download link (`AR_CERT_FORM_URL`).
- Test accounts or tokens for each connector and channel to be certified.
- A Kubernetes cluster, or agreement that a local kind cluster stands in for it.
- A real identity provider, if sign-in through one is to be certified.
- A decision on which connectors are in scope. Certifying all 22 needs 22 accounts.

## Suggested order

1. Group A, the rule breaks. One pull request per coherent set: the in-memory stores (A1, A2, A4), the channels screen (A3), run resume on Temporal (A5 to A7), then the rest.
2. Group B, the known defects.
3. The real-product screen suite, then every capability in Part 2 section 3 again.
4. Part 2 sections 2 and 4 as the owner supplies what Part 3 lists.
5. A final full run of all three scripts on the cluster, then update the certification report and the capability matrix.

## Working notes for the next person

- Work in a git worktree under `.claude/worktrees/`, on a fresh branch from `origin/main`. Never use a bare `git stash`.
- Do not commit `apps/web/AGENTS.md`, `apps/web/next-env.d.ts` or `var/`. `var/staging.env` holds secrets.
- Do not touch Postgres on 5432, Redis and Temporal on 6379 and 7233, or the applications on 8000, 8010 and 8013. They belong to other work on this machine.
- The production-mode stack runs with `honcho start -e var/staging.env -f var/Procfile.staging`: API on 18010, web on 3000, sandbox manager on 8003. Sign in as `admin@dev.local`.
- Read the model key from `AR_LLM_API_KEY`. Never print or log it.
- Local checks need `UV_NO_SYNC=1 UV_OFFLINE=1` and `uv run --no-sync`. Three tests fail locally for reasons that are not defects: two need Qdrant, one reads a port from `.env`.
- Keep industry content out of core. The GRC material in `packs/examples/grc-flows/` is test data only.
