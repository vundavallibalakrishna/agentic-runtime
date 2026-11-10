# Agnostic production plan

Status: complete. Stage 9 is the exit. The single Alembic head is revision `0039`.

Stage 0 records the decisions. Later stages change the product. Core stays domain-agnostic: no industry in code, schemas, seeds, tools, prompts, tests, UI, or product docs. Industry solutions ship only as optional signed packs. The security audit log and four-eyes approvals stay in core.

Decisions: [ADR-0028](../02-architecture/adr/ADR-0028-agnostic-core.md) through [ADR-0034](../02-architecture/adr/ADR-0034-signed-pack-model.md).

Production means the Stage 9 exit has passed and core still passes the Stage 2 grep.

## Target architecture

```
browser (OIDC auth code)          integrators (JWT bearer via JWKS)
                 \                      /
                  +--------------------+
                  | API, stateless     |
                  | no model loop      |
                  | no shell, no browser
                  +---------+----------+
                            |
          SSE on every replica, fed by the event bus
                            |
     +----------------------+----------------------+
     |                      |                      |
 Postgres + RLS         Valkey                 object store
 + pgvector             sessions               original bytes
 read model             idempotency
                        rate limits
     |
 runtime worker
 owns the model loop
 one Temporal activity = one step
     |
 tool gateway
 the only caller of tools, including built-ins
 policy, approvals, result wrapping, secrets
     |
 sandbox manager
 the only creator of pods
 Kubernetes in production
 empty endpoint => the tool does not run

Packs are out of process.
Signed manifest, own schema.
Core never imports a pack.

Host bash is dev-only and is absent from production images.
```

## Boundary laws

1. The API process does not run the model loop, a shell, or a browser.
2. The runtime worker owns the loop. One Temporal activity is one step.
3. The tool gateway is the only caller of tools, including built-ins. It applies policy, approvals, result wrapping, and secrets.
4. The sandbox manager is the only creator of pods. Production uses Kubernetes. An empty `endpoint_url` means the tool does not run.
5. Postgres with row-level security and pgvector is the read model for API requests.
6. The object store holds original bytes. The database holds the hash and the pointer.
7. Valkey holds sessions, idempotency, and rate limits.
8. An event bus feeds server-sent events on every API replica.
9. Host bash exists only in development. Production images do not contain it.
10. A pack is out of process. Core never imports a pack. An unsigned pack is refused outside development.
11. Core names no industry and no framework, including in tests.
12. Four-eyes and the security audit log stay in core.

## Pack model

A pack is signed camelCase content. The manifest carries:

| Field | Meaning |
|---|---|
| `id`, `version`, `minCore` | Identity, immutable version, minimum core that can load it |
| `permissions[]` | Permissions the pack registers |
| `auditActions[]` | Audit actions the pack registers |
| `schema` | Optional. The pack's own Alembic history, run through `packs/alembic_env.py` |
| `nav[]` | Navigation items. Each route is under `/packs/{id}/...` |
| `tools[]`, `agents[]`, `skills[]` | Declarative content |
| `ruleSets[]` | Versioned rule sets ([ADR-0029](../02-architecture/adr/ADR-0029-generic-judgements.md)) |
| `connectors[]` | Slugs only. Secrets stay in core |
| `recognisers[]` | Locale personal-data packs |

The web app renders a pack through a generic `PackFrame`. `apps/web` has no industry routes. Pack versions and rule-set versions are immutable. A judgement stores both. Outside development, a pack whose signature is not in `AR_PACK_TRUSTED_KEYS` is refused.

## Proof labels

Progress docs and the UI use only these labels ([ADR-0032](../02-architecture/adr/ADR-0032-proof-labels.md)).

| Label | Meaning |
|---|---|
| `unit` | In-process. No network and no model. |
| `contract` | Real HTTP and real Postgres. The model and third parties are stubbed. |
| `live` | The tenant's configured model endpoint. The report names the model id and the date. |

A dry-run gym is not `live`. `llm_judge` is renamed, or it calls a model. Lexical overlap is `not_judged`, never a verdict.

## Rule sets and judgements

A rule set is versioned content: `id`, `version`, `items[]` (`itemId`, `statement`), and `sourceFileId` plus `sha256`.

