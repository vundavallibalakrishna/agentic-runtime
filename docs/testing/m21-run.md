# M21 run guide

Use ports that are not already taken by another local stack. Do not stop Postgres, Temporal, Redis or apps on 8000, 8001 or 8013.

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

Sign in at the web URL with `admin@dev.local` via dev sign-in. Chat is the first screen.

To connect a model, open Admin → Models, choose advanced, set the OpenAI-compatible base URL, the upstream model name and the key, then test the provider. The key is not shown again.

Create an agent from Agents → New agent → "Create and use", or edit one and choose Use in chat.

The real-model proof uses `AR_CERT_LLM_API_KEY` from the environment only. Do not copy that value into a file, a log, a screenshot or a commit. The checklist records the result, not the key.
