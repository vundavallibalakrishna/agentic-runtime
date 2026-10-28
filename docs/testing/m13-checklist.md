# M13 visual checklist

Builders can inspect a run, see workspace operations on Usage, run an evaluation suite, and turn feedback into a case. A publish gate keeps a failing draft unpublished. Platform health lists component probes.

Seed data is the dev tenant. The admin is `admin@dev.local`. Platform suites **Prompt injection** and **Assistant golden** are installed for that tenant. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make dev
make seed
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`. Grafana and Langfuse come up with `make up OBS=1` (Grafana http://localhost:3001, Langfuse http://localhost:3100).

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it.

Earlier screens stay on Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage and Quotas.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open **Usage**. Expect **Operations** with run, helpful and not-helpful counts. A workspace with no runs in range still shows zeroes and "No runs in this range yet." Export CSV still downloads.
3. Open **Evaluations**. Expect **Prompt injection** and **Assistant golden**. An empty library would say "No suites yet."
4. Choose **Run suite** on Prompt injection. Expect each case marked Passed, including tool-output-injection.
5. Create a suite named "Desk check" whose reply must contain `Say hello`. Expect "Case saved." Run it and expect Passed.
6. Open an agent, then **Evaluations**. Expect suites for that agent, or the empty state, and a way back to the agent.
7. Open **Runs** and a run trace. Expect the step bar, the activity list, and trace links when `AR_TRACE_UI_URL` is set. A run with no steps says "This run has no steps to draw."
8. Open **Platform health**. Expect the API status and a component list. A dependency that is not configured reads "Not configured". A failed load shows **Try again**.
9. Narrow to 375px and switch to dark. Usage, evaluations, the run trace and health stay on the same tokens.

## Deferred

M13-T07 (run records, replay, groundedness publish gate) waits for M14-T08. Eval rows stay on the process store until a durable flush bucket is added (OQ-44). The red-team corpus shipped here covers the categories in spec 18 §4.5; the 150-case set in the eval strategy grows with later cases.
