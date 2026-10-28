# M21 — Operator workflows

Goal: a person can create and manage GRC records from the web UI, and the default assistant can call a tool, pause for approval, and refuse to claim an action that never ran. The certification addendum records what a real `Qwen/Qwen3-32B` run actually did.

Exit criteria: the workflow and audit screens create the records listed in OQ-54 without a dev installer. A browser session connects an account, sees an approval, and approves or rejects it. `docs/testing/m21-certification-addendum.md` states pass or fail for each affected scenario.

**Depends on:** M20 exit.

**Spec:** [principles](../00-overview/principles.md), [ux-quality](../08-quality/ux-quality.md), [design-system](../08-quality/design-system.md), [spec 08](../03-specs/08-tool-registry-mcp.md), [spec 09](../03-specs/09-policy-approvals.md), [OQ-54](../open-questions.md).

## M21-T01 — GRC record forms

**Do:** Workflow and audit screens offer a validated form for each record a person can create through the existing pack API: vendors and assessments, questionnaire upload and answers, policies (draft, submit review, publish), risks, incidents, exceptions and waivers, ethics cases, regulatory feed sources, PBC requests, access-review campaigns, inspections, DSAR, consent, resilience tests, and report generation. Edit, close, or delete only where that API already allows it. Empty lists stay empty until the form is submitted. No new pack tables.

**Done when:** a component test submits a vendor and a PBC request, rejects an empty required field, and still shows the empty state before submit.

**Tests:** `apps/web/src/components/grc/workflow-screen.test.tsx`, `apps/web/src/components/grc/audit-screen.test.tsx`.

## M21-T02 — Tools, connections, and unbacked claims

**Do:** The published assistant may call the tickets tools and `petstore.create_pet`, with a non-zero tool budget. A real model completion includes those tools. A returned tool call runs through the existing pipeline, including approval. Text that claims a ticket was filed or a pet was created is replaced when no tool call was recorded. Connecting a workspace account finishes on the connections screen. Dev user ids on in-memory grants follow the durable id remap. The Temporal v1 loop still does not run tool steps.

**Done when:** a unit test executes a model tool call into an approval pause, rewrites an unbacked claim, and remaps a grant onto the bound user id.

**Tests:** `libs/ar_domain/tests/unit/test_m21_tools.py`, `apps/web/src/components/tools/tools-screen.test.tsx`.

## M21-T03 — Certification addendum

**Do:** Re-run sign-in, model registration, chat, the new GRC forms, a tool call, a connection, and an approval with `Qwen/Qwen3-32B`. No mock model and no GRC seed rows. Capture light and dark, desktop and mobile, and a walkthrough. Write `docs/testing/m21-certification-addendum.md` and `docs/testing/m21-checklist.md`. Separate platform defects from model limits. Leave durable GRC storage, the document-review agent, the soak, and live Slack, Teams, and a customer IdP as recorded conditions.

**Done when:** the addendum states one result per scenario that was run and does not claim a scenario that was not run.

## How to test visually

1. `make up && make migrate && uv run alembic -c packs/grc/alembic.ini upgrade head && make seed`, then `uv run honcho start -f Procfile.dev`. Use free host ports when 5432, 6379, 7233, 8000, 8001, or 8013 are taken. Set `AR_GRC_DEMO=0` when the workflow lists should start empty; catalogues still install.
2. Sign in as `admin@dev.local` (password `dev-password`, or the dev sign-in button).
3. Open **Admin → Models**, switch to Advanced, and register `https://api.deepinfra.com/v1/openai` with upstream model `Qwen/Qwen3-32B`. The key field is empty after save.
4. Open each GRC workflow and audit screen. The list is empty until you submit the form. Create one record, edit it where the screen offers edit, and confirm the row appears.
5. Open **Connections**, connect Tickets, and finish with the workspace code. In Chat, ask the assistant to file a ticket and to create a pet. Approve one request in **Approvals** and reject another. The transcript does not say the action is done unless a tool call is shown.
