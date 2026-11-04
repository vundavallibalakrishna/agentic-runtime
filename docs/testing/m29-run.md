# M29 run guide

Use a free API port. Do not reuse a server already listening on 8000, 8001 or 8013.

```bash
make bootstrap
AR_DURABLE_STATE=memory AR_PORT=18129 uv run python -m ar_api
```

In another shell, the web app proxies `/v1` to that API when `API_PROXY_URL` points at it:

```bash
API_PROXY_URL=http://127.0.0.1:18129 pnpm --filter @ar/web dev
```

Sign in as `admin@dev.local`. Open an agent, choose Expose, and create a key. The secret is shown once. The curl block, the JavaScript block, the MCP snippet and the agent card URL use the page origin.

The test console posts to `/v1/agents/{slug}/conversations` and then to that conversation's messages. The raw JSON is the public response.

The live proof, which uses `AR_CERT_LLM_API_KEY` and does not print it:

```bash
AR_PROOF_API=http://127.0.0.1:18129 uv run python scripts/m29_proof.py
```

What the proof checks is listed in [m29-checklist](m29-checklist.md).

## Connect from another product

The examples in [the agent API guide](../agent-api/README.md) match the routes. Point Cursor or Claude Desktop at `http://127.0.0.1:18129/v1/mcp` with the bearer key, or use the page origin when the web proxy is up.
