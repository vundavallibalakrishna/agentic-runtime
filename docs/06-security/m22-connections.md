# M22 connections, MCP and OpenAPI

## Secrets

A service connection stores its secret with AES-256-GCM. The key is SHA-256 of `ar-connection-v1:` plus `AR_CURSOR_SECRET`. API responses, audit detail, tool arguments and model-visible tool results do not include the secret. If an upstream body echoes the secret, the text is replaced with `[redacted]` before it is stored or wrapped for the model. Rotation replaces the ciphertext and bumps a version counter. The previous value is not kept.

Connections are owner-scoped. Another user in the same tenant, and every user in another tenant, receives 404. OAuth client-credentials and refresh exchanges send the client secret only to the token URL. That URL is checked with the same public-address guard as other outbound HTTP.

The rows live on the process store, the same place as OAuth grants (OQ-58). A process restart drops them. They are not a Postgres table in this milestone.

## SSRF and egress

Admin fetches of an OpenAPI document and connection tests allow public hosts and refuse private, link-local and metadata addresses. They do not follow a redirect until the next URL passes the same check.

Agent calls to an imported or described tool may use the host stored on that tool plus the tenant egress list. `general.http` still requires the tenant list. Private addresses stay denied. Loopback is allowed only when `AR_ENV` is `dev`, `ci` or `test`.

Remote MCP uses the same public-address guard. In dev, ci and test, loopback is allowed so a local reference server can be registered. Production does not allow it.

## MCP stdio

Stdio runs through `run_isolated` with network off. The program must be `python`, `python3`, `node`, `npx`, `uv` or `uvx`. Arguments cannot start with a dash, so the interpreter cannot be given `-c`. This is the M21b sandbox. When user namespaces are refused, the process fallback is not a security boundary (OQ-57). M22 does not widen that boundary and does not give the child a network namespace.

## Untrusted tool output

MCP, OpenAPI and described-tool results are prefixed as untrusted data and passed through `wrap_tool_result` before they re-enter the prompt. The same wrapping is used for fetched pages. A read-only MCP tool is auto-allowed only when the server sets `readOnlyHint`. Every other MCP tool, and every non-GET OpenAPI or described operation, waits for approval.

## What was tested

- A bearer secret is absent from the API view, the ciphertext, and a tool result that echoed it.
- A second user and a second tenant receive 404 for the connection.
- An OpenAPI GET runs. An OpenAPI POST waits for approval. The page text is labelled untrusted.
- A described tool sends the connection and the model-visible result does not contain the secret.
- MCP discovery maps `readOnlyHint` to R0 and everything else to W2.
- `rm -rf /` is rejected as a stdio command.
- Run-step audit actions are included in the durable audit copy. A duplicate model alias raises a conflict instead of an integrity error.

The real-model proof is recorded in [m22-checklist](../testing/m22-checklist.md).
