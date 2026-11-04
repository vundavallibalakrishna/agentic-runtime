# A2A

The agent card is served at:

- `GET /.well-known/agent-card.json` with `Authorization: Bearer ara_...` (the key selects the agent)
- `GET /v1/agents/{slug}/.well-known/agent-card.json` with the same header

The card's `url` is `POST /v1/agents/{slug}/a2a`. `POST /v1/a2a` uses the key's agent.

Implemented JSON-RPC methods:

| Method | Behaviour |
|---|---|
| `message/send`, `tasks/send` | Run the agent and return the task, including an artifact |
| `message/stream`, `tasks/sendSubscribe` | The same task as `text/event-stream` |
| `tasks/get` | The task this key created |
| `tasks/cancel` | Mark the task canceled |

A task that is waiting on approval has `status.state` of `input-required` and the text `Approval required`.

Not implemented, and not claimed:

- `tasks/pushNotificationConfig/set`, `get`, `delete`, `list`
- `tasks/resubscribe`
- gRPC
- listing every historical task

Those methods return JSON-RPC error `-32601` with `Method not implemented` or `Method not found`. See [OQ-64](../open-questions.md).

## Calling a remote agent

Bind `control.a2a_call` on the caller. Arguments are `url` (the remote agent card), `message`, and `secret_name`. Store the remote bearer token with `POST /api/v1/secrets` under that name. The tool reads the secret on the server. Do not put the token in the instructions or the tool arguments the model writes.

The URL must pass the public egress check. Loopback is allowed only in `dev`, `ci` and `test`.
