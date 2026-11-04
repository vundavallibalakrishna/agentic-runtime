# M25 run

The API and web processes for this proof use ports that are not 8000, 8001 or 8013, and a Postgres that is not the operator database.

```bash
export AR_DATABASE_URL=postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:55449/agentic_runtime
export AR_PORT=18125
uv run alembic -c libs/ar_domain/alembic.ini upgrade head
uv run ar-api
```

In another shell, with `AR_CERT_LLM_API_KEY` set in the environment and not printed:

```bash
M25_API=http://127.0.0.1:18125 uv run python scripts/m25_proof.py
```

The script downloads the public M24 documents, builds a knowledge base, and asks an agent that uses Qwen/Qwen3-32B. Embeddings use `BAAI/bge-m3` on the same DeepInfra base URL. Evidence is written under the temp directory `m25-proof` with the provider key removed.

`scripts/m25_eval.py` asks a fixed set of questions of the indexed public documents and writes recall and citation counts into that evidence directory. The checklist copies those counts. They are not estimated.

Screenshots from Playwright are `docs/testing/m25/`. The walkthrough video is recorded with that spec (`video: on`).

Retrieval stops at 12,000 characters. A 492-page file is not placed whole in the prompt. See [M25](../09-plan/M25-knowledge-memory-skills.md).
