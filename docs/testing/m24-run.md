# M24 run

The API and web processes for this proof use ports that are not 8000, 8001 or 8013, and a Postgres that is not the operator database.

```bash
# isolated database and API, after the image dependencies are installed
export AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:55448/agentic_runtime
export AR_PORT=18124
uv run alembic -c libs/ar_domain/alembic.ini upgrade head
uv run ar-api
```

In another shell, with `AR_CERT_LLM_API_KEY` set in the environment and not printed:

```bash
M24_API=http://127.0.0.1:18124 uv run python scripts/m24_proof.py
```

The script downloads public documents, uploads them, and asks an agent that uses Qwen/Qwen3-32B to summarise, compare, check, find a missing passage, rewrite and redact. Evidence is written under the temp directory `m24-proof` with the provider key removed.

Screenshots from Playwright are `docs/testing/m24/`. The walkthrough video is recorded with that spec (`video: on`).

A 300-page file is not placed in the model prompt. Passages are about 1,000 characters. Retrieval keeps the page number and stops at 12,000 characters. See [spec 24 §3](../03-specs/24-documents.md#3-long-documents).
