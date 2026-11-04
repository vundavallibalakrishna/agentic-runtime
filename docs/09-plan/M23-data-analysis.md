# M23 — Data analysis

Depends on M22. A tenant keeps database connections, MCP servers, imported OpenAPI tools and described tools in Postgres. An agent can ask a read-only question of a customer database, inspect a spreadsheet, draw a chart and return JSON that matches a schema.

## M23-T01 Durable connections and registry

**Spec:** [08-tool-registry-mcp](../03-specs/08-tool-registry-mcp.md), [migrations](../04-data/migrations.md), [m23-database](../06-security/m23-database.md).

**Do:**

- Revision `0025` adds `service_connections` and `data_connections.dsn_ciphertext`, plus last-error columns on the tool registry.
- Flush service connections, data-connection ciphertext, tool versions and the model catalogue. Hydrate them on bind, including the provider API key into process memory.
- AES-256-GCM for connection secrets and DSNs uses SHA-256 of `ar-connection-v1:` plus `AR_CURSOR_SECRET`. Model keys stay on the existing envelope (`AR_DB_ENCRYPTION_KEYS`).

**Done when:** a restart and a new API process against the same database still list the connection, the described tool and the model alias. The secret is not in the API response.

**Tests:** `libs/ar_domain/tests/unit/test_m23_tools.py`.

## M23-T02 Read-only database tool

**Spec:** [m23-database](../06-security/m23-database.md).

**Do:**

- Tools `data.list_schemas`, `data.list_tables`, `data.describe_table`, `data.query` on `builtin://data`.
- Postgres and MySQL. One statement, read-only transaction, statement timeout, row and byte caps, allowlisted schemas and tables, no platform database unless `allowPlatform` is set.
- Refuse link-local and metadata hosts. Strip `options` and `init_command` from the DSN.

**Done when:** `DROP`, a second statement, `pg_sleep` and a write CTE are rejected before execution.

**Tests:** `test_m23_tools.py`.

## M23-T03 Spreadsheets, charts and structured output

**Spec:** [M21b](M21b-general-tools.md).

**Do:**

- `general.inspect_table`, `general.query_table`, `general.export_table` for CSV, TSV, JSON and xlsx in the run workspace. SQL runs in SQLite (OQ-60).
- `general.chart` writes a PNG for bar, line, scatter and pie.
- An agent `output.jsonSchema` is validated. One invalid answer is audited as `run.retried` and sent back to the model.

**Done when:** a file query and a chart land in the workspace, and a bad final answer is retried once.

**Tests:** `test_m23_tools.py`.

## M23-T04 UI, proof and docs

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- Connections screen saves a database connection and tests it. The connection string is a password field and is not shown again.
- Agent editor and builder attach the database tools with a row limit, schemas and tables, and a JSON schema.
- Chat cards show the query, a result table, a truncation note, the chart and a download.

**Done when:** Playwright captures light and dark at desktop and mobile, and the checklist records the Qwen3-32B run.

**Tests:** `apps/web/src/components/tools/tools-screen.test.tsx`, `apps/web/e2e/m23-data.spec.ts`.
