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
| `tasks/cancel` | Mark the task canceled and POST any saved webhook |
| `tasks/list` | One page of this key's tasks. `pageSize` defaults to 20 and is capped at 100. `pageToken` is the last task id from the previous page. The result has `tasks` and `nextPageToken` |
| `tasks/pushNotificationConfig/set` | Store `url` and optional `token` for one task. The token is returned to this key on get. It is not written to the audit detail |
| `tasks/pushNotificationConfig/get` | The config for this key and task |
| `tasks/pushNotificationConfig/delete` | Remove that config |
| `tasks/pushNotificationConfig/list` | The configs for one task |

`message/send` accepts `configuration.pushNotificationConfig`. When the task is saved or canceled, the server POSTs the task to each saved URL. A failed POST does not fail the task. The card sets `pushNotifications` to true.

A task that is waiting on approval has `status.state` of `input-required` and the text `Approval required`.

Still not implemented, and not claimed:

- `tasks/resubscribe`
- gRPC

Those methods return JSON-RPC error `-32601`. See [OQ-64](../open-questions.md).

## Calling a remote agent

Bind `control.a2a_call` on the caller. Arguments are `url` (the remote agent card), `message`, and `secret_name`. Store the remote bearer token with `POST /api/v1/secrets` under that name. The tool reads the secret on the server. Do not put the token in the instructions or the tool arguments the model writes.

The URL must pass the public egress check. Loopback is allowed only in `dev`, `ci` and `test`.
