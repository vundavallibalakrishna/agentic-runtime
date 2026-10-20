# Technology stack (pinned)

Versions verified against the public package registries (PyPI, npm, GitHub releases, endoflife.date) on **2026-10-20**. Pin exact versions in lockfiles (`uv.lock`, `pnpm-lock.yaml`); Renovate proposes upgrades weekly (see [07-ops/ci-cd.md](07-ops/ci-cd.md)). "Floor" means the minimum version the code may assume. Exact patch versions below are the ones to put in the lockfile at M0; minor upgrades are allowed when CI is green.

Rules:
- Do not add a dependency that is not in this file without adding a row here (with a reason) in the same PR.
- Never pull a model, image or package from the public internet at runtime in production. Mirrors are listed in [07-ops/environments.md](07-ops/environments.md).

## 1. Languages and runtimes

| Component | Version | Reason |
|---|---|---|
| Python | 3.14.8 | Current stable line with a year of ecosystem maturity; 3.15.0 (released 2026-10-09) is too new for native-extension libraries; has `uuid.uuid7()` built in. |
| Node.js | 24.22.0 LTS ("Krypton") | Active LTS; Node 26 becomes LTS only at the end of October 2026. |
| TypeScript | 7.0.2 | Native (Go) compiler with roughly 10x faster type checks; `next build` supports it through the `tsc` CLI checker by default. Fallback if a tool needs the JS compiler API: alias `typescript` to `@typescript/typescript6@6.0.2` (see [open-questions.md](open-questions.md) OQ-12). |
| SQL | PostgreSQL 18.6 | Built-in `uuidv7()`, async I/O, virtual generated columns; supported to 2030. |

## 2. Python backend

