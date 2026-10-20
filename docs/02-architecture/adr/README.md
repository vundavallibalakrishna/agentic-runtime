# Architecture decision records

Format: context, decision, consequences, alternatives. Status of all records below: **Accepted** (2026-10-20). New ADRs take the next number; superseded ADRs are kept and marked.

| ADR | Title |
|---|---|
| [ADR-0001](ADR-0001-modular-monolith.md) | Modular monolith with several deployables |
| [ADR-0002](ADR-0002-monorepo-python-typescript.md) | Monorepo with uv (Python) and pnpm + Turborepo (TypeScript) |
| [ADR-0003](ADR-0003-temporal-durable-runs.md) | Temporal for durable agent runs and background work |
| [ADR-0004](ADR-0004-custom-agent-loop.md) | Custom, thin agent loop instead of an agent framework |
| [ADR-0005](ADR-0005-thin-model-gateway.md) | In-house thin OpenAI-compatible model gateway |
| [ADR-0006](ADR-0006-mcp-tool-protocol.md) | MCP (2026-07-28) as the only tool protocol; single gateway |
| [ADR-0007](ADR-0007-opa-policy-engine.md) | OPA for tool-call policy with data-driven tenant rules; RBAC in Python |
| [ADR-0008](ADR-0008-shared-schema-rls.md) | Shared-schema multi-tenancy with Postgres RLS; dedicated DB option |
| [ADR-0009](ADR-0009-retrieval-stores.md) | Postgres + pgvector as the default retrieval store behind a `RetrievalStore` port; Qdrant optional adapter (revised 2026-10-20) |
| [ADR-0010](ADR-0010-streaming-and-events.md) | Valkey streams for run events, transactional outbox for domain events; no Kafka in v1 |
| [ADR-0011](ADR-0011-identity-keycloak-bff.md) | Keycloak (Organizations) as identity broker; BFF session for the web app |
| [ADR-0012](ADR-0012-secrets-backend.md) | OpenBao/Vault for secrets with an envelope-encrypted DB fallback |
| [ADR-0013](ADR-0013-sandbox-isolation.md) | gVisor (default) / Kata sandboxes on Kubernetes; Docker driver for dev |
| [ADR-0014](ADR-0014-object-storage.md) | S3-compatible object storage; SeaweedFS as the bundled default |
| [ADR-0015](ADR-0015-approval-args-hash.md) | Approvals bound to an RFC 8785 (JCS) hash of tool version + arguments |
| [ADR-0016](ADR-0016-single-codebase-deployment-modes.md) | One codebase for SaaS and single-tenant installs |
| [ADR-0017](ADR-0017-openapi-first-codegen.md) | FastAPI-generated OpenAPI as the contract; generated TS and Python clients |
| [ADR-0018](ADR-0018-declarative-definitions.md) | Declarative, versioned YAML/JSON definitions for agents and other resources |
| [ADR-0019](ADR-0019-sse-streaming.md) | Server-Sent Events for client streaming |
| [ADR-0020](ADR-0020-ids-pagination-errors.md) | UUIDv7 ids, signed cursor pagination, RFC 9457 errors |
| [ADR-0021](ADR-0021-evidence-immutability.md) | Evidence objects are immutable, hashed, signed and locked |
| [ADR-0022](ADR-0022-run-records.md) | Run records are sealed recordings, not bit-reproducible regeneration |
| [ADR-0023](ADR-0023-pack-extensions.md) | Solution packs use public extension points and a separate Alembic history |
| [ADR-0024](ADR-0024-guest-principals.md) | External participants are guest principals, not users |
| [ADR-0025](ADR-0025-output-signoff.md) | Sign-off binds a statement and a content hash, separate from tool-call approval |
| [ADR-0026](ADR-0026-public-json-camel-case.md) | Public JSON is camelCase |
