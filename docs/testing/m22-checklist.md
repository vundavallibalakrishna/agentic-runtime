# M22 checklist

## Connections

- [x] API key, bearer, basic, OAuth authorization-code and client-credentials are accepted.
- [x] The secret is encrypted and is not returned by the API or a tool result.
- [x] Another user and another tenant receive 404.
- [x] Test, rotate and expiry are on the connection screen.
- [x] `general.http` and generated tools take a connection by name.

## MCP

- [x] Streamable HTTP discovery lists tools.
- [x] SSE and stdio transports exist. Stdio stays in the sandbox with network off.
- [x] `readOnlyHint` is auto-allowed. Every other MCP tool waits for approval.
- [x] A changed manifest is reported on refresh.
- [x] Results are labelled untrusted data.

## OpenAPI and described tools

- [x] An OpenAPI 3.x document can be previewed and imported with a selection.
- [x] Documents over 2 MB are refused. More than 40 operations must be selected.
- [x] GET runs. POST waits for approval.
- [x] A sentence becomes a reviewable tool with Test.

## Registry and builder

- [x] The registry shows source, status, last error, calls and limits, and can enable or disable a tool.
- [x] The editor attaches by source or by individual tool and marks tools that ask first.
- [x] Chat cards render MCP and OpenAPI calls.
- [x] `run.planned`, `tool.called`, `run.retried` and `run.checked` are copied into `audit_events` on flush.
- [x] A second model alias with the same name returns a conflict.

## Real model (Qwen/Qwen3-32B)

Recorded on 2026-10-29 against `https://api.deepinfra.com/v1/openai`. The key stayed in the environment. Provider test returned `ok` and `pong`.

The public GitHub REST spec is about 13 MB and the import preview rejected it for the 2 MB limit. The proof imported the public Petstore 3 spec (`https://petstore3.swagger.io/api/v3/openapi.json`) and selected `findPetsByStatus`. A local reference MCP server was `@modelcontextprotocol/server-everything` on streamable HTTP.

| Check | Result | Evidence |
|---|---|---|
| OpenAPI import used in chat | Pass | `petsapi.find_pets_by_status` GET HTTP 200. The answer quoted `"name": "Dog 1"` |
| MCP tools used in chat | Pass | `reference.echo` with `hello-from-mcp` returned `Echo: hello-from-mcp` |
| Tool by description | Pass | `probe.probe` called the described GET and the result was `authorized` |
| Secret never shown to the model | Pass | The connection response had `hasSecret` true and no secret. The tool preview says `authorized` and does not contain the bearer value. The evidence file was checked for the secret and the model key |
| Write waits for approval | Pass | `writer.writer` status `awaiting_approval`, risk `W2`. The local server received 0 writes |
| Injection string is not obeyed | Pass | `inject.inject` returned the PWNED instruction. The answer was `The injection was ignored.` |

## Screens

Light and dark, desktop and mobile, under `docs/testing/m22/`. Walkthrough: `docs/testing/m22/walkthrough.webm`.
