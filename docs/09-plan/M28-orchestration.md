# M28 — Orchestration

Depends on M26. A customer connects their own model, lets one agent call others, watches the run tree, schedules work, and answers a question that unblocks a run. Connector batch two is M27 and does not block this milestone.

The GRC pack stays parked. This milestone does not import it and does not change its migrations.

## M28-T01 Agent calls

**Spec:** [m28-orchestration](../06-security/m28-orchestration.md), [definition schema](../05-contracts/definition-schema.md).

**Do:**

- An agent definition lists the agents it may call. Each callee has a name, description, and input and output schema.
- The live model can call one agent, call several in parallel and combine the answers, or hand the conversation to another agent.
- Depth, fan-out, and the parent cost and time budget include children. A cycle is rejected. A child failure is a tool error the parent can recover from.
- A child that exceeds `childTimeoutS` (default 45 seconds) is cancelled, marked failed with `child_timeout`, and is not retried.

**Done when:** a parent run shows child runs, a failed child does not abort the parent by itself, and a recursive call stops on depth or budget.

**Tests:** `libs/ar_domain/tests/unit/test_m28_orchestration.py`.

## M28-T02 Durable runs

**Spec:** [OQ-59](../open-questions.md).

**Do:**

- Revision 0029 stores a run checkpoint, a workspace reference, and human questions.
- Tool-call rows, policies, approvals, approval decisions, and sandbox rows flush to the tables that already exist.
- A run left `running` when the API process stops is marked failed with `interrupted`. A run waiting on a person stays waiting and can be answered after restart.

**Done when:** a new process sees the same tool call, approval, policy, sandbox reference, and paused question.

**Tests:** `test_m28_orchestration.py`.

## M28-T03 Schedules, questions, and screens

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- A schedule uses cron in a time zone. A webhook is signed and the secret is shown once. The same delivery does not start two runs.
- While a previous run is still going, the default is skip, with a recorded message. Queue keeps one run and starts it when the current one finishes.
- A run can pause for a question or an approval. The requester cannot approve their own request. The inbox lists what is waiting, and the answer resumes the run.
- Screens: runs with the tree, duration, cost, and an open step; schedules; inbox; the agent editor selects callable agents.

**Done when:** Playwright captures the new screens in light and dark at desktop and mobile widths.

**Tests:** `apps/web/e2e/m28-orchestration.spec.ts`, `apps/web/src/components/schedules/schedules-screen.test.tsx`.

## Out of scope

Documents and knowledge beyond what M24 and M25 already shipped. Exposing an agent as an API or MCP server (M29). Connector batch two is M27.
