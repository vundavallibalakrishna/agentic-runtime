# M20 certification checklist

This is the operator run, not a fake-llm click-through. Chat uses a provider registered in **Admin → Models**. The certification run used DeepInfra's OpenAI-compatible API and `Qwen/Qwen3-32B`. The API key is pasted into the model form. It is not an environment variable the gateway reads, and it is not printed back by the API.

Dev login and the seeded tenant still come from `make seed`. The GRC dev installer also writes demo workflow rows when the API starts. Those rows are called out in the [report](m20-certification-report.md). Do not add a second seed script to fill empty screens.

## Start

```bash
make bootstrap
make ports-check
make up
make migrate
uv run alembic -c packs/grc/alembic.ini upgrade head
make seed
set -a && . ./.env && set +a
uv run honcho start -f Procfile.dev
```

`make dev` is the same sequence. When 5432, 6379, 7233, 8000, 8001 or 8013 are taken, set the host-port variables in `.env` (or `make dev AUTO_PORTS=1`). Do not stop another project's Postgres, Temporal, Redis, or the processes already bound to those ports.

The certification run used API `18000`, model gateway `18001`, system worker `18013`, web `13000`, Postgres `15432`, Valkey `16379`, Temporal `17233`.

Sign in at `/login` as **Sign in as admin@dev.local**.

## Model

1. Open **Models**. Choose **Advanced**.
2. Choose **OpenAI-compatible**. Set the base URL to `https://api.deepinfra.com/v1/openai` and the upstream model to `Qwen/Qwen3-32B`.
3. Paste the API key and choose **Register and test**. Expect a sample that is the model's words, a latency, and **Key stored**. The key field is empty after submit. The table does not show the key.
4. Open **Chat**. Ask for a one-word reply. Expect that word from the assistant, not a `fake:` echo.

## Product screens

Walk these while signed in, in light and dark, at desktop width and at 390px:

Chat, Agents, New agent, Tools, Connections, Knowledge, Memory, Skills, Routines, Approvals, Reviews, Runs, Models, Users, Policies, Channels, Evaluations, Usage, Quotas, Computers, Assurance, Platform health, Profile.

On **Knowledge**, create a collection and upload a text file. Expect the file name and an indexed state.

On **New agent**, describe an agent and choose **Draft**. Expect a preview and a validation line.

## GRC

Open **GRC** and each tab: Frameworks, Controls, Evidence, Tests, Findings, Connectors, Workflows (Overview, Questionnaires, Vendors, Policies, Risks, Regulatory, Incidents, Exceptions, Ethics), Audit (Requests, Reviews, Reports, Inspections, Privacy, Resilience).

A fresh dev API shows the shipped catalogues and the dev installer's demo rows. A tenant without that installer sees the empty states. The workflow screens do not have create forms (OQ-54).

## What this run does not cover

- The 24 hour soak, a live Slack or Teams workspace, and a customer IdP (OQ-48).
- GRC rows moving off the process store (OQ-49 to OQ-52).
- Gateway circuit breaker, semaphore, traffic split, and mid-stream fallback (OQ-53).
- An approval decision. The Desk agent answers "Connect an account to use this tool" and the inbox stays empty until an account is connected.

Screenshots and the walkthrough are in `docs/testing/m20/`. The verdict is in [m20-certification-report.md](m20-certification-report.md).
