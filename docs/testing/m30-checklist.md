# M30 checklist

The industry pack is gone. Chat, tools, documents, knowledge, connectors, orchestration and the external API stay.

The provider key is read from `AR_CERT_LLM_API_KEY` at runtime. This file does not contain the value. Do not print that variable.

## Start

Ports 5432, 6379 and 7233 were already this project's Postgres, Valkey and Temporal. Ports 3000, 8000, 8001 and 8013 were already this project's web and services, so the proof used a separate API and web:

```bash
[ -n "$AR_CERT_LLM_API_KEY" ] && echo present || echo absent
make migrate
# fresh database
docker exec agentic-runtime-postgres-1 psql -U ar_owner -d postgres -c "CREATE DATABASE m30_fresh OWNER ar_owner;"
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5432/m30_fresh' \
  uv run alembic -c libs/ar_domain/alembic.ini upgrade head
AR_DATABASE_URL='postgresql+asyncpg://ar_owner:ar_owner@127.0.0.1:5432/m30_fresh' \
  uv run python scripts/seed.py
AR_DATABASE_URL='postgresql+asyncpg://ar_app:ar_app@127.0.0.1:5432/m30_fresh' \
  AR_PORT=18131 AR_TEMPORAL_ADDRESS=127.0.0.1:1 uv run ar-api
# web, from apps/web, so it does not take the server already on 3000
API_PROXY_URL=http://127.0.0.1:18131 AR_NEXT_DIST=.next-m30 pnpm exec next dev --port 18132
M30_EVIDENCE=/tmp/m30-proof.json AR_PROOF_API=http://127.0.0.1:18131 uv run python scripts/m30_proof.py
```

`AR_TEMPORAL_ADDRESS=127.0.0.1:1` keeps the turn in the API process. The Temporal worker already running is bound to the other database, so it must not take these runs.

Model: `Qwen/Qwen3-32B` through DeepInfra (`https://api.deepinfra.com/v1/openai`).

## What to expect

1. `make migrate` on an empty database finishes at revision `0031` and does not create a `grc` schema.
2. Sign in as `admin@dev.local` and land on Chat.
3. Create an agent, attach a document and a knowledge base, and ask a question. The answer cites the uploaded text.
4. On a database that already has the retired schema, `make migrate` drops that schema and leaves the other rows.
5. The shell has no industry entry. `/grc` and `/grc/audit` show **Page not found**.
6. `AR_GRC_PACK_ENABLED` is not a setting.

## Proof

| Item | Result |
|---|---|
| Key present | `present` |
| Fresh migrate | Database `m30_fresh`. `alembic_version` is `0031`. `information_schema` count for schema `grc` is 0. Seed wrote 1 tenant and 4 users. |
| Default `make migrate` | Database `agentic_runtime` moved `0030` → `0031`. |
| Document check | Verdict `met`. Reason: the document states the warehouse code `ND-1844-QUILL`. Citation anchor `p1-s0`, page 1. |
| Knowledge citation | Run `01a1a7d5-d462-7535-bfa5-054535cda492` completed. Text: `The warehouse code for the north dock is ND-1844-QUILL [1].` Collection `m30-library-1793817164` indexed 1 chunk. |
| Tool call | Run `01a1a7d5-dddd-7387-8418-10d3a149d558` completed. `general.code` printed `323` (`17 * 19`). |
| Connector call | GitHub read of `octocat/Hello-World` README completed. Summary: `The first line of the README file is: "Hello World!"` |
| Child run | Run `01a1a7d6-06ba-7394-bd81-3240624b9097` completed with 2 children. Summary: `RED and BLUE.` |
| External REST | `POST /v1/agents/m30-exposed-1793817164/conversations/.../messages` completed. `output` is `4`. |
| External MCP | `POST /v1/agents/m30-exposed-1793817164/mcp` `tools/list` returned HTTP 200. |
| Existing database | `m30_prior` was migrated with the pre-M30 history to `0030`, then the pack history to `0002`. One control, one installed pack row and one flag were inserted. Revision `0031` left `alembic_version` at `0031`, schema count 0, pack rows 0, flag rows 0, and the tenant and plan rows at 1. |
| Flag gone | `AR_GRC_PACK_ENABLED` remains only in this checklist, as the name of the setting that was removed. |
| Screenshots | `docs/testing/m30/` light and dark, desktop (1440) and mobile (390): chat, builder, documents, knowledge, connectors, orchestration, the agent editor, and the retired route. The Expose tab did not finish hydrating in this headless session (Next blocked the dev socket from `127.0.0.1`). The REST and MCP calls above are the live proof of that surface. |
| Walkthrough | `docs/testing/m30/walkthrough.webm` |

## Counts

| | Before | After |
|---|---|---|
| Pack files | 89 files, 13,182 lines | 0 |
| Pack HTTP paths in `openapi.json` | 77 | 0 |
| Generated client files whose names contained the pack | 274 | 0 |
| Pack doc pages | 8 | 0 |
| Pack screenshots under `docs/testing/m20` | 88 | 0 |

## Remaining text hits

A case-insensitive search still finds the schema name in revision `0031` and its integration test, the old `/grc` deep-link checks in Playwright, historical plan notes, and base64 integrity strings in `pnpm-lock.yaml` that happen to contain those three letters. None of those are a setting, a route in the shell, or a package.
