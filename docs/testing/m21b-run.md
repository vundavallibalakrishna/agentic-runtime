# M21b run guide

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

Sign in at the web URL with `admin@dev.local` via dev sign-in. Chat is the first screen. The assistant can run Python, a shell, workspace files, page fetch, web search and HTTP.

## Search

Search does nothing useful until a provider is configured. Either:

1. Set `AR_SEARCH_PROVIDER` to `brave` or `tavily` and `AR_SEARCH_API_KEY` to that provider's key, or
2. Create a secret (Secrets) and, on Tools, choose the provider and type the secret's name. Save access.

The key is not shown again and is not written into traces. With no key, `general.search` tells the agent how to configure it and returns no hits.

## Egress

Fetch and HTTP only call hosts on the tenant egress allow list, plus any hosts named on that agent's tool limits. Private addresses stay denied. Loopback is allowed only when `AR_ENV` is `dev`, `ci` or `test` and the host is listed.

## Sandbox

Code and shell start with network off. Enable "Allow network in the sandbox" on the agent to let a command open an allowlisted URL. See [m21b-sandbox](../06-security/m21b-sandbox.md).

The real-model proof uses `AR_CERT_LLM_API_KEY` from the environment only. Do not copy that value into a file, a log, a screenshot or a commit.
