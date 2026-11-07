# The fresh-tenant run (release gate)

`fresh_run.mjs` drives a real, running stack through the flows a new customer meets —
sign-in, model setup, a chat answer, a knowledge search, a knowledge question in chat,
memory, and a second user — and writes a screenshot and a pass/fail for each. It is the
[fresh-tenant run](../../docs/testing/fresh-tenant-2026-11-06/report.md) made repeatable.

It needs a **real model endpoint**, so it is a **pre-release check, not a CI job** (CI has
no model). Run it against a stack that is up and has a seeded tenant.

## What it checks

| Step | What it proves | Deterministic? |
|---|---|---|
| sign-in | the seeded admin signs in through the real identity provider | yes |
| configure-models | a provider, a chat model and an embedding model are added on the screen (skipped when already set) | yes |
| chat-answers | the agent answers a plain question with the real model | yes |
| knowledge-search | a collection is indexed and searched by meaning | yes |
| knowledge-in-chat | the agent answers from the library | no — the default assistant's tool choice is a known gap ([F66](../../docs/testing/fresh-tenant-2026-11-06/report.md), M39); this step **skips** rather than fails when it does not search |
| memory-recall | a fact saved on the Memory screen is recalled in a later chat | yes |
| second-user | a second seeded user signs in and sees the workspace | yes, when `AR_FRESH_SECOND_EMAIL` is set |

A step that is not configured for the run (no model key needed because models are already
set; no second user given) is recorded as **skip**, not a failure. The gate fails only
when a step that should work does not.

## Run it

1. Bring up a stack with its dependencies and a real model endpoint configured, and seed a
   tenant whose slug is **not** `dev`:

   ```bash
   uv run python scripts/seed_tenant.py --slug acme --name "Acme" \
       --admin-email ada@acme.example --admin-name "Ada Lovelace"
   ```

2. Point the gate at it and run (no secret is written to this repo; pass them by file or
   environment):

   ```bash
   AR_FRESH_WEB=http://localhost:3000 \
   AR_FRESH_ADMIN_EMAIL=ada@acme.example \
   AR_FRESH_ADMIN_PASSWORD_FILE=/path/to/admin-password \
   AR_FRESH_MODEL_BASE_URL=https://your-model-endpoint/v1 \
   AR_FRESH_MODEL_KEY_FILE=/path/to/model-key \
   AR_FRESH_CHAT_MODEL=Qwen/Qwen3-32B \
   AR_FRESH_EMBED_MODEL=BAAI/bge-m3 \
   AR_FRESH_OUT=./fresh-run-out \
   node scripts/fresh_run/fresh_run.mjs
   ```

   `scripts/fresh_run/seed_and_run.sh` wires the seed and the gate into one command.

The gate writes `summary.md`, `summary.json` and a numbered screenshot per step to
`AR_FRESH_OUT`, and exits non-zero if any step fails. Every configuration value is listed
in the header of `fresh_run.mjs`.
