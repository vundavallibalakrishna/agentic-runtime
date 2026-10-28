# M15 visual checklist

Deployment does not add a new screen. Confirm chat still streams, then render the Helm chart.

Seed data is the dev tenant. Sign in as `admin@dev.local`. `fake-llm` answers chat. No model API key.

## Start

```bash
make bootstrap
make dev
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login`.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it.

Chart-only check, without the web app:

```bash
bash scripts/check_helm.sh
bash scripts/dr/restore_drill.sh
```

## Click-through

1. Open `/login`. Expect **Sign in** and the four dev users.
2. Sign in as `admin@dev.local`. Expect the chat heading.
3. Choose **Write something**. Expect a streamed reply from fake-llm. Empty chat, before that click, shows the suggestion buttons. A failed load shows the alert on the thread.
4. Narrow the window to 375 px and switch the theme to dark. The same thread stays readable.
5. Earlier screens stay on Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers, Users, Usage, Quotas, Evaluations, Platform health and Assurance.

## Helm

1. `helm template agentic-runtime deploy/helm/agentic-runtime -f deploy/helm/agentic-runtime/values-small.yaml` includes the migrate Job, bootstrap Job and a CloudNativePG Cluster.
2. The same command with `values-saas.yaml` has no bootstrap Job.
3. `helm template` with `--set bootstrap.adminEmail=` fails.
4. `helm template` with `--set global.env=prod --set sandboxes.driver=docker` fails.

## Deferred

The 24 hour soak, a live Slack or Teams workspace, a customer IdP, and a CloudNativePG point-in-time restore into a second namespace are operator steps (OQ-48).
