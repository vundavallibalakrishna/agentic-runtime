# Connect your platform

This guide takes another system from nothing to a working integration: calling the API,
saving documents, and chatting with an agent. Every call here was run against a real
install. Replace `{{BASE_URL}}` with the address of the workspace and keep keys in your
own secret store.

## 1. What you need from the workspace owner

| You want to | Ask for | It looks like | It works on |
|---|---|---|---|
| Call the platform as a program: upload files, fill a knowledge base, manage agents, chat | a **service-account key** | `ak_<id>.sk_<secret>` | `/api/v1/...` |
| Let another product talk to **one** published agent | an **agent key** | `ara_<id><secret>` | `/v1/agents/<slug>/...` |

The two are not interchangeable. An agent key on `/api/v1` is refused with `403`, and a
service-account key is not read on `/v1`.

A workspace administrator creates a service account and its key on **Settings → Service
accounts**, choosing what the account will do. The key is shown once. An agent key is
created on the agent's **Expose** tab.

What a service account creates (files, documents, conversations) belongs to that account,
not to a person.

## 2. Check that the key works

```bash
export CURA_KEY='ak_....sk_....'
curl -s {{BASE_URL}}/api/v1/agents -H "Authorization: Bearer $CURA_KEY"
```

`200` with `{"items": [...]}` means the key is valid and may read agents. `401` means the
key is wrong, expired or revoked. `403` names the permission the key lacks.

## 3. Send files and build a knowledge base

Upload a file. The form field names are `upload` and, optionally, `mime_type`:

```bash
curl -s {{BASE_URL}}/api/v1/files:upload \
  -H "Authorization: Bearer $CURA_KEY" \
  -F "upload=@handbook.md" -F "mime_type=text/markdown"
```

The reply has the file's `id` and, once it is read, a `documentId` in the document
library. `GET /api/v1/files:limits` gives the types and the size this workspace accepts.

Create a knowledge base (a collection) and add the file to it:

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/collections \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"slug":"handbook","name":"Handbook"}'

curl -s {{BASE_URL}}/api/v1/knowledge/collections/$COLLECTION_ID/documents \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"fileIds":["'$FILE_ID'"]}'
```

The workspace needs an embedding model before a collection can be created; without one
the reply is `409` and says so. Search it:

```bash
curl -s {{BASE_URL}}/api/v1/knowledge/search \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"query":"when does the visitor desk open","collectionIds":["'$COLLECTION_ID'"],"topK":5}'
```

More ways to add documents (a web address, a whole site from its sitemap, pasted text) are
in [Documents and knowledge bases](documents-and-knowledge.md).

## 4. Chat with an agent

With a service-account key, on `/api/v1`:

```bash
curl -s {{BASE_URL}}/api/v1/conversations \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"agentId":"'$AGENT_ID'"}'

curl -s {{BASE_URL}}/api/v1/conversations/$CONVERSATION_ID/messages \
  -H "Authorization: Bearer $CURA_KEY" -H "Content-Type: application/json" \
  -d '{"text":"Summarise the handbook.","fileIds":["'$FILE_ID'"]}'
```

The second call answers `202` with `{message, run}`. Follow the run at
`GET /api/v1/runs/$RUN_ID/events` (server-sent events) and read the finished reply from
`GET /api/v1/conversations/$CONVERSATION_ID`.

With an agent key, on `/v1`, one call waits for the reply:

```bash
export AGENT_KEY='ara_....'
curl -s {{BASE_URL}}/v1/agents/{{AGENT_SLUG}}:run \
  -H "Authorization: Bearer $AGENT_KEY" -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"text":"What are your opening hours?"}'
```

The reply has `output` (the text), `content` (the parts, citations among them), `usage`
and `runId`. For a conversation with several turns, attaching and mentioning documents,
streaming, and structured answers, see [Chat from your application](chat.md).

## 5. Work that takes a long time

Send `"wait": false` to get `202` at once with `runId` and `eventsUrl`. Add
`"callbackUrl"` to be told when the run ends. The callback carries only
`{"runId", "status"}` and is signed; fetch the reply with
`GET /v1/agents/<slug>/runs/$RUN_ID`. Details and the signature check are in
[Without the console](without-the-console.md) and [Webhooks](webhooks.md).

A run that needs a person's approval stops with status `waiting_approval` until someone
decides it.

## 6. Put the chat on your own site

The workspace's **Channels** screen creates a widget and gives a script tag to paste into
your page. Your server signs a short-lived token for each signed-in person; the signing
secret never reaches the browser. See [Embed the chat](embed.md).

## 7. Let the agent call your platform

An agent reaches your system through tools. Import your OpenAPI document on the **Tools**
screen to turn its operations into tools, keep your credentials in a named connection, or
expose an MCP server. To be told about events, register a webhook
(`POST /api/v1/webhooks`). The other direction, calling an agent as a tool from your own
agent, is the MCP endpoint `/v1/mcp` and A2A ([a2a.md](a2a.md)).

## 8. Rules every call follows

- **Errors** are `application/problem+json` with a stable `code`. Switch on `code`.
- **Idempotency**: send `Idempotency-Key` on a `POST` that starts work. A retry with the
  same key and body returns the same result.
- **Rate limits**: `429` carries `Retry-After`. Agent keys have a per-minute rate and a
  monthly quota set where the key was made.
- **Lists** are paged: `{items, nextCursor, hasMore}`, with `limit` and `cursor`.
- **Field names** are camelCase. An unknown field in a request body is refused with `422`.
  Ignore fields in a reply that you do not know.
- **Keys**: the part before `.sk_` is safe to log; the secret is not. Rotating a key gives
  a new secret and stops the old one at once. Revoking stops the key.

What does not yet behave as the contract says is listed in
[Known differences](known-differences.md).
