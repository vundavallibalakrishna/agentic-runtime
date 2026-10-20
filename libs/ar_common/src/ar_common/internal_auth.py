"""Allowed callers for internal APIs. Spec: docs/05-contracts/internal-apis.md §1."""

# target service → caller service → scopes that caller's token must carry
ALLOWED_CALLERS: dict[str, dict[str, frozenset[str]]] = {
    "model-gateway": {
        "runtime-worker": frozenset({"models:invoke", "models:embed"}),
        "system-worker": frozenset({"models:invoke", "models:embed"}),
        "ingest-worker": frozenset({"models:invoke", "models:embed"}),
        "mcp-gateway": frozenset({"models:invoke", "models:embed"}),
        "api": frozenset({"models:invoke", "models:embed"}),
    },
    "mcp-gateway": {
        "runtime-worker": frozenset({"tools:call", "tools:list"}),
        "api": frozenset({"tools:call", "tools:list"}),
        "system-worker": frozenset({"tools:call", "tools:list"}),
    },
    "sandbox-manager": {
        "mcp-gateway": frozenset({"sandboxes:manage"}),
        "api": frozenset({"sandboxes:manage"}),
        "system-worker": frozenset({"sandboxes:manage"}),
        "squid": frozenset(),
    },
    "api": {
        "channels": frozenset({"api:internal"}),
        "mcp-sql": frozenset({"api:internal"}),
        "mcp-openapi": frozenset({"api:internal"}),
        "opa": frozenset({"api:internal"}),
        "runtime-worker": frozenset({"api:internal"}),
        "system-worker": frozenset({"api:internal"}),
        "ingest-worker": frozenset({"api:internal"}),
        "model-gateway": frozenset({"api:internal"}),
        "mcp-gateway": frozenset({"api:internal"}),
        "sandbox-manager": frozenset({"api:internal"}),
    },
    "channels": {
        "mcp-gateway": frozenset({"channels:deliver"}),
        "system-worker": frozenset({"channels:deliver"}),
        "api": frozenset({"channels:deliver"}),
    },
    "mcp-sql": {
        "mcp-gateway": frozenset({"tools:call"}),
        "api": frozenset({"tools:call"}),
    },
    "mcp-openapi": {
        "mcp-gateway": frozenset({"tools:call"}),
        "api": frozenset({"tools:call"}),
    },
}
