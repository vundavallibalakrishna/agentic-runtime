# Agentic Runtime

A self-hosted platform on which a company builds, governs and operates AI agents for its employees — on the company's own infrastructure and models. Builders compose **agents** from instructions, **tools** (MCP servers, internal APIs, databases), **knowledge**, **memory**, **skills**, **subagents** and **sandboxes**; **policies and approvals** keep risky actions under human control; agents are used from the **web app, Slack, Microsoft Teams, email and the API**, on demand or as scheduled **routines**. One codebase runs as a **multi-tenant SaaS** or a **single-tenant Kubernetes / on-prem** install.

This repository currently contains the complete build specification. An implementer (human or AI coding agent) builds the product by following [AGENTS.md](AGENTS.md) and the ordered backlog in [docs/09-plan](docs/09-plan/README.md).

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
| [docs/09-plan](docs/09-plan/README.md) | **The build plan**: 20 milestones, 172 ordered tasks with dependencies and acceptance criteria |
| [docs/10-grc-pack](docs/10-grc-pack/README.md) | GRC solution pack (separate from core) |
| [docs/grc-gap-analysis.md](docs/grc-gap-analysis.md) | Approved GRC fit and gap analysis |
| [docs/open-questions.md](docs/open-questions.md) | Undecided points, each with the default to apply now |

The original architecture document is kept alongside this repository as `docs/architecture/agentic-runtime-architecture.docx` / `.pdf` (reference only; this specification set supersedes it where they differ).

## Quick start

```bash
make bootstrap   # install toolchains and dependencies, generate dev keys
make dev         # start dependencies (compose) and all services with reload
open http://localhost:3000   # sign in as admin@dev.local via dev login
```

Kubernetes install (Helm 4.3, chart `deploy/helm/agentic-runtime` 1.0.0):

```bash
helm upgrade --install agentic-runtime deploy/helm/agentic-runtime \
  -n agentic-runtime --create-namespace \
  -f deploy/helm/agentic-runtime/values-small.yaml
```

See [Helm and Kubernetes](docs/07-ops/helm-k8s.md) and the [M15 checklist](docs/testing/m15-checklist.md).

Details: [docs/07-ops/local-dev.md](docs/07-ops/local-dev.md).

## Repository layout (target)

See [service-decomposition §4](docs/02-architecture/service-decomposition.md#4-repository-layout): `apps/web`, `packages/*`, `libs/ar_*`, `services/*`, `connectors/*`, `policies/`, `images/`, `deploy/`, `evals/`, `scripts/`.

## Licence and naming

Product name in code and docs: **Agentic Runtime** (prefix `ar` / `AR_`). The platform is generic; no customer- or vendor-specific branding.