| Library | Version | Reason |
|---|---|---|
| uv | 0.13.3 | Fast resolver, workspaces, lockfile, Python toolchain management in one tool. |
| fastapi | 0.151.0 | Async web framework with Pydantic v2 integration and OpenAPI 3.1 generation. |
| starlette | 1.9.0 | Pulled in by FastAPI; pinned explicitly because SSE and middleware behaviour depend on it. |
| uvicorn[standard] | 0.54.0 | ASGI server used in local development and inside containers (`--workers 1`, scale with pods). |
| granian | 2.8.4 | Optional production ASGI server (Rust, HTTP/2); behind the flag `AR_ASGI_SERVER=granian`. |
| pydantic | 2.14.1 | Validation and serialisation for every DTO, config and contract. |
| pydantic-settings | 2.16.0 | Typed configuration loaded from `AR_*` environment variables. |
| sqlalchemy[asyncio] | 2.1.5 | Async ORM with typed `Mapped[]` models. |
| asyncpg | 0.32.0 | Fastest async Postgres driver; used by SQLAlchemy. |
| psycopg[binary] | 3.3.6 | Used only by Alembic offline scripts and by `mcp-sql` for Postgres targets (server-side cursors, read-only transactions). |
| alembic | 1.20.0 | Schema migrations, autogenerate support. |
| pgvector (python) | 0.5.1 | SQLAlchemy `Vector`/`HalfVector` types: knowledge chunk embeddings (default `pgvector` retrieval adapter), memory and tool-search embeddings. |
| temporalio | 1.34.0 | Durable workflows for runs, routines, ingestion and maintenance jobs. |
| mcp | 2.3.0 | Official MCP Python SDK; implements spec revision **2026-07-28** (stateless Streamable HTTP). |
| openai | 3.35.1 | OpenAI-compatible client used by `model-gateway` to talk to upstream engines (vLLM, TEI, other compatible servers). |
| httpx | 0.28.1 | Async HTTP client for every outbound call (with OpenTelemetry instrumentation). |
| redis | 8.1.0 | Client for Valkey (protocol compatible): sessions, rate limits, run event streams, caches. |
| qdrant-client | 1.19.1 | **Optional** extra `ar-domain[qdrant]`: client for the optional Qdrant retrieval adapter ([ADR-0009](02-architecture/adr/ADR-0009-retrieval-stores.md)). |
| fastembed | 0.9.0 | **Optional** extra `ar-domain[qdrant]`: CPU BM25 sparse vectors (`Qdrant/bm25`) for the Qdrant adapter's lexical signal (the default pgvector adapter uses Postgres full-text search). |
| docling | 2.140.0 | Layout-aware parsing of PDF, Office and HTML to Markdown with structure. |
| sqlglot | 30.23.0 | SQL parsing and validation for the read-only SQL connector. |
| presidio-analyzer / presidio-anonymizer | 2.2.364 | PII detection and redaction (custom recognisers for Aadhaar, PAN, Indian phone numbers). |
| rfc8785 | 0.1.4 | JSON Canonicalization Scheme (JCS) used to hash tool arguments for approval binding. |
| pyjwt[crypto] | 2.15.1 | Verify OIDC tokens (JWKS) and sign internal service JWTs (EdDSA). |
| authlib | 1.9.1 | OIDC authorization-code + PKCE client for the BFF login flow and OAuth flows for credential grants. |
| cryptography | 48.0.1 | AES-256-GCM envelope encryption for the `db_encrypted` secrets backend; Ed25519 keys. 50.0.2 is the newest release, but presidio-anonymizer 2.2.364 requires `cryptography>=48,<49`, so 48.0.1 is the newest version that resolves with the PII stack. |
| hvac | 2.4.0 | Vault/OpenBao client (KV v2, Transit, Kubernetes auth). |
| boto3 / aiobotocore | 1.43.106 / 3.9.2 | S3-compatible object storage (presigned URLs via boto3, async I/O via aiobotocore). boto3 1.43.115 requires botocore ≥ 1.43.115, which the current aiobotocore 3.9.2 rejects (`botocore>=1.43.101,<1.43.107`); 1.43.106 is the newest boto3 that resolves. |
| kubernetes-asyncio | 36.1.0 | Sandbox manager Kubernetes driver (pods, PVCs, network policies). |
| aiodocker | 0.27.0 | Sandbox manager Docker driver for local development. |
| slack-bolt | 1.30.0 | Slack app (Socket Mode by default, HTTP events optional). |
| microsoft-agents-hosting-core / -aiohttp | 1.9.0 | Current Microsoft SDK for Teams bots (successor of Bot Framework SDK). |
| aioimaplib / aiosmtplib | 2.0.3 / 5.1.3 | Email channel: inbound IMAP polling, outbound SMTP relay. |
| croniter | 6.2.4 | Validate cron expressions and compute `next_run_at` for display (Temporal schedules do the actual firing). |
| structlog | 26.1.0 | Structured JSON logs with trace correlation. |
| opentelemetry-sdk / -exporter-otlp | 1.45.1 | Traces and metrics (GenAI semantic conventions). |
| opentelemetry-instrumentation-fastapi / -httpx / -sqlalchemy | 0.66b1 | Auto-instrumentation of inbound HTTP, outbound HTTP and DB. |
| prometheus-client | 0.26.0 | `/metrics` endpoint on every service. |
| langfuse | 5.0.3 | LLM traces, prompt/version tracking and scores (self-hosted Langfuse server). |
| tenacity | 9.2.1 | Retries for non-Temporal code paths (HTTP clients, startup checks). |
| orjson | 3.13.0 | Fast JSON for SSE frames and large payloads. |
| sse-starlette | 3.5.0 | Server-Sent Events responses with keep-alive pings and disconnect detection. |
| python-multipart | 0.0.32 | Multipart file uploads in FastAPI. |
| pyyaml | 6.0.3 | YAML definition bundles (`ar.yaml`) import/export. |
| jsonschema | 4.26.0 | Validate tool input arguments against MCP tool JSON Schemas (draft 2020-12). |
| tiktoken | 0.14.0 | Fast token counting (`o200k_base`) for chunk sizing and prompt-size estimates (approximation; billing uses upstream usage). |
| pillow | 12.3.0 | Image thumbnails and dimensions in `FileProcessWorkflow`. 13.0.0 is newer, but fastembed 0.9.0 (the optional Qdrant BM25 extra) requires `pillow>=12,<13`. |
| pypdf | 6.21.1 | PDF page counts and text excerpts for file previews. |
| filetype | 1.2.0 | Magic-byte MIME sniffing of uploads (pure Python, no libmagic). |
| mistune | 3.4.0 | Markdown → HTML for email replies and notification emails (output sanitised with nh3). |
| jmespath | 1.1.0 | Routine `event_filter` expressions and webhook idempotency key paths. |
| jinja2 | 3.1.6 | Email notification templates (`ar_system/templates/email/*.html.j2`). |
| nh3 | 0.3.7 | HTML sanitising of rendered previews (approval previews, email bodies). |
| openapi-python-client | 0.29.1 | Generates the public Python SDK (`libs/ar_client`) from `openapi.json`. |
| attrs | 26.1.0 | Runtime dependency of the generated Python client (`openapi-python-client` emits `attrs` classes). |

### Python tooling

