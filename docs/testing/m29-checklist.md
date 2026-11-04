# M29 checklist

| Check | Result |
|---|---|
| Agent key is hashed and shown once | Unit test `test_key_is_hashed_and_shown_once`. A later list has the prefix and not the secret. |
| REST answer with the real model | `scripts/m29_proof.py` against `http://127.0.0.1:18129`. `What is 2 + 2?` returned `4`. |
| Streaming call | The same agent, `stream: true`, HTTP 200 and `text/event-stream` data. |
| Idempotent retry is one run | The retry header was `idempotent-replayed: true` and the run id matched. |
| Missing key refused | HTTP 401, detail `agent api key is required`. |
| Revoked key refused | HTTP 401, detail `agent api key was revoked`. |
| MCP lists the agent and calls it | `tools/list` returned `agent_m29_exposed`. `tools/call` for `5 + 5` returned `10`. |
| A2A card and task send | Card URL ends in `/v1/agents/m29-exposed/a2a`. `message/send` for `3 + 3` returned artifact `6`. |
| This platform calls a remote A2A agent | `control.a2a_call` called a peer on `127.0.0.1:18130`. The peer used Qwen3-32B. The tool text was `12`. |
| Rate limit trips | A key with `rateLimitRpm` 2 returned 200, 200, then 429. |
| External write returns approval required | MCP write of `control.propose_change` returned `approval_required` and an approval id. |
| Another key cannot read the stream | API test returns 404 and no events. |
| Screenshots | `docs/testing/m29/desktop-*.png` and `mobile-*.png`, light and dark. |
| OpenAPI | `GET /v1/openapi.json` and [docs/agent-api/openapi.json](../agent-api/openapi.json). |

A2A push notifications, gRPC and task-list pagination are not implemented. See [OQ-64](../open-questions.md) and [a2a.md](../agent-api/a2a.md).
