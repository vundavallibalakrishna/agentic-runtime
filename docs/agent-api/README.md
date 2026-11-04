# Calling an agent from another product

A published agent has its own keys. Create one on the agent's Expose tab. The secret is shown once. Send it as `Authorization: Bearer ara_...`.

The contract is `GET /v1/openapi.json`. A copy generated from those routes is [openapi.json](openapi.json).

Replace `https://runtime.example` and `ara_...` with the origin that serves `/v1` and a real key.

## REST

Create a conversation, then send a message. `Idempotency-Key` makes a retry return the same run.

```bash
curl -s https://runtime.example/v1/agents/assistant/conversations \
  -H "Authorization: Bearer ara_example" \
  -H "Content-Type: application/json"
```

```bash
curl -s https://runtime.example/v1/agents/assistant/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer ara_example" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 4b1c0d2e-6f7a-4b8c-9d0e-1a2b3c4d5e6f" \
  -d '{"text":"What is 2 + 2?"}'
```

Stream the same call with `"stream": true`. The response is `text/event-stream` with `delta` events and a final `done` event.

```javascript
const base = "https://runtime.example/v1/agents/assistant";
const headers = {
  Authorization: "Bearer ara_example",
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
  -H "Authorization: Bearer ara_example" \
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
        "Authorization": "Bearer ara_example"
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
        "Authorization": "Bearer ara_example"
      }
    }
  }
}
```

A generic client posts JSON-RPC to the same URL:

```bash
curl -s https://runtime.example/v1/mcp \
  -H "Authorization: Bearer ara_example" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

`tools/call` takes `message`. A write uses `write.tool` and `write.arguments`. If the policy gate holds the write, the tool result text is `Approval required` and `structuredContent.status` is `approval_required`.

## A2A

See [a2a.md](a2a.md).