| Tool | Version | Reason |
|---|---|---|
| ruff | 0.17.1 | Lint and format (replaces black, isort, flake8, pyupgrade). |
| mypy | 2.4.0 | Strict type checking with the Pydantic plugin; mature and supported by SQLAlchemy 2 typing. `ty` (0.0.89, beta) is not yet production-grade. |
| pytest | 9.1.1 | Test runner. |
| pytest-asyncio | 1.4.0 | Async tests (`asyncio_mode = "auto"`). |
| pytest-xdist | 3.8.0 | Parallel test execution. |
| pytest-cov / coverage | 7.1.0 / 7.16.2 | Coverage gates. |
| testcontainers | 4.15.0 | Real Postgres, Valkey (and Qdrant for the `conformance-qdrant` job) in integration tests (no SQLite stand-ins). |
| respx | 0.23.1 | Mock httpx calls in unit tests. |
| hypothesis | 6.170.5 | Property tests for canonical hashing, SQL validator, chunker, policy rule compiler. |
| polyfactory | 3.3.0 | Factories for Pydantic models and SQLAlchemy rows in tests. |
| time-machine | 3.5.1 | Deterministic clocks (expiry, schedules, retention). |
| inline-snapshot | 0.36.1 | Snapshot assertions for prompts, OpenAPI and event payloads. |
| schemathesis | 4.32.1 | Property-based API contract tests against `openapi.json`. |
| locust | 2.46.7 | Load tests for performance budgets. |
| import-linter | 2.15 | Enforce package layering (services may not import each other; see [08-quality/coding-standards-python.md](08-quality/coding-standards-python.md)). |
| deptry | 0.25.1 | Detect unused or missing dependencies. |
| lefthook | 2.2.2 | Git hooks (format, lint, typecheck on staged files) for both Python and TS. |
| honcho | 2.0.0 | Runs `Procfile.dev` processes for `make dev` (dev dependency only). Verified on PyPI during M0-T02. |

## 3. Web app (TypeScript)

