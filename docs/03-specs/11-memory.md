# Spec 11: Memory (`ar_domain.memory`)

Endpoints served by `api`; recall runs in `runtime-worker` (activity `recall_memory`) and in `mcp-gateway` (`memory.*` built-in tools); extraction runs on `system-worker` (`MemoryExtractionWorkflow`). Owns `memory_facts` ([schema §9](../04-data/schema.md#9-memory-ar_domainmemory)), stored in Postgres with pgvector (`vector(1024)`, HNSW cosine). PRD: [07-memory](../01-prd/07-memory.md).

## 1. Memory types

| Type | Where | Lifetime |
|---|---|---|
| Working memory | the prompt (run context) | one run |
| Conversation memory | `messages` + `conversations.rolling_summary` | conversation retention |
| Long-term facts | `memory_facts` with scope `user` (about the user, any agent), `agent_user` (this agent with this user), `agent` (shared lessons/glossary for all users of an agent), `team` (team glossary) | until deleted, superseded or inactive for `retention.memory_inactive_days` |
| Episodic search | `conversations.search_history` tool over the user's own past conversations | conversation retention |

## 2. Rules

1. Memory is **off** if any of: tenant `settings.memory.enabled=false`, user `settings.memory_enabled=false`, agent `memory.enabled=false`.
2. Automatic extraction only reads **user-authored** text and the final assistant answer of the turn; never raw tool outputs or retrieved documents (memory-poisoning defence, [prompt-injection §5](../06-security/prompt-injection.md)).
3. Facts saved via `memory.save` during a run whose context contains untrusted tool output since the last user message get `trust_level='low'` and `source_kind='tool_output'`; low-trust facts are labelled as such when recalled and are never `instruction` category.
4. `agent` and `team` scope writes from the model always land as `pending_review`; only reviewers (agent editors with `memory:manage_agent`, team leads) activate them.
5. Never store secrets/credentials (regex detectors from `ar_common.redaction`) or DPDP-sensitive categories (health, religion, caste, sexual orientation, biometric, financial account numbers) unless the user explicitly asked to remember (explicit API or explicit "remember that…" detected by the extractor with `explicit: true`).
6. Users can view, edit, delete all their facts (`user`, `agent_user`) and export them (`GET /api/v1/me/export`).

## 3. Recall (`memory.service.recall(ctx, query, scopes, top_k)`)

1. Embed the query (`embed` alias, `dimensions=1024`, purpose `memory_recall`).
2. SQL (RLS on): candidates = active facts where (`scope='user' AND user_id=:u`) OR (`scope='agent_user' AND agent_id=:a AND user_id=:u`) OR (`scope='agent' AND agent_id=:a`) OR (`scope='team' AND team_id IN :user_teams`), filtered to `read_scopes`; order by `embedding <=> :q` limit 30.
3. Score `= 0.75 * cosine_sim + 0.15 * exp(-age_days/90) + 0.10 * min(1, recall_count/10)`; drop `cosine_sim < 0.25`; take `top_k` (`definition.memory.recall_top_k`, default 8) within 1,500 tokens.
4. Update `last_recalled_at`, `recall_count` (async). Emit `memory.recalled`.
Latency budget: p95 ≤ 80 ms excluding embedding.

## 4. Extraction (`MemoryExtractionWorkflow`)

- Started by the outbox subscriber on `run.completed` when the run is top-level, trigger ∈ {chat, channel, api}, and memory extraction is enabled (tenant `settings.memory.extraction` and agent `memory.user_writes='auto'`). Workflow id `memx-{run_id}`, queue `ar-system`.
- Activity `extract_memory_candidates` (fast alias, purpose `memory_extraction`, prompt `ar_system/prompts/memory_extraction.md`): input = the turn's user message(s) + final assistant text + top 10 similar existing facts (ids + content). Output (JSON schema enforced) `[{op: "add"|"update"|"delete"|"noop", content, category, scope: "user"|"agent_user", target_fact_id?, confidence: 0..1, explicit: bool}]` (≤ 5 ops).
- Activity `apply_memory_ops`: drop ops with `confidence < 0.7` (unless `explicit`), apply rule 5, de-duplicate (`cosine ≥ 0.92` to an existing fact → convert `add` to `update`), `update` = insert new fact + mark old `superseded` with `superseded_by_id`; `delete` only for facts of the same user. Emit `memory.saved` events into the (completed) run's stream for the UI toast "Memory updated" and audit `memory.extracted` (fact ids only).
- Retries 3×; failure is logged, never surfaces to the user.

## 5. Public API

#### GET /api/v1/memory
Any user. The caller's facts. Query `scope` (`user|agent_user`), `agent_id`, `category`, `q` (semantic when ≥ 3 words, else ILIKE), `status` (`active` default | `superseded`). Item `MemoryFact {id, scope, agent: {id, name}|null, content, category, source_kind, trust_level, confidence, status, created_at, last_recalled_at, recall_count, source: {conversation_id, message_id}|null}`.

#### POST /api/v1/memory
Body `{content (≤ 500), scope: "user"|"agent_user", agent_id? (required for agent_user), category?}`. `source_kind='explicit'`.

#### PATCH /api/v1/memory/{fact_id}
Owner. `{content?, category?}` (re-embeds).

#### DELETE /api/v1/memory/{fact_id}
Owner. Hard delete. Audit `memory.deleted`.

#### DELETE /api/v1/memory
Owner. Query `agent_id?` → delete all of the caller's facts (optionally for one agent). Requires header `X-Confirm: delete-all-memory`.

#### GET /api/v1/agents/{agent_id}/memory
Agent editors or `memory:manage_agent`. Agent-scope facts; `status=pending_review` for the review queue.

#### POST /api/v1/agents/{agent_id}/memory
Editors. Add an agent-scope fact (`source_kind='admin'`, active).

#### POST /api/v1/agents/{agent_id}/memory/{fact_id}:approve
#### POST /api/v1/agents/{agent_id}/memory/{fact_id}:reject
Reject = delete. Audit.

#### PATCH /api/v1/agents/{agent_id}/memory/{fact_id}
#### DELETE /api/v1/agents/{agent_id}/memory/{fact_id}

#### GET /api/v1/teams/{team_id}/memory
Team members (read), team leads (write).
#### POST /api/v1/teams/{team_id}/memory
#### DELETE /api/v1/teams/{team_id}/memory/{fact_id}

## 6. Configuration and limits

| Item | Default |
|---|---|
| Facts per user | 2,000 (oldest least-recalled superseded first when exceeded) |
| Facts per agent / team | 5,000 |
| `AR_PGVECTOR_DIMENSIONS` | `1024` (fixed; changing requires a migration and re-embed job `scripts/reembed_memory.py`) |
| `AR_MEMORY_RECALL_MIN_SIM` | `0.25` |
| `AR_MEMORY_DEDUPE_SIM` | `0.92` |

The embedding model change procedure: new `embed` alias target → `scripts/reembed_memory.py --tenant <id>` re-embeds facts and tool versions in batches; `embedding_model_id` records which model produced each vector and recall ignores mismatching rows until re-embedded.

## 7. Metrics

`ar_memory_recall_seconds`, `ar_memory_recalled_facts`, `ar_memory_extraction_ops_total{op,result}`, `ar_memory_facts{scope}` (rollup gauge), `ar_memory_pending_review`.

## 8. Test plan

- Unit: scoring function, rule 5 filters (table of sensitive examples), dedupe/supersede logic.
- Integration: recall respects scope and RLS (user A cannot recall user B's facts even with same agent); extraction against `fake-llm` scripted outputs (add/update/delete/noop); low-trust labelling after a tool call; disabled at each of tenant/user/agent level → no recall, no extraction; delete-all.
- Eval (M13): memory suite: preference remembered across conversations; injection attempt via tool output does not create a fact.
