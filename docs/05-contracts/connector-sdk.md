# Connector / plugin SDK contract (`ar_connector_sdk`)

Customers extend the platform in three ways, all without changing platform code:

1. **Tool servers**: any MCP server (any language) that meets [mcp-integration.md](mcp-integration.md). The Python SDK makes this trivial and adds platform conventions.
2. **Knowledge connectors**: a custom source exposed as an MCP server with resources (`knowledge_sources.kind='mcp_resource'`) using the SDK's `DocumentSource` helper, which emits ACL-aware documents.
3. **Declarative definitions**: agents, routines, policies, skills via bundles ([definition-schema.md](definition-schema.md)).

The SDK is published from `libs/ar_connector_sdk` (package name `agentic-runtime-connector-sdk`, import `ar_connector_sdk`), versioned with SemVer independently of the platform, supporting Python ≥ 3.12.

## 1. Tool server helper

```python
from ar_connector_sdk import ToolServer, ToolContext, tool, RiskClass

server = ToolServer(name="erp", version="1.2.0")

@server.tool(risk=RiskClass.W2, idempotent=False, title="Create purchase request")
async def create_purchase_request(ctx: ToolContext, vendor_id: str, amount_inr: int, reason: str) -> dict:
    """Create a draft purchase request in the ERP. Returns the request number."""
    ctx.require_scope("erp.pr.write")
    async with ctx.idempotency(ttl_s=86400) as cached:      # dedupes on X-AR-Idempotency-Key
        if cached.hit:
            return cached.value
        pr = await erp_client(ctx.user_token()).create_pr(vendor_id, amount_inr, reason)
        return cached.store({"pr_number": pr.number})

app = server.asgi_app()        # Starlette app serving POST /mcp (Streamable HTTP, MCP 2026-07-28)
```

Behaviour provided by the SDK:

| Feature | Detail |
|---|---|
| Schema generation | From type hints + docstring (Pydantic v2) → `inputSchema` (JSON Schema 2020-12), `outputSchema` when the return type is a Pydantic model. |
| Annotations | `risk` maps to MCP annotations (`R0/R1` → `readOnlyHint=true`; `W3` → `destructiveHint=true`; `idempotent` → `idempotentHint`). The platform reviewer still confirms the final risk class. |
| `ToolContext` | `ctx.tenant_id`, `ctx.user` (`id, email, groups`), `ctx.agent_id`, `ctx.run_id`, `ctx.tool_call_id`, `ctx.scopes`, `ctx.user_token()` (bearer token from `Authorization` in user_oauth/token_exchange modes), `ctx.progress(msg, fraction)`, `ctx.log`. Populated from verified headers. |
| Internal JWT verification | `ToolServer(auth=InternalJwtAuth(jwks_url=..., audience="erp"))` verifies `X-AR-Context` / `Authorization` JWTs from `mcp-gateway`; rejects expired (> 60 s) or wrong-audience tokens. |
| Idempotency | `ctx.idempotency()` with pluggable store (in-memory for tests, Redis/Valkey or Postgres for production). |
| Errors | Raise `ToolError(code, message, retriable=False)` → MCP result with `isError: true` and `structuredContent: {code, message}`. Uncaught exceptions → `isError: true`, code `internal_error`, no stack trace leaked. |
| Large results | `ctx.attach_file(name, bytes, mime)` returns an embedded `resource` item; the gateway offloads it to object storage. |
| Observability | OpenTelemetry spans per call with `traceparent` propagation; Prometheus metrics `ar_connector_tool_calls_total{tool,status}`. |
| Testing | `ar_connector_sdk.testing.ToolServerHarness` runs the server in-process and lets tests call tools with a fake context; `conformance.run(url)` executes the platform's registration checks (§3) against a running server. |

## 2. Knowledge connector helper

```python
from ar_connector_sdk import DocumentSource, SourceDocument, Acl

source = DocumentSource(name="legal-dms", version="0.3.0")

@source.lister
async def list_documents(ctx, cursor: str | None):
    page = await dms.changes(since=cursor)
    for d in page.items:
        yield SourceDocument(
            external_id=d.id, uri=d.url, title=d.title, mime_type=d.mime,
            modified_at=d.modified, version=d.etag,
            acl=Acl(users=[d.owner_email], groups=d.reader_groups, public_within_tenant=False),
            deleted=d.is_deleted)
    source.set_cursor(page.next_cursor)

@source.fetcher
async def fetch(ctx, external_id: str) -> bytes: ...

app = source.asgi_app()
```

The helper exposes this as MCP resources: `resources/list` (paged, includes ACL metadata in `_meta["io.agentic-runtime/acl"]`), `resources/read` (bytes as blob), plus tool `source.changes(cursor)` returning changed/deleted ids. `ingest-worker` maps ACL emails/group names to platform principals (`user:{id}`, `group:{id}`) via the tenant directory; unknown principals are dropped and counted in `ingestion_jobs.stats.unmapped_principals`.

## 3. Conformance checks (run at registration and by `conformance.run`)

1. `server/discover` returns protocol version `2026-07-28` (or compatibility mode warning).
2. `tools/list` returns ≤ 200 tools; valid names; object input schemas; descriptions present (≥ 20 chars) and ≤ 4,000 chars.
3. Two consecutive `tools/list` calls return identical bytes (deterministic ordering).
4. Calling a non-existent tool returns a JSON-RPC error, not a crash.
5. Response to a call with an invalid argument returns `isError: true` or a JSON-RPC invalid-params error within 5 s.
6. For `internal_jwt` mode: a request with an expired JWT is rejected with HTTP 401.

## 4. Compatibility promise

- Headers in [mcp-integration.md](mcp-integration.md) §3 and JWT claims in §4.5 are stable within platform major version 1.
- New optional headers or claims may be added; servers must ignore unknown ones.
