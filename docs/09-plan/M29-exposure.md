# M29 — Expose agents

Depends on M28. A published agent can be called from outside the product: a versioned REST API, an MCP server, and A2A.

## M29-T01 Agent API and keys

**Spec:** [m29-exposure](../06-security/m29-exposure.md), [api catalogue](../05-contracts/api-catalogue.md).

**Do:**

- Revision 0030 stores agent API keys, idempotency rows, grants and A2A tasks. The raw key is returned once. Only the SHA-256 hash is stored.
- `POST /v1/agents/{slug}/conversations`, message send, SSE or JSON reply, file upload, and `GET` of that run's trace. A key is scoped to one agent or, when its scope is `workspace`, to published agents in the same tenant.
- `Idempotency-Key` on message send returns the original run. A different body with the same key is rejected.
- Per-key requests per minute and a monthly quota. Every external call is audited with the key label.

**Done when:** a missing key and a revoked key are both refused, a retry does not start a second run, and a second key cannot read the first key's stream.

**Tests:** `libs/ar_domain/tests/unit/test_m29_exposure.py`, `services/api/tests/unit/test_m29_exposure_api.py`.

## M29-T02 MCP server

**Spec:** [m29-exposure](../06-security/m29-exposure.md), [how to connect](../agent-api/README.md).

**Do:**

- `POST /v1/mcp` speaks streamable HTTP MCP. `tools/list` returns one tool per published agent the key may call.
- A write that the policy gate holds returns a tool result whose text is `Approval required`, with `structuredContent.status` of `approval_required`.

**Done when:** a client can list the agent and a write does not fail silently.

**Tests:** `test_m29_exposure_api.py`.

## M29-T03 A2A

**Spec:** [m29-exposure](../06-security/m29-exposure.md), [A2A](../agent-api/a2a.md).

**Do:**

- Agent card at `/.well-known/agent-card.json` and under the agent path. Task send, stream, get and cancel. Artifacts carry the reply.
- `control.a2a_call` calls a remote card URL. The bearer token is a named secret, not a model argument.
- Push-notification methods and gRPC return a JSON-RPC method-not-implemented error. That gap is documented. It is not described as conformance.

**Done when:** a card fetch and a task send hit the running server, and the remote tool can call an agent card.

**Tests:** `test_m29_exposure.py`.

## M29-T04 Expose tab

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- The agent page has an Expose tab: keys, endpoint URLs, curl, JavaScript, an MCP snippet, the agent card URL, usage per key, and a test console that posts to `/v1`, not `/api/v1`.
- The web app proxies `/v1` and the well-known card so the console is same-origin.

**Done when:** Playwright captures the tab in light and dark at desktop and mobile widths.

**Tests:** `apps/web/e2e/m29-exposure.spec.ts`, `apps/web/src/components/agents/expose-panel.test.tsx`.

## Out of scope

Removing the parked industry pack (M30). A certification pass. Full A2A conformance (push notifications, gRPC, task list pagination).