A judgement records the rule-set version, the item id, the verdict, the passage id, the quote, the model id, and the prompt hash.

A quote that is not a substring of the stored passage is `not_supported`. Lexical overlap is `not_judged`.

## Read model

Postgres is the read model for API requests. The in-memory `ChatService` becomes a test double and leaves the production path in Stage 8.

## Stage map

Sizes are the owner's marks: S, M, L. A stage starts only after the stages in its "after" line are done. Stages 1, 2, 4, and 7 may run in parallel once Stage 0 is done. Stage 1 is also parallel with 2, 4, and 7.

### Stage 0: Decisions (S)

This document and the ADRs. Depends on nothing.

### Stage 1: Safe process (L)

After Stage 0. Parallel with Stages 2, 4, and 7.

- Production refuses host exec. An empty `endpoint_url` returns `sandbox_unavailable`.
- Helm replicas stay 1, and the horizontal pod autoscaler minimum stays 1, until Valkey sessions, Postgres or Valkey idempotency (the existing `idempotency_keys` table), and a run-event bus exist.
- `/readyz` checks Postgres, and Temporal when `AR_TEMPORAL_REQUIRED` is set.
- There is no in-process generate fallback when Temporal is required.
- A turn that the worker lost is marked `interrupted` / `not_resumed`.
- Boot refuses a missing `AR_CURSOR_SECRET` and refuses the default `dev-cursor-secret`.
- The Valkey rate limiter retries and never latches open.

Closes F01 (the refuse half), F03, F07, F10, F12, F26.

### Stage 2: Domain strip (M)

After Stage 0.

- Remove the `features.assurance` flag, the `/admin/assurance` route, its navigation and messages, and the assurance router.
- Remove the `evidence`, `holds`, `ai_governance`, and `binders` permissions, the evidence tools, `BinderBook`, and the questionnaire tool and skill.
- Those capabilities move into an uninstalled signed example pack named `records`, with no framework text.
- Records tables follow expand/contract: core stops writing them, and a later revision drops them.
- Rename `documents.check` to `documents.judge` (`ruleSetId` or `statements[]`).
- Rename `documents.gaps` to `documents.missing`.
- The personal-data profile `analysis` becomes `verbatim`.
- The tool server `control` becomes `session`.
- Citation `source_kind` value `evidence_item` becomes `sealed_record`.
- Hold record classes become generic names.
- Core's default personal-data recognisers are email, phone, card, and IBAN. `Aadhaar`, `PAN`, `IFSC`, `UPI`, and `medical_license` become an opt-in locale recogniser pack.
- Rewrite the named-framework samples in `demo_chat.py`, `e2e` `m3-builder.spec.ts` around line 48, `test_m3_agents.py` around line 289, and `scripts/m24_proof.py`, `scripts/m25_eval.py`, and `scripts/m25_proof.py`.
- Move `docs/testing/grc-flows` to `packs/examples`.
- CI fails a grep for `soc 2`, `nist`, `hipaa`, `gdpr`, `gxp`, `21 cfr`, `pharma`, `clinical`, or `/admin/assurance` in core. Migration `0031` may keep a tombstone comment.

Closes D01-D19.

### Stage 3: Identity and `/v1` (L)

After Stage 1.

- OIDC for production, plus JWT bearer tokens checked with JWKS.
- `Secure` cookies.
- Lockout state in Valkey.
- Resumable external server-sent events: `Last-Event-ID`, heartbeat, and tail.
- Cursor pagination.
- `application/problem+json` for login failures.
- `Retry-After` on HTTP 429.

Closes F05, F06, F17, F18.

### Stage 4: Trust (M)

After Stage 0.

- Slack and Teams approvals resolve the user and call `ApprovalBook.decide`.
- One audit writer: `audit.service.record`, in the same transaction as the change.
- The audit API reads only the chain.
- User turns and channel turns enter the prompt as untrusted content.
- The read-only OPA fallback list is explicit.
- Outbound masking is strict.

Closes F02, F04, F13, F19, F27.

### Stage 5: Files and judgements (L)

After Stage 2.

