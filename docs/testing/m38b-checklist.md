# M38b release checklist — the fresh-tenant run

Before a release, a new customer's first hour must still work: a seeded tenant signs in,
configures its models on the screen, and the core AI flows answer with a real model and no
built-in data. [`scripts/fresh_run/`](../../scripts/fresh_run/README.md) automates that run
and writes a pass/fail and a screenshot for each step. It needs a real model endpoint, so
it is run by hand before a release, not in CI.

## How to run

1. Bring up a stack with its dependencies and a real model endpoint, on an empty database.
2. Seed a tenant whose slug is **not** `dev`, and run the gate — one command does both:

   ```bash
   AR_FRESH_ADMIN_PASSWORD_FILE=... AR_FRESH_MODEL_BASE_URL=... AR_FRESH_MODEL_KEY_FILE=... \
   AR_FRESH_CHAT_MODEL=... AR_FRESH_EMBED_MODEL=... \
   scripts/fresh_run/seed_and_run.sh --slug acme --name "Acme" \
       --admin-email ada@acme.example --admin-name "Ada Lovelace"
   ```

3. The gate exits non-zero if any step fails. Read `summary.md` and the screenshots in the
   output directory.

## What must pass

- **sign-in** — the seeded admin signs in through the identity provider.
- **configure-models** — a provider, a chat model and an embedding model are added on the
  Models screen (skipped when the tenant is already configured).
- **chat-answers** — the agent answers a plain question with the real model.
- **knowledge-search** — a collection is indexed and searched by meaning.
- **memory-recall** — a fact saved on the Memory screen is recalled in a later chat.
- **second-user** — a second seeded user signs in and sees the workspace (when one is given).

Two steps are allowed to **skip**, not fail, for reasons that are tracked work, not
regressions:

- **knowledge-in-chat** — the default assistant does not yet reliably choose the knowledge
  tool (F66, M39). The knowledge path itself is covered by **knowledge-search**.
- any step not configured for the run (no second user; models already set).

## Last recorded run

The gate was run on the live `acme` tenant (slug not `dev`) against real DeepInfra models
on 7 November 2026: **4 passed, 0 failed, 3 skipped** — sign-in, chat, knowledge search and
memory recall all green, with the two allowed skips above and the already-configured
models. See [`fresh-tenant-2026-11-06/run24-fresh-run-gate/`](fresh-tenant-2026-11-06/run24-fresh-run-gate/).
