# M22 — Connections, MCP and OpenAPI

A customer reaches tools they did not ask us to hand-write. A connection holds a credential. An MCP server, an OpenAPI document, or a plain-language HTTP description becomes tools on the same registry the agent already calls.

This milestone is one pull request. The four surfaces share the tool pipeline, the approval gate and the chat trace.

## Tasks

### M22-T01 Connections

- **Depends on:** M21b-T03
- **Do:** A named connection stores an API key, a bearer token, basic auth, or OAuth 2.0 (authorization code or client credentials). The secret is encrypted, never returned, and scoped to its owner. The owner can test it, rotate it, and see expiry. `general.http` and the tools below take the connection by name.
- **Done when:** A response and a tool result do not contain the secret, and another user or tenant receives 404.
- **Tests:** `libs/ar_domain/tests/unit/test_m22_tools.py`

### M22-T02 MCP client

- **Depends on:** M22-T01
- **Do:** An admin adds a remote MCP server over streamable HTTP or SSE, or a stdio server that runs in the existing sandbox with network off. The admin picks a connection for auth. Discovered tools join the registry. A tool is auto-allowed only when the server marks it read-only. Every other tool waits for approval. Results are untrusted data. Timeouts, upstream errors, a changed manifest and one reconnect are handled.
- **Done when:** A read-only tool runs, a write waits, and a changed manifest is reported instead of being called as if nothing changed.
- **Tests:** `libs/ar_domain/tests/unit/test_m22_tools.py`

### M22-T03 OpenAPI and described tools

- **Depends on:** M22-T02
- **Do:** Paste or link an OpenAPI 3.x document. The platform makes one tool per selected operation, uses a connection for auth, and allows GET and HEAD. Other methods wait. Documents over 2 MB are rejected. More than 40 operations must be selected. A sentence that names a method and a URL becomes a reviewable tool with a Test action.
- **Done when:** An imported GET runs, an imported POST waits, and a described tool can be saved and called.
- **Tests:** `libs/ar_domain/tests/unit/test_m22_tools.py`

### M22-T04 Registry and builder

- **Depends on:** M22-T03
- **Do:** The tools screen lists built-in, MCP, OpenAPI and custom tools with source, status, last error, call counts, limits and enable or disable. The agent editor attaches a source, a server, or one tool, and marks tools that ask first. Chat cards show MCP and OpenAPI calls. Run-step audit rows are copied into `audit_events`. A duplicate model alias returns 409.
- **Done when:** Playwright covers the new screens in light and dark at desktop and mobile widths, and the checklist records the real-model proof.
- **Tests:** `apps/web/e2e/m22-tools.spec.ts`

## Out of scope

Documents, knowledge, connector libraries for specific products, orchestration, and exposing agents. The GRC pack stays parked.
