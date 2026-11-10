# GRC flows — end-to-end proof on merged `main` (9 Nov 2026)

A full end-to-end run of the GRC flows on **production `main`** after the Keycloak removal
(#158) and the GRC screenshot refresh (#157) merged. This proves the platform and its generic
document/knowledge tools still work on GRC-shaped inputs with the new **in-app userid/password
sign-in** (no external identity provider) and a real model (`Qwen/Qwen3-32B` via DeepInfra).

Harness: `scripts/grc_proof.py`. Stack: the lean shared-infra setup — the host's Postgres
(pgvector), Redis and minio + OPA, the api/model-gateway/mcp-gateway/web as host processes, a
**fresh** `agentic_runtime` database migrated to head (`0037`) and seeded. **No Keycloak container.**

## Headline

**The platform works end-to-end on merged `main`, signed in with a password.** From an empty
database, through the password login form, to the GRC screens and a real model: **15/18 asserted
checks passed** — the generic document actions are prompt-driven across SOC 2, ISO 27001 and CCM,
and no decoy control is hallucinated. The 3 misses are the same two known findings as the 9 Nov
pre-merge run (narrative variance and the RAG embedding path), not regressions.

## Proof screenshots (`shots-merged/`)

| Screenshot | Shows |
|---|---|
| `login-form` | The new **userid/password** sign-in form (no "Continue with SSO", no Keycloak) |
| `documents` | The 6 GRC fixtures uploaded and "Ready" (policy v1/v2, SOC 2 excerpt, CCM, ISO 27001, SOC 2 subset) |
| `agents` | The published `GRC Analyst` agent alongside the seeded assistant/builder/helpdesk |
| `gap-result` | A live SOC 2 gap table: Control / Verdict (with confidence) / Evidence (anchored) / Gap — MFA flagged `partial (0.6)` ("recommended… but must be enforced"), access control `met (0.95)` |

Each is captured in light and dark.

## Results (15/18, `Qwen/Qwen3-32B`)

| Flow | Check | Result |
|---|---|---|
| A. Gap analysis (SOC2/ISO/CCM) | prompt fires `check`/`gaps`/`read` | **PASS** ×3 |
| A. Gap analysis | decoy control returns `not_found` | **PASS** ×3 (MARS-1, A.9.99, SEF-99) |
| A. Gap analysis | agent surfaces the MFA weakness | SOC2 **PASS**, ISO **PASS**, CCM **FAIL** (F1) |
| B. Rewrite | prompt fires a rewrite action | **PASS** |
| B. Rewrite | proposal on the resolved anchor (`p1-s2`) + strengthens MFA | **PASS** |
| C. Extract | prompt fires an extract action | **PASS** |
| C. Extract | encryption-at-rest value (AES-256) correct | **PASS** |
| D. Grounded RAG | prompt fires `knowledge.search` | **PASS** |
| D. Grounded RAG | grounded answer from the trust library | **FAIL** — `knowledge.search` errored (F2) |
| Defect | OQ-66 redaction not corrupting gap evidence | **PASS** (clean) |

## Findings (unchanged from the 9 Nov pre-merge run — not regressions)

- **F1. Narrative gap-table variance.** The gap tools fire every time, but the agent's *prose*
  table is model-dependent — SOC 2 and ISO rendered the MFA-weakness narrative, CCM did not on this
  run. The structured `:check`/`:gaps` result is the reliable surface.
- **F2. `knowledge.search` (RAG) errored.** The embedding/vector retrieval path with the DeepInfra
  `bge-m3` alias returned an error; the agent honestly reported it rather than inventing an answer.
  Gap/rewrite/extract (no embeddings) are unaffected.

## What this proves about the auth change

Sign-in is now the product's own password check end to end: a fresh seed sets the dev admin's
argon2id password, the login form posts `POST /api/v1/auth/login`, and the issued `ar_session`
drives every GRC screen and REST call above — with no Keycloak container running.

## How to reproduce

Bring up the lean stack (shared Postgres/Redis/minio + OPA, api/model-gateway/mcp-gateway/web as
host processes; temporal skipped → synchronous runs), migrate + seed, then:

```bash
# sign in with the password and capture the session cookie
curl -s -i -X POST http://127.0.0.1:8005/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@dev.local","password":"dev-password"}'   # -> ar_session / ar_csrf
# then the asserting proof against the real model
AR_GRC_BASE=http://127.0.0.1:8005 AR_GRC_KEY="$(cat .secrets/deepinfra_api_key)" \
  uv run python docs/testing/grc-flows/scripts/grc_proof.py
```
