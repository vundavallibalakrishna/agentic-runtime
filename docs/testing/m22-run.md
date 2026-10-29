# M22 run guide

Use ports that are not already taken. Do not stop Postgres, Temporal, Redis or apps on 8000, 8001 or 8013.

```bash
cp .env.example .env
# Point the host ports at a free block, then:
make ports-check
make up
make migrate
make seed
honcho start -f Procfile.dev
```

`AR_GRC_PACK_ENABLED` stays unset or `false`.

Sign in at the web URL with `admin@dev.local` via dev sign-in.

## Connections

Open Connections. Save a named connection (API key, bearer, basic, or OAuth). The secret field is a password input and the saved row does not show the value. Test uses the test URL and reports only the status. Rotate replaces the secret. Expiry, when set, is shown on the row.

`general.http` accepts `auth.connection` with that name. Imported and described tools store the name on the operation.

## MCP

On Tools, register a server. Transport is streamable HTTP, server-sent events, or stdio in the sandbox. Stdio takes a program such as `python /path/to/server.py` and runs with network off. Put the connection name in Connection name. After approval, the discovered tools appear in the registry. A tool the server marks read-only can run. Any other tool waits for approval. Refresh reports a changed manifest.

## OpenAPI

Paste an OpenAPI 3.x JSON document or give a public URL. List operations, select at most 40, and import. Documents over 2 MB are refused. GET and HEAD run. Other methods wait.

## A tool from a description

Write a sentence that includes the method and the URL, for example `GET https://example.com/zen using connection github`. Review definition shows the generated name, method, URL and risk. Save tool, then Test.

## Registry and agents

The registry lists source, status, last error, call count, timeout, rate and size. Enable and disable sit on each row. The agent editor can attach every MCP tool, every OpenAPI tool, every custom tool, or one tool. Tools that wait are labelled Asks first. Chat shows the method, URL and status for those calls.

## Real model

The proof uses `AR_CERT_LLM_API_KEY` from the environment only. Do not copy that value into a file, a log, a screenshot or a commit. The checklist records what the model actually did.
