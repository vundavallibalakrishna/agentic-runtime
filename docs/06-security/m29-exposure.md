# M29 exposure

## Keys

An agent API key is `ara_` plus a 12-character prefix plus a secret. The API returns the full key on create and on rotate. Later reads return the label, prefix, scope, rate limit, monthly quota, month count, last-used time and revoked time. The stored column is the SHA-256 hex of the full key. A lookup finds the prefix, then compares the hash in constant time. A missing prefix still runs a dummy compare.

Scope `agent` reaches only that agent. Scope `workspace` reaches published agents in the same tenant. Another tenant, another agent, or another key's run is a 404. Revoked keys are refused with `agent api key was revoked`. A request with no `Authorization: Bearer` key is refused with `agent api key is required`. A session cookie does not authorise `/v1`.

`/v1/openapi.json` is the only unauthenticated `/v1` route. It is the contract, and it contains no tenant data.

## Rate limits and quota

Each key has `rateLimitRpm` (default 60, maximum 6000) and `monthlyQuota` (default 10000, `0` means no cap). The minute window is process-local, the same way other rate buckets are (see [OQ-59](../open-questions.md) and [OQ-64](../open-questions.md)). The monthly counter is on the key row and is flushed with the key. A refused call is audited as `agent_api_call.refused` or `agent_api_key.denied`. The audit detail has the key label and a reason. It does not have the secret, the prompt, or the reply.

## External surface

| Path | Auth |
|---|---|
| `POST /v1/agents/{slug}/conversations` | agent key |
| `POST /v1/agents/{slug}/conversations/{conversationId}/messages` | agent key |
| `POST /v1/agents/{slug}/files` | agent key |
| `GET /v1/agents/{slug}/runs/{runId}` | agent key |
| `GET /v1/agents/{slug}/runs/{runId}/events` | agent key |
| `POST /v1/mcp` and `POST /v1/agents/{slug}/mcp` | agent key |
| `GET /.well-known/agent-card.json` and the agent card path | agent key |
| `POST /v1/a2a` and `POST /v1/agents/{slug}/a2a` | agent key |
| `GET /v1/openapi.json` | none |

Message send accepts `Idempotency-Key`. The same key and the same text return the stored reply and do not start a second run. A different body is `idempotency_key_reused`. The internal idempotency middleware does not apply on `/v1`, so two keys cannot share a slot.

Streaming reads the grant for that key and that run before any event is written. A different key receives 404 and no events.

## Writes

MCP `tools/call` may pass `write.tool` and `write.arguments`. The call goes through the same policy gate as a model tool call. A W2 write such as `control.propose_change` returns `Approval required` and `structuredContent.status = approval_required`. It does not run the write and it does not return an empty error.

## Egress

`control.a2a_call` loads the bearer token with `secret_name` from the named-secret store. The model does not receive the token. The URL is checked with the public-host guard used by other HTTP tools: http or https, private and link-local addresses denied, loopback allowed only when `AR_ENV` is `dev`, `ci` or `test`. A card URL is fetched, then the card's `url` is checked again before the task is sent.

Inbound `/v1` is the customer-facing surface. `/api/v1` stays on session authentication. The web app proxies `/v1` so the Expose test console can call the public path on the same origin. Operators who publish the API directly should put it behind the same TLS terminator as the rest of the product and should not leave it on an open network without the key check above.

## What was tested

Unit tests cover hashing, revocation, the rate window, the monthly quota, one-run idempotency, cross-key trace denial, workspace tool listing, approval-required writes, the agent card, an unimplemented A2A method, and a remote call that sends the named secret. The API tests cover a missing key, a revoked key, idempotent replay, a stream that a second key cannot read, MCP tool listing, and an approval-required write. The real-model proof is recorded in [m29-checklist](../testing/m29-checklist.md).

## Still incomplete

A2A push notifications, gRPC, and task-list pagination are not implemented. Those methods return JSON-RPC `-32601`. See [OQ-64](../open-questions.md).
