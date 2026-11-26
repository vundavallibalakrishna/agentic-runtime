# Chat from your application

Two ways in. A **service-account key** uses `/api/v1/conversations` and can do everything
a signed-in person can. An **agent key** uses `/v1/agents/<slug>/...` and reaches one
published agent. Replace `{{BASE_URL}}` and `{{AGENT_SLUG}}`.

## A conversation with an agent key

```bash
curl -s -X POST {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}/conversations \
  -H "Authorization: Bearer $AGENT_KEY"

curl -s {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"text":"What is our notice period?"}'
```

The reply, once the agent has finished:

| Field | Meaning |
|---|---|
| `output` | the answer as text |
| `content` | the answer as parts: text, files, images, citations, follow-ups |
| `status`, `finishReason` | how the turn ended |
| `usage` | `tokensIn`, `tokensOut`, `toolCalls`, `costMicros`, `elapsedMs` |
| `runId`, `conversationId` | to fetch the trace or send the next message |

Send the next message to the same conversation to continue it. For one question with no
history, `POST /v1/agents/{{AGENT_SLUG}}:run` with the same body does both steps.

Body fields: `text`, `fileIds`, `attachmentIds`, `collectionIds`, `taskTemplate`, `items`,
`responseFormat`, `suggestFollowups`, `stream`, `wait`, `callbackUrl`.

## Attach documents

Upload first, then name the file on the message.

```bash
curl -s {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}/files \
  -H "Authorization: Bearer $AGENT_KEY" -F "upload=@contract.pdf"

curl -s {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"text":"What is the notice period in this contract?","fileIds":["'$FILE_ID'"]}'
```

- `fileIds` and `attachmentIds` both take file ids and are treated alike.
- A file can be used when the caller uploaded it, when it is in a collection the caller
  can read, or when it was given to the agent.
- `collectionIds` points the turn at whole knowledge bases.
- With a service-account key the same fields go on
  `POST /api/v1/conversations/$CONVERSATION_ID/messages`, and files are uploaded with
  `POST /api/v1/files:upload`.

## Mention documents

In the product, type `@` in the message box, or press **Documents**, and pick one or more
documents from the library. They appear as chips on the message.

Over the API a mention is the same thing as an attachment: put the file id of each
document in `fileIds`. A library document's file id is the `fileId` field of
`GET /api/v1/library-documents`.

## Read citations

A cited answer has `citation_ref` parts in `content`:

```json
{"type": "citation_ref", "index": 1,
 "citation": {"index": 1, "sourceKind": "knowledge", "title": "Handbook",
              "uri": "https://example.com/handbook", "snippet": "The desk opens at 08:30.",
              "pageFrom": 1, "pageTo": 1, "documentId": "...", "collectionId": "..."}}
```

`sourceKind` is `knowledge` for a knowledge base and `document` for an attached file; a
`document` citation has `anchor`, `page` and `fileId`. Read citations from `content` on
the reply. The event stream does not carry all of them.

## Stream, or do not wait

- `"stream": true` returns `text/event-stream`: the run's events (`message.delta` with
  `text`, `tool_call.*`, `subagent.*`, `run.completed`), then a final `done` event with
  `output` and `status`. The events are sent once the turn has finished.
- `"wait": false` returns `202` with `runId` and `eventsUrl` at once. Follow
  `GET /v1/agents/{{AGENT_SLUG}}/runs/$RUN_ID/events`, or give a `callbackUrl`.
- With a service-account key, `GET /api/v1/runs/$RUN_ID/events` streams a run as it
  happens. Resume with `Last-Event-ID`.

## A structured answer

Send a JSON Schema as `responseFormat`. The answer is JSON that matches it, or the turn
fails saying it could not produce one.

```bash
curl -s {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}:run \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"text":"Extract the parties.","fileIds":["'$FILE_ID'"],
       "responseFormat":{"type":"object","properties":{"parties":{"type":"array","items":{"type":"string"}}},"required":["parties"]}}'
```

## The same from Python and JavaScript

```python
import httpx

api = httpx.Client(base_url="{{BASE_URL}}", headers={"Authorization": f"Bearer {AGENT_KEY}"}, timeout=300)
reply = api.post("/v1/agents/{{AGENT_SLUG}}:run", json={"text": "What are your opening hours?"}).json()
print(reply["output"])
for part in reply["content"]:
    if part["type"] == "citation_ref":
        print(part["citation"]["title"], part["citation"]["uri"])
```

```javascript
const reply = await fetch("{{BASE_URL}}/v1/agents/{{AGENT_SLUG}}:run", {
  method: "POST",
  headers: { Authorization: `Bearer ${AGENT_KEY}`, "Content-Type": "application/json" },
  body: JSON.stringify({ text: "What are your opening hours?" }),
}).then((response) => response.json());
console.log(reply.output);
```

## Other ways to reach an agent

| Way | Where |
|---|---|
| MCP | `POST /v1/mcp` or `/v1/agents/<slug>/mcp`, agent key |
| A2A | `/v1/agents/<slug>/a2a` and the agent card; see [a2a.md](a2a.md) |
| OpenAI-compatible | `POST /api/v1/openai/chat/completions`, service-account key, `model` is the agent's slug; `GET /api/v1/openai/models` lists the agents as models |
| Research | `POST /v1/research/runs` starts a longer, multi-step research run with an agent key; `GET /v1/research/runs/{run_id}` and `/v1/research/runs/{run_id}/events` follow it |
