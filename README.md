# Agentic Runtime

A self-hosted, chat-first agentic platform, designed and built by Balakrishna Vundavalli. A customer connects their own OpenAI-compatible model, defines agents, and gives them tools: sandboxed Python and shell, workspace files, page fetch, web search, and HTTP. Agents can use documents, knowledge bases, memory, skills, and connectors. They plan, act, check, and retry. A parent agent can hand work to other agents, run them in parallel, wait for a person, or fire on a schedule or a signed webhook. A published agent is callable from outside over REST `/v1`, MCP, and A2A.

The industry pack that used to live in this repository was removed. A fresh tenant does not see it.

The specification set under `docs/` is still the behaviour contract. [AGENTS.md](AGENTS.md) is for people and coding agents changing the code, and `CLAUDE.md` is generated from it. A customer can start from the quick start below. The record of the final pass is [the M31 certification](docs/testing/m31-certification.md).

## Stack at a glance

| Layer | Choice |
|---|---|
| Backend | Python 3.14, FastAPI, uv workspace, Pydantic v2, SQLAlchemy 2 (async) + Alembic |
| Data | PostgreSQL 18 + pgvector (system of record and default retrieval store for knowledge, memory and tool search), Valkey, S3-compatible object storage; Qdrant optional retrieval backend |
| Orchestration | Temporal (durable agent runs, routines, ingestion) |
| Tools | Model Context Protocol (MCP) via `mcp-gateway`; OPA policies |
| Identity | Keycloak (Organizations) with BFF sessions, SCIM 2.0 |
| Frontend | Next.js (App Router), React, Tailwind CSS, shadcn/ui, TanStack Query |
| Observability | OpenTelemetry, Prometheus, Tempo, Loki, Grafana, Langfuse |
| Deployment | Docker Compose (dev), Helm chart on Kubernetes (staging/prod), gVisor sandboxes |

Exact versions: [docs/stack.md](docs/stack.md). Decisions: [ADRs](docs/02-architecture/adr/README.md).

## Documentation map

| Folder | What it contains |
|---|---|
| [docs/00-overview](docs/00-overview/) | Vision and goals, glossary, personas, scope and non-goals, deployment modes |
| [docs/01-prd](docs/01-prd/README.md) | 125 user stories with acceptance criteria across 15 product areas |
| [docs/02-architecture](docs/02-architecture/README.md) | System context, service decomposition, request flows, tenancy and isolation, ADRs |
| [docs/03-specs](docs/03-specs/) | 21 component specifications (normative behaviour, endpoints, workflows, failure modes, tests) |
| [docs/04-data](docs/04-data/) | Database schema (97 core tables), ER diagrams, row-level security, migration plan |
| [docs/05-contracts](docs/05-contracts/) | API conventions and [catalogue](docs/05-contracts/api-catalogue.md), definition schemas, stream and domain events, internal APIs, MCP integration, connector SDK |
| [docs/06-security](docs/06-security/) | Threat model, authentication and RBAC, secrets, prompt-injection defences, DPDP data protection, audit catalogue |
| [docs/07-ops](docs/07-ops/) | Local development, environments and configuration, CI/CD, Helm/Kubernetes, scaling, backup/DR, runbooks |
| [docs/08-quality](docs/08-quality/) | Python and TypeScript standards, testing strategy, evaluation strategy, performance budgets |
| [docs/09-plan](docs/09-plan/README.md) | **The build plan**: milestones and ordered tasks with dependencies and acceptance criteria |
| [docs/open-questions.md](docs/open-questions.md) | Undecided points, each with the default to apply now |

How the running system fits together: [docs/architecture/README.md](docs/architecture/README.md). The original architecture document is kept as `docs/architecture/agentic-runtime-architecture.docx` / `.pdf` (reference only; the specification set supersedes it where they differ).

## Quick start

```bash
make bootstrap   # install toolchains and dependencies, generate dev keys
make dev         # Postgres, Valkey, Temporal, Keycloak, API, workers, and the web app
open http://localhost:3000
```

Sign in as `admin@dev.local`. On a laptop the password for Keycloak is `dev-password`, and the sign-in page also lists the seeded roles for dev login. Chat is the first screen. `make seed` inserts the dev tenant, four users, a local `fake-llm` provider, and the built-in assistants. It does not insert sample conversations.

Connect the model you actually want to use:

1. Open **Models**, switch to **Advanced**, and choose **OpenAI-compatible**.
2. Set the base URL (for DeepInfra, `https://api.deepinfra.com/v1/openai`) and the upstream model id (for example `Qwen/Qwen3-32B`).
3. Paste the API key and choose **Register and test**. The key is stored as a secret. The page shows **Key stored** and a short sample. It does not show the key again.

Point the tenant `reasoning` alias at that model if the form did not do it. New agents use that alias. Embeddings for a knowledge base use a registered model of kind `embedding` (the certification used `BAAI/bge-m3` on the same base URL).

If the web app is not on port 3000, set `AR_WEB_HOST_PORT` to that port before the API starts. The API checks the browser `Origin` against `AR_PUBLIC_URL`, and that URL follows the web port. A mismatch fails CSRF on every save.

Production UI for a certification or a demo:

```bash
# from apps/web, after the API is listening
API_PROXY_URL=http://127.0.0.1:8000 pnpm exec next build
API_PROXY_URL=http://127.0.0.1:8000 pnpm exec next start --port 3000
```

`API_PROXY_URL` is read when the production server starts. The dev server is `pnpm --filter @ar/web dev`.

Kubernetes install (Helm 4.3, chart `deploy/helm/agentic-runtime` 1.0.0):

```bash
helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  -n agentic-runtime --create-namespace \
  -f deploy/helm/agentic-runtime/values-small.yaml
```

See [Helm and Kubernetes](docs/07-ops/helm-k8s.md) and the [M15 checklist](docs/testing/m15-checklist.md).

Details: [docs/07-ops/local-dev.md](docs/07-ops/local-dev.md).

## What a tenant can do

- Chat with an agent that calls tools, recovers from a failed call, and shows the trace.
- Run sandboxed Python and shell, read and write workspace files, fetch a page, and call HTTP. A POST waits for a person who is allowed to approve it.
- Upload a document, read its outline, and ask for a summary or a check with page anchors. A compare and a rewrite stay proposed until someone accepts them.
- Build a knowledge base, keep memory, and load a skill when the request matches its description.
- Install a connector. GitHub can be used live. Connectors without credentials stay labelled **Not live-tested**.
- Orchestrate child agents, pause for an inbox answer, and fire a schedule or a signed webhook.
- Publish an agent and call it with a key over `/v1`, MCP, and A2A.

Details and the observed output of the final pass: [docs/testing/m31-certification.md](docs/testing/m31-certification.md).

## Repository layout

See [service-decomposition §4](docs/02-architecture/service-decomposition.md#4-repository-layout): `apps/web`, `packages/*`, `libs/ar_*`, `services/*`, `connectors/*`, `policies/`, `images/`, `deploy/`, `evals/`, `scripts/`.

## Licence and naming

Product name in code and docs: **Agentic Runtime** (prefix `ar` / `AR_`). The platform is generic; no customer- or vendor-specific branding.
