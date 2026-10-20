# Python coding standards

Applies to `libs/*`, `services/*`, `connectors/*`. Versions: [stack](../stack.md). Enforced by `make lint typecheck` and CI ([ci-cd §2](../07-ops/ci-cd.md#2-jobs)).

## 1. Baseline

- Python 3.14, `from __future__ import annotations` not needed (PEP 649 semantics); type hints on every function signature and module-level variable.
- `uv` only (no pip/poetry); dependencies declared in the project's own `pyproject.toml`; dev tools in the root `[dependency-groups] dev`.
- `src/` layout; package names `ar_*`; one public API per module via explicit `__all__` where re-exported.
- Async everywhere on I/O paths (FastAPI, SQLAlchemy async, httpx.AsyncClient, redis.asyncio); never call blocking I/O in async code (use `anyio.to_thread.run_sync` for CPU-bound or blocking libs such as parsers).
- Formatting: `ruff format` (line length 100, double quotes).

## 2. Ruff and lint configuration

Root `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py314"
line-length = 100
src = ["libs/*/src", "services/*/src", "connectors/*/src"]

[tool.ruff.lint]
select = ["E", "W", "F", "I", "UP", "B", "A", "C4", "SIM", "RET", "PTH", "N", "S", "ASYNC", "DTZ", "T20", "PT", "PL", "RUF", "TRY", "PERF", "FBT", "ARG", "ERA", "LOG", "G", "BLE", "TID", "TC", "FAST"]
ignore = ["PLR0913", "TRY003", "PLR2004", "FBT003"]

[tool.ruff.lint.per-file-ignores]
"**/tests/**" = ["S101", "PLR2004", "ARG", "FBT"]
"**/alembic/versions/*.py" = ["E501", "N999"]

[tool.ruff.lint.flake8-tidy-imports.banned-api]
"requests".msg = "use httpx.AsyncClient via ar_common.http"
"datetime.datetime.utcnow".msg = "use ar_common.time.utcnow()"
"json.loads".msg = "use orjson or Pydantic model_validate_json on hot paths"
"logging.getLogger".msg = "use ar_common.logging.get_logger (structlog)"

[tool.ruff.lint.isort]
known-first-party = ["ar_common", "ar_contracts", "ar_domain", "ar_connector_sdk", "ar_client", "ar_testing", "ar_api", "ar_runtime", "ar_system", "ar_ingest", "ar_model_gateway", "ar_mcp_gateway", "ar_sandbox_manager", "ar_sandbox_agent", "ar_channels", "ar_mcp_sql", "ar_mcp_openapi", "ar_fake_llm"]
```

mypy: `strict = true`, plugins `pydantic.mypy`; `disallow_any_explicit` for `ar_contracts`; `# type: ignore[code]` must carry a code and a reason comment.

### import-linter contracts (`.importlinter`)

```ini
[importlinter]
root_packages = ar_common ar_contracts ar_domain ar_connector_sdk ar_api ar_runtime ar_system ar_ingest ar_model_gateway ar_mcp_gateway ar_sandbox_manager ar_sandbox_agent ar_channels ar_mcp_sql ar_mcp_openapi ar_fake_llm

[importlinter:contract:layers]
name = Library layering
type = layers
layers =
    (ar_api) | (ar_runtime) | (ar_system) | (ar_ingest) | (ar_model_gateway) | (ar_mcp_gateway) | (ar_sandbox_manager)
    ar_domain
    ar_contracts
    ar_common

[importlinter:contract:services-independent]
name = Services never import each other
type = independence
modules = ar_api ar_runtime ar_system ar_ingest ar_model_gateway ar_mcp_gateway ar_sandbox_manager ar_sandbox_agent ar_channels ar_mcp_sql ar_mcp_openapi ar_fake_llm

[importlinter:contract:no-db-in-edge]
name = Channels, sandbox agent and connectors have no DB access
type = forbidden
source_modules = ar_channels ar_sandbox_agent ar_mcp_sql ar_mcp_openapi
forbidden_modules = ar_domain sqlalchemy

[importlinter:contract:domain-modules]
name = Domain modules use each other's services only
type = forbidden
source_modules = ar_domain.*.service
forbidden_modules = ar_domain.*.repository
allow_indirect_imports = true

[importlinter:contract:retrieval-adapters]
name = Services never import retrieval store adapters or engine clients
type = forbidden
source_modules = ar_api ar_runtime ar_system ar_ingest ar_mcp_gateway
forbidden_modules = ar_domain.knowledge.store_pgvector ar_domain.knowledge.store_qdrant qdrant_client fastembed
allow_indirect_imports = true   # services reach adapters only via ar_domain.knowledge.store
```

The `domain-modules` contract is complemented by a custom test (`tests/architecture/test_module_boundaries.py`) that fails if module `a` imports `ar_domain.b.repository` or `ar_domain.b.models` for `a != b`, and if any module other than `ar_domain.knowledge.store` imports `store_pgvector`/`store_qdrant` (or anything other than `store_qdrant` imports `qdrant_client`/`fastembed`) ([service-decomposition §3](../02-architecture/service-decomposition.md#3-domain-modules-ar_domainmodule)).

## 3. Structure of a domain module

```
ar_domain/<module>/
  models.py       # SQLAlchemy 2 typed models (Mapped[...]); no business logic
  repository.py   # queries; takes AsyncSession; returns models; never commits
  schemas.py      # Pydantic v2 request/response/DTO models (or ar_contracts for cross-process)
  service.py      # business logic; transactions; permission checks; audit; outbox
  errors.py       # DomainError subclasses with stable `code`
  permissions.py  # permission keys used by this module (subset of authn-authz §3)
  events.py       # domain event payload models (ar_contracts.events re-exports)
```

- Routers (`ar_api/routers/*.py`) are thin: parse → `service.call(ctx, ...)` → map to response. No SQL in routers.
- `ctx: RequestContext` (principal, tenant_id, request_id, trace) is the first argument of every service function.
- Unit of work: `async with uow(ctx) as session:` opens a transaction, sets `app.tenant_id`/`app.user_id` (`SET LOCAL`), commits on success. Repositories never commit.
- Errors: raise `DomainError` subclasses (`NotFound`, `Conflict`, `Forbidden`, `ValidationFailed`, `PlanLimitReached`, …); the API maps them to RFC 9457 responses ([api-conventions](../05-contracts/api-conventions.md)). Never return `None` to signal errors.

## 4. Pydantic and typing

- Public contract models subclass `ar_contracts.api_model.ApiModel` ([ADR-0026](../02-architecture/adr/ADR-0026-public-json-camel-case.md)): camelCase JSON, snake_case attributes, `populate_by_name=True`. Add `frozen=True` on the subclass. `str_strip_whitespace=True` for user text inputs.
- IDs are `uuid.UUID` (UUIDv7 generated in Postgres via `uuidv7()` or in Python `uuid.uuid7()`); timestamps are timezone-aware `datetime` (UTC).
- Money as integer micros (`cost_micros: int`); never floats.
- Enums: `StrEnum`. Database CHECK values match the Python values. Public JSON property names are still camelCase. Identifier tokens (error codes, event types) stay as the catalogue writes them.
- No `Any` in public signatures; use `TypedDict`/models; `JsonValue` from Pydantic for free-form JSON.

## 5. Async, Temporal and concurrency

- Workflows (`*/workflows.py`) are deterministic: no I/O, no `datetime.now()` (use `workflow.now()`), no random (use `workflow.random()`), no imports of non-deterministic modules outside `workflow.unsafe.imports_passed_through()`.
- Activities are idempotent (keyed by deterministic ids) and declare `start_to_close_timeout` and retry policies explicitly; heartbeats for activities > 30 s.
- Workflow and activity input/output are Pydantic models via the Temporal Pydantic data converter.
- Never share `AsyncSession` across tasks; use `asyncio.TaskGroup` for fan-out; cancellations propagate.

## 6. Logging, telemetry, errors

- `structlog` JSON logs via `ar_common.logging.get_logger(__name__)`; keys snake_case; include `tenant_id`, `run_id` where known (context vars). Never log message content, prompts, tool arguments/results, tokens or secrets (`ar_common.redaction` processor enforces known patterns).
- Spans via OpenTelemetry (`ar_common.telemetry.setup(service_name)` once per process); GenAI semantic conventions for model/tool spans.
- Catch broad exceptions only at process boundaries (activity wrapper, ASGI middleware) and re-raise or convert with context.

## 7. Security rules (code level)

- SQL only via SQLAlchemy expressions or `text()` with bound parameters; dynamic identifiers only from allowlists.
- Outbound HTTP only via `ar_common.http.client()` which applies `ssrf_guard` (deny private/metadata ranges unless allowlisted), timeouts (connect 5 s, read 30 s default) and OTel propagation.
- Secrets only via `SecretStore` (`ar_domain.secrets.store`); never read secrets from env in domain code.
- Untrusted text placed into prompts only via `ar_common.wrapping` ([prompt-injection §3](../06-security/prompt-injection.md#3-untrusted-content-wrapping)).
- `subprocess` forbidden outside `ar_sandbox_agent` and ingestion converters (allowlisted calls with argument lists, never `shell=True`).
- Constant-time comparison (`hmac.compare_digest`) for tokens and signatures.

## 8. Naming

| Thing | Convention | Example |
|---|---|---|
| Modules, functions, variables | snake_case | `build_prompt` |
| Classes | PascalCase | `AgentRunWorkflow` |
| Constants | UPPER_SNAKE | `MAX_TOOL_RESULT_BYTES` |
| Env vars | `AR_` + UPPER_SNAKE | `AR_OPA_URL` |
| Workflow ids | kebab with entity id | `run-{run_id}` |
| Metrics | `ar_<area>_<name>_<unit>` | `ar_tool_call_seconds` |
| Permission keys | `<resource>:<action>` | `agents:publish` |
| Audit actions | `<resource>.<past_verb>` | `agent.published` |
| Error codes | snake_case | `plan_limit_reached` |

## 9. Documentation in code

Docstrings for public functions of services and SDKs (Google style, short). Link the spec section in module docstrings (`Spec: docs/03-specs/07-agent-runtime.md §4`). No commented-out code (ruff `ERA`).
