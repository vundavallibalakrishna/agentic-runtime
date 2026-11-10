# Architecture for someone starting the product

This page is the map of the system a customer runs. The normative detail stays in [docs/02-architecture](../02-architecture/README.md) and the component specs. The original long-form document is `agentic-runtime-architecture.pdf` in this folder. Where that PDF and the specification disagree, the specification wins. The industry pack described in older copies of the PDF is not part of the product.

## What you run

| Piece | Role |
|---|---|
| Web app | Chat-first UI. Next.js, production build with `next start`. It proxies `/api` and `/v1` to the API. |
| API | Sessions, agents, tools, documents, knowledge, connectors, approvals, and the public `/v1` surface. |
| Model gateway | Forwards chat completions to the provider the tenant registered. A `fake-*` model stays on the local fake. |
| Runtime worker | Temporal worker for turns when `AR_TEMPORAL_ADDRESS` points at a live server. If Temporal is down, the API finishes the turn in process. |
| Postgres | System of record, including pgvector for knowledge. Every tenant table has row-level security. |
| Valkey | Cache and rate buckets when the process is configured to use it. |
| Temporal | Durable schedules and runs when the workers are polling. |
| Object storage | Uploaded file bytes (SeaweedFS in the local compose stack). |

Local ports and the `make dev` path are in [local development](../07-ops/local-dev.md).

## How a request moves

1. A person signs in with email and password (`POST /api/v1/auth/login`) and lands on Chat. That is the dev and single-tenant door. Production OIDC is not this build (Stage 3).
2. The tenant registers an OpenAI-compatible provider. The API key is sealed in `encrypted_secrets`. Later reads return `hasApiKey`, not the key.
3. An agent definition names instructions, a model alias, and tools. Publishing freezes that version.
4. A message starts a run. The model may call tools. Tool results enter the prompt only through the untrusted-content wrapper. A write that the policy marks W2 waits for an approver who is allowed to decide it. The owner of the agent cannot approve that call.
5. A published agent accepts a bearer key on `/v1` (REST, SSE, MCP, A2A). The key is hashed at rest and shown once.

## What is deliberately not in the core

Industry catalogues, control frameworks, and the old pack routes are gone. `/grc` renders **Page not found**. Approvals and the security audit log stay. Records-as-a-product is not a core feature (Stage 2).

Search stays off until a provider key is set. There is no self-serve signup route. Proof labels are `unit`, `contract`, and `live` ([capability matrix](../09-plan/capability-matrix.md)). See [open questions](../open-questions.md).
