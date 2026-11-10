# Calling an agent from another product

New to the API? Start with the [getting-started guide](getting-started.md), which also covers
service-account integration on `/api/v1`.

A published agent has its own keys. Create one on the agent's Expose tab. The secret is shown once. Send it as `Authorization: Bearer ara_...`.

The contract is `GET /v1/openapi.json`. A copy generated from those routes is [openapi.json](openapi.json).

Replace `https://runtime.example` and `ara_...` with the origin that serves `/v1` and a real key.

## REST

Create a conversation, then send a message. `Idempotency-Key` makes a retry return the same run.

```bash
curl -s https://runtime.example/v1/agents/assistant/conversations \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json"
```

```bash
curl -s https://runtime.example/v1/agents/assistant/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: retry-1" \
  -d '{"text":"What is 2 + 2?"}'
```

Stream the same call with `"stream": true`. The response is `text/event-stream` with `delta` events and a final `done` event.

```javascript
const base = "https://runtime.example/v1/agents/assistant";
const headers = {
  Authorization: "Bearer ara_<prefix><secret>",
  "Content-Type": "application/json",
};
const created = await fetch(`${base}/conversations`, { method: "POST", headers });
const conversation = await created.json();
const reply = await fetch(`${base}/conversations/${conversation.id}/messages`, {
  method: "POST",
  headers: { ...headers, "Idempotency-Key": crypto.randomUUID() },
  body: JSON.stringify({ text: "What is 2 + 2?" }),
});
console.log(await reply.json());
```

Attach a file first, then pass its id:

```bash
curl -s https://runtime.example/v1/agents/assistant/files \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -F "upload=@notes.txt" \
  -F "mime_type=text/plain"
```

The trace for that run, and only that run, is `GET /v1/agents/assistant/runs/$RUN_ID`. Events are `GET /v1/agents/assistant/runs/$RUN_ID/events`.

## MCP

Streamable HTTP. One tool is listed per published agent the key may call. A workspace-scoped key lists every published agent in the tenant.

Cursor (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "assistant": {
      "url": "https://runtime.example/v1/mcp",
      "headers": {
        "Authorization": "Bearer ara_<prefix><secret>"
      }
    }
  }
}
```

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "assistant": {
      "type": "http",
      "url": "https://runtime.example/v1/mcp",
      "headers": {
        "Authorization": "Bearer ara_<prefix><secret>"
      }
    }
  }
}
```

A generic client posts JSON-RPC to the same URL:

```bash
curl -s https://runtime.example/v1/mcp \
  -H "Authorization: Bearer ara_<prefix><secret>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

`tools/call` takes `message`. A write uses `write.tool` and `write.arguments`. If the policy gate holds the write, the tool result text is `Approval required` and `structuredContent.status` is `approval_required`.

## Errors, rate limits and versioning

The `/v1` surface follows the platform [API conventions](../05-contracts/api-conventions.md):

- **Errors** are RFC 9457 Problem Details with a stable `code` (switch on `code`, not the HTTP
  phrase): `401 unauthenticated` (missing/invalid/expired key), `404 not_found` (another key's
  run, or an unpublished agent — existence is never revealed), `409 idempotency_key_reused`,
  `429 rate_limited`, `429 quota_exceeded`. See the
  [code table](../05-contracts/api-conventions.md#5-errors-rfc-9457-problem-details).
- **Rate limits & quota** are per key. Every response carries `RateLimit-Limit`,
  `RateLimit-Remaining` and `RateLimit-Reset`; a `429 rate_limited` carries `Retry-After`. Each
  key has a requests-per-minute limit (`rateLimitRpm`) and a monthly quota (`monthlyQuota`,
  `0` = unlimited).
- **Idempotency**: message send accepts `Idempotency-Key`; the same key and body return the
  stored reply without starting a second run; a different body is `idempotency_key_reused`.
- **Versioning**: additive changes happen in `/v1` — ignore unknown response fields. A breaking
  change ships under a new major path. Responses carry `API-Version: 1`. `GET /v1` returns
  `{"version": "1"}`.
- **Streams**: `POST` with `"stream": true`, and `GET /v1/agents/{slug}/runs/{runId}/events`,
  are `text/event-stream`. Resume with `Last-Event-ID` (a sequence or `{runId}:{seq}`). The
  server replays from the shared run-event stream, sends `: ping` heartbeats while the run
  is still working, and closes after the tail. `Accept: application/json` on the events
  route returns one cursor page (`items`, `nextCursor`, `hasMore`).

## Rotating and revoking a key

Rotate a key from the Expose tab (or `POST /api/v1/agents/{agentId}/api-keys/{keyId}:rotate`):
the new secret is shown once and the old one stops working immediately. Revoke deletes it;
later calls are `401`. Keys are stored as a SHA-256 hash and never returned after creation.

## A2A

See [a2a.md](a2a.md).
