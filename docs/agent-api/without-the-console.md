# Using an agent without the console

People who approve work, and systems that start work, do not need an account in the web console.

## Call an agent

`POST /v1/agents/{slug}:run` with `Authorization: Bearer <agent key>`. Send `wait: false` and `callbackUrl` to get the result as a signed POST (`X-Signature`, the tenant run-callback secret) instead of holding the connection. Upload a file first with `POST /v1/agents/{slug}/files`. The same key opens MCP (`POST /v1/agents/{slug}/mcp`) and A2A (`POST /v1/a2a`).

Keys are created in the console, or by someone who already has `agents:edit`, and are shown once.

## Decide an approval from a link or a card

When a tool needs a person, and the tenant has a Slack or Teams binding (or the approver has linked their account), the approver gets a card with Approve, Reject and Review. The review link is `{AR_PUBLIC_URL}/review/{token}`. It shows that one request, rendered from the tool's JSON Schema, and accepts an edit. Approving with edited values keeps the original and the edited arguments.

Mail goes to the approvers named by the policy (the requester, a list of users, a group, or the agent owner). `AR_APPROVAL_NOTIFY_EMAIL` adds one more address. It is empty unless an install sets it.

If the install signs people in with OIDC (`AR_AUTH_MODE=oidc`), the link still names the item and the approver must sign in as that person. Otherwise the signed link is the credential. A guest session cannot decide.

## Receive events

`POST /api/v1/webhooks` with `webhooks:manage` stores a subscription on `outbound_webhooks`. The response includes `secret` once. Each delivery is a camelCase JSON body signed with `X-AR-Signature: t=<unix>,v1=<hex>`, over `timestamp + "." + body`, plus `X-AR-Event-Id` and `X-AR-Topic`. Retries follow the backoff in `ar_domain.events.sign`. `POST /api/v1/webhooks/{id}/deliveries/{deliveryId}:redeliver` sends one again.

Public topics include `approval.requested`, `approval.decided`, `run.completed`, `run.failed`, `document.ingested` and `extraction.completed`. Payloads carry ids and status, not document text.

A customer Slack workspace, Teams tenant or mail server was not used to prove the live send. The card is built and, when the binding stores a bot token or an incoming webhook URL, posted by the channels service. The signature check is proven against a local receiver.