- Ingest keeps original bytes and their `sha256` in the object store.
- Tables for rule sets and judgements.
- Each judgement stores the prompt hash and the model id.
- A schema failure is a failed judgement.
- Each chunk records its embedding model id. A mismatch is HTTP 409.
- An image is read with tesseract in the image, or the result is `text_not_extracted`.
- A PDF is Unicode, or the tool returns an explicit error.
- One retrieval path.
- Agent YAML omits keys that are undefined.

Closes F08, F09, F14, F20, F21, F24, F25, F28.

### Stage 6: Gateway and pods (L)

After Stage 1.

- The worker calls the gateway over HTTP for every tool.
- The Kubernetes driver creates pods.
- Screenshots come from real Chromium.
- Network policy is enforced.

Closes F16 and the rest of F01.

### Stage 7: Honesty (M)

After Stage 0.

- Every connector shows a verification badge.
- Tools that are not live are hidden from the model.
- `llm_judge` is renamed to the lexical-overlap check, or it calls a model.
- Dry-run and live eval artifacts are distinct.
- Signup is implemented, or it is removed.
- `progress.md` and `README` are rewritten. The README still says Keycloak.

Closes F11, F22, F29, F30.

### Stage 8: One read model (L)

Status: done. Last, after Stages 1 through 7.

- Repositories per request.
- `ChatService` leaves the production path.
- Run events are written in the same transaction as the change.
- The single Alembic head is documented.
- Live exit: the Stage 3 and Stage 5 scenarios pass on a two-replica Helm install.

Closes F15, F23.

### Stage 9: Hardening and live certification (L)

Status: done. After Stage 8.

- Builder sessions, rate-limit buckets and the external API minute window live in Valkey. Standing approvals and review queues live in Postgres. Staging and production refuse an in-memory implementation (`ProcessLocalStateRefusedError`).
- Two instances on shared Valkey and Postgres see the same session, window, standing approval and review queue.
- The runtime worker registers the sandbox manager launcher. Tool steps that need a sandbox go through the manager. The sandbox image bakes Chromium, LibreOffice and the pinned data libraries. The in-process browser is dev and CI only.
- `scripts/check_api_catalogue.py` fails CI when the catalogue and `openapi.json` disagree on method and path.
- A kind job installs the chart with 2 API replicas and 2 workers and runs the contract scenarios (fake-llm). Bundled Postgres creates `ar_owner` during database init, before the migrate Job, for both CloudNativePG and the dev StatefulSet. `scripts/certify_live.sh` is the live run against `AR_LLM_BASE_URL` / `AR_LLM_API_KEY` (default Qwen3-32B on DeepInfra). Without a key the scorecard is `contract` and the live run stays pending.

Proof label: `unit` for boot refusal; `contract` for two instances and the kind job; `live` only from `scripts/certify_live.sh` when a real model key is set.

### Stage 10: Agent quality and deep research (L)

After Stage 9.

- Optional per-agent plan step, shown on the run stream, with a replan after a failed tool.
- Bounded repair retries for tool errors, schema-invalid arguments and malformed model output. A structured tool-failure notice (OQ-113).
- Per-tenant ordered model endpoints. Timeout, 429, 5xx and bad JSON fall through. Circuit state is in Valkey outside dev and CI. The trace and the audit record the endpoint id and model id, never a key.
- Token budgeting, rolling summary, and truncated tool output that `context.retrieve` can read back.
- `scripts/eval_run.py` scores the 60-case assistant set and the 150-case red-team set. CI fails if the contract rates regress. A live label is written only when `AR_LLM_API_KEY` is set.
- Research mode: search, fetch, read, synthesise, verify. Temporal child workflows for the parallel reads. Bounds on depth, breadth, time and cost. Cancel and resume. Citations must appear in the stored page. Sources keep sha256 and a timestamp.
- Search providers are SearXNG, Brave, Tavily and Bing, plus a fixture provider for contract runs. Keys are named secrets. Page text uses readability, and the sandbox Chromium fetcher when one is configured.
- Chat has a research toggle, a live step stream and a sources panel. `/v1`, MCP and A2A expose the same mode.

Proof label: `unit` for the loop, the citation check and the workflow definition; `contract` for `scripts/eval_run.py` without a key. `live` only from `scripts/certify_live.sh` on a machine that has `AR_LLM_API_KEY`.

## Exit

Production is Stage 9's exit passed, and core still passes the Stage 2 grep. The runbook is [live-certification.md](live-certification.md).