| Library | Version | Reason |
|---|---|---|
| pnpm | 12.14.0 | Fast, strict, disk-efficient workspaces. |
| turbo | 2.11.9 | Task graph and caching for the JS workspace (and for codegen tasks). |
| next | 16.4.2 | App Router, React Server Components, streaming, route handlers. |
| react / react-dom | 19.3.1 | Required by Next 16; Actions, `use()`, transitions. |
| tailwindcss | 4.3.3 | CSS-first configuration, fast engine. |
| shadcn (CLI) | 4.22.1 | Copies accessible Radix-based components into `apps/web/src/components/ui`. |
| @radix-ui/* | latest compatible (e.g. react-dialog 1.3.1) | Primitives behind shadcn/ui components. |
| lucide-react | 1.60.0 | Icon set used by shadcn/ui. |
| class-variance-authority / tailwind-merge / tw-animate-css | 0.7.1 / 3.7.0 / 1.4.0 | Standard shadcn/ui helpers. |
| @tanstack/react-query | 5.104.5 | Server-state cache, mutations, optimistic updates. |
| @tanstack/react-table | 9.3.1 | Headless tables for admin lists. |
| @tanstack/react-virtual | 3.14.21 | Virtualised message lists and log views. |
| @hey-api/openapi-ts | 0.99.0 | Generates the typed client and TanStack Query hooks from `openapi.json` (`@ar/api-client`). |
| eventsource-parser | 4.1.2 | Parses SSE frames from `fetch` streams (supports POST, headers and resume). |
| zod | 4.6.7 | Runtime validation of forms and of stream events. |
| react-hook-form / @hookform/resolvers | 7.90.0 / 6.0.0 | Forms in the builder and admin screens. |
| nuqs | 2.10.2 | Type-safe URL search-param state (filters, tabs, pagination). |
| zustand | 5.0.15 | Small client-only state (chat composer, run stream buffers, panels). |
| react-markdown / remark-gfm / rehype-katex / katex | 10.1.0 / 4.0.1 / 7.0.1 / 0.19.0 | Render assistant Markdown, tables and maths. |
| rehype-sanitize / dompurify | 6.0.0 / 3.4.17 | Sanitise rendered Markdown and HTML previews. |
| shiki | 4.5.0 | Code highlighting in messages and code viewers. |
| mermaid | 12.2.0 | Render Mermaid blocks produced by agents. |
| @monaco-editor/react / monaco-editor | 4.7.0 / 0.57.0 | YAML/JSON/Markdown editors (agent definition, policies, skills). |
| @xyflow/react | 12.12.0 | Run trace graph (parent run and subagents). |
| recharts | 3.10.1 | Usage and evaluation charts. |
| react-resizable-panels | 4.14.7 | Chat + side panels (artifacts, computer, run inspector). |
| sonner | 2.0.8 | Toasts. |
| cmdk | 1.1.1 | Command palette. |
| next-intl | 4.14.9 | i18n (English first; message catalogues for Indian languages later). |
| date-fns | 4.4.0 | Date formatting with time zones. |

### TypeScript tooling

| Tool | Version | Reason |
|---|---|---|
| @biomejs/biome | 2.5.15 | One fast tool for lint and format (replaces ESLint + Prettier); Next 16 no longer ships `next lint`. |
| vitest | 5.0.5 | Unit and component tests. |
| @testing-library/react | 16.3.3 | Component tests. |
| jsdom | 30.1.3 | DOM environment for Vitest. |
| msw | 3.0.3 | Mock the API in component tests and Storybook. |
| @playwright/test | 1.64.1 | End-to-end tests across web, API and workers. |
| @axe-core/playwright | 4.14.0 | Automated WCAG 2.1 AA checks in E2E. |
| storybook / @storybook/nextjs-vite | 10.6.3 | Component catalogue for chat and builder components. |
| knip | 6.42.1 | Detect unused files, exports and dependencies. |
| @hey-api/client-fetch | 0.13.1 | Runtime fetch client used by the generated `@ar/api-client`. Required by `@hey-api/openapi-ts` 0.99. |
| json-schema-to-typescript | 16.0.0 | Emits TypeScript types from `ar_contracts` JSON Schema during `make gen`. |
| json-schema-to-zod | 2.8.1 | Emits Zod 4 schemas from the same Pydantic JSON Schema. Maintained through 2.8.1; pinned because it is the converter that targets Zod 4. |
| @vitejs/plugin-react | 6.1.2 | JSX transform for Vitest. |
| @tailwindcss/postcss | 4.3.3 | Tailwind 4 PostCSS plugin required by Next.js. |
| @types/react / @types/react-dom | 19.3.0 | React 19.3 publishes types, but TypeScript 7 still resolves the DefinitelyTyped packages for JSX. |

## 4. Platform services and infrastructure

| Component | Version | Reason |
|---|---|---|
| PostgreSQL + pgvector | 18.6 + 0.8.7 (image `pgvector/pgvector:0.8.7-pg18-trixie`) | System of record; default retrieval store for knowledge (HNSW on `halfvec`, iterative index scans, full-text `tsvector` for hybrid search), memory and tool search; RLS for tenancy. |
| CloudNativePG operator | 1.30.1 | HA Postgres on Kubernetes, PITR backups to S3. |
| Valkey | 9.1.2 | BSD-licensed Redis-compatible store: sessions, rate limits, streams, caches. |
| Temporal server | 1.32.1 (`temporalio/server:1.32.1`, Helm chart from `temporalio/helm-charts`); CLI image `temporalio/temporal:1.9.1` for `temporal server start-dev` locally | Durable execution backbone. Docker Hub has no tag `temporalio/temporal:1.32.1`; the server image is `temporalio/server`. Local dev uses the CLI image, which vendors the dev server (SQLite). |
| Qdrant (optional) | 1.19.2 | Optional retrieval backend (`AR_VECTOR_BACKEND=qdrant`) for very large knowledge corpora; not deployed by default (compose profile `qdrant`, Helm `qdrant.enabled=false`). |
| Keycloak | 26.8.1 | OIDC broker with Organizations (tenant = organization), identity brokering to corporate IdPs, token exchange. |
| Open Policy Agent | 1.21.3 | Policy-as-code (Rego v1) for runtime tool decisions; bundles served by `api`. |
| OpenBao | 2.7.1 | Open-source (MPL-2.0) Vault-API-compatible secrets store; avoids BSL constraints for a SaaS offering. HashiCorp Vault 2.2.0 also supported (same API). |
| S3-compatible object store | SeaweedFS 4.48 (default self-host), any S3 API (Ceph RGW, cloud S3) | MinIO community edition was archived in April 2026; SeaweedFS is Apache-2.0, supports versioning and Object Lock (needed for the audit bucket). |
| vLLM | 0.32.0 | Default LLM engine (OpenAI-compatible, tool-call parsers, guided decoding, prefix caching). |
| Hugging Face TEI | 1.9.4 | Embedding and reranker serving (BGE-M3, bge-reranker-v2-m3). |
| OpenTelemetry Collector (contrib) | 0.163.1 | Receives OTLP; exports to Tempo, Prometheus, Loki and Langfuse. |
| Langfuse (server) | 4.64.0 | Self-hosted LLM observability and evaluation datasets. |
| Prometheus | 3.15.0 | Metrics. |
| Grafana Tempo / Loki / Grafana | 3.1.0 / 3.7.8 / 13.2.4 | Traces / logs backends and the local dashboards UI (profile `obs`). |
| Kubernetes | 1.34 to 1.37 supported | Standard APIs only (Deployments, StatefulSets via operators, NetworkPolicy, RuntimeClass). |
| Helm | 4.3.1 | Packaging of the umbrella chart `agentic-runtime`. |
| Argo CD | 3.5.5 | GitOps delivery for SaaS and recommended for customer installs. |
| cert-manager | 1.21.2 | Internal PKI and ingress certificates. |
| KEDA | 2.21.0 | Scale workers on Temporal task-queue backlog. |
| Envoy Gateway | 1.9.2 | Gateway API ingress (TLS, rate limits, request size limits); any Gateway API implementation works. |
| gVisor | release-20261012.0 | Default sandbox runtime (`RuntimeClass gvisor`). |
| Kata Containers | 4.2.0 | VM-grade sandbox runtime (`RuntimeClass kata`) for high-assurance tenants. |
| ClamAV (clamd) | 1.5.4 | Malware scanning of uploads (`AR_FILES_SCANNER=clamav`). |
| Mailpit | 1.31.6 | Local-dev SMTP capture with web UI (ports 1025/8025); never used in production. |
| GreenMail | 2.1 | SMTP + IMAP test server for email-channel integration tests (Mailpit has no IMAP). |
| Squid | 7.7 | Sandbox egress proxy with per-sandbox domain allowlists. |
| Falco | 0.45.1 | Runtime threat detection on the sandbox node pool. |
| Docker Engine + Compose v2 | Engine 28+ / Compose 2.40+ | Local development stack (`compose.yaml`). |

### CI and supply-chain tools

Pinned at M0-T02/M0-T10 (2026-10-20) to the latest stable GitHub release. Used only in CI ([07-ops/ci-cd.md](07-ops/ci-cd.md)).

| Tool | Version | Use |
|---|---|---|
| gitleaks | 8.30.1 | Secret scanning of diffs and history |
| osv-scanner | 2.7.0 | Dependency vulnerability scanning |
| pip-audit | 2.10.1 | Python dependency vulnerability scanning (`pnpm audit` covers the JS lockfile) |
| Trivy | 0.76.0 | Image and Helm misconfiguration scanning |
| Semgrep | 1.181.0 | Static analysis (OSS rules) with custom rules |
| zizmor | 1.31.1 | CI workflow security linting |
| OWASP ZAP | 2.17.0 | Nightly DAST of the web app |
| squawk | 2.70.0 | Lint SQL migrations for locking hazards |
| kubeconform | 0.8.0 | Helm chart validation |
| syft | 1.55.0 | SBOM generation |
| cosign | 3.1.3 | Image signing |
| @mermaid-js/mermaid-cli (`mmdc`) | 12.0.0 | Render-check Mermaid diagrams in docs |

## 5. Protocols and standards

| Standard | Version | Use |
|---|---|---|
| MCP | 2026-07-28 | Stateless Streamable HTTP; `server/discover`; tool annotations; `Mcp-Method`/`Mcp-Name` headers used by `mcp-gateway`. |
| OpenAPI | 3.1 | Public API contract generated by FastAPI. |
| OIDC / OAuth 2.1, RFC 8693 | - | SSO, BFF login, token exchange for delegated tool credentials. |
| SCIM | 2.0 | User and group provisioning. |
| RFC 9457 | - | Problem Details error format. |
| RFC 8785 | - | JSON canonicalisation for argument hashes. |
| OpenTelemetry GenAI semantic conventions | current | Span attributes for model and tool calls. |
| Server-Sent Events | WHATWG | Run event streaming to clients. |

Note: M0-T02 re-verified every Python and npm pin against PyPI and the npm registry, and infrastructure/CI pins against GitHub releases and container registries, on 2026-10-20. Versions that had moved since the spec was drafted are the ones in the tables above (FastAPI, Langfuse client, tiktoken, Pillow, pypdf, mistune, jmespath, lucide-react, Storybook, Mailpit, ClamAV, the OpenTelemetry Collector, Grafana, and the CI scanners). GreenMail stays at 2.1 (test-only; not pulled into the M0 lockfile). The TypeScript 6 fallback alias is `@typescript/typescript6@6.0.2` because 6.0.3 is not published.
