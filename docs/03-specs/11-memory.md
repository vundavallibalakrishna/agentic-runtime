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

## 4. Extraction

After a top-level turn completes, the process that ran it asks a chat model what to remember from it and applies the answer (`ar_domain/memory/extraction.py`). Nothing decides what to remember by matching words in the turn ([OQ-105](../open-questions.md)).

- **When.** The run is top-level, its trigger is one of {chat, channel, api}, the tenant's `settings.memory.extraction` and the person's own switch are on, and the agent's `memory.user_writes` is `auto`. It runs after `run.completed` has been emitted, so it adds nothing to the time the answer takes, and whatever goes wrong in it never changes the turn.
- **Which model.** The agent's `model.fast_alias` (default `fast`) when the tenant has pointed it at a chat model, else the alias the agent answers with. With neither, nothing is remembered and the log has `memory_extraction_skipped reason=no_model`.
- **What the model is given.** The instructions in `ar_domain/prompts/text/memory_extraction.md`, then what the tenant's administrator added on the Memory screen (`settings.memory.extraction_instructions`, up to 2,000 characters). Then the person's words, the assistant's answer wrapped as untrusted content, and the person's ten kept memories closest to the exchange, each with its id. Text the person typed cannot open or close a block of that prompt. Tool results and retrieved passages are never included.
- **What it returns.** A JSON list of at most five `{op: "add"|"update"|"delete", content, category, scope: "user"|"agent_user", target_fact_id?, confidence: 0..1, explicit: bool}`. Anything else changes nothing. A provider that does not answer changes nothing (`reason=no_answer`).
- **How it is applied.** Operations under `confidence 0.7` are dropped unless `explicit`; rule 5 applies; an `add` close to an existing fact (`similarity ≥ 0.92`) becomes an `update`; `update` inserts a new fact and marks the old one `superseded` with `superseded_by_id`; `delete` only reaches the person's own facts. Text that appears in tool output and not in the exchange is dropped. Audit `memory.extracted`.
- **Events.** `memory.saved` is added to the completed run's stream. That stream has closed by then, so a client reads it again with `Last-Event-ID` ([stream events §3](../05-contracts/stream-events.md)); the chat screen does, and shows "Memory updated" with **Undo**.
- **Cost.** The call is counted and priced with the run, under the usage keys `mg:{run_id}:memory:in` and `mg:{run_id}:memory:out`.
- **Checking the prompt.** `scripts/memory_extraction_eval.py` sends the prompt for nineteen exchanges to a real model and prints what it kept. Run it after changing the prompt or before pointing `fast` at a smaller model.

**One memory across processes.** Before a turn, and before each memory endpoint, a process makes its copy of the tenant's facts equal the database rows: a fact a worker saved appears on the Memory screen, and a fact the person deleted leaves every process, so no worker goes on recalling it. Rows a process changed and has not saved yet are kept.

## 5. Public API

#### GET /api/v1/memory
Any user. The caller's facts. Query `scope` (`user|agent_user`), `agent_id`, `category`, `q` (semantic when ≥ 3 words, else ILIKE), `status` (`active` default | `superseded`). Item `MemoryFact {id, scope, agent: {id, name}|null, content, category, source_kind, trust_level, confidence, status, created_at, last_recalled_at, recall_count, source: {conversation_id, message_id}|null}`. The list also returns `memory_enabled` and `teams` (`{id, name, items}` for each team the caller belongs to) so the settings page can show the toggle and shared glossary without a second catalogue call ([OQ-39](../open-questions.md)).

#### PATCH /api/v1/memory/settings
Any user. Body `{enabled}`. Sets the caller's `memory_enabled` toggle. `PATCH /api/v1/me` stays on the identity database, which the dev API does not use for this switch ([OQ-39](../open-questions.md)).

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
| `AR_PGVECTOR_DIMENSIONS` | `1024` (fixed; changing requires a migration and a run of `scripts/reembed_memory.py`) |
| `AR_MEMORY_RECALL_MIN_SIM` | `0.25` |
| `AR_MEMORY_DEDUPE_SIM` | `0.92` |

A fact is embedded by the model the tenant's `embed` alias points at ([spec 04](04-model-gateway.md)), and `embedding_model_id` records which model produced each vector. With no embedding model a fact is not saved: the request answers `409 invalid_state` with a message that names the Models screen, the `memory.save` tool returns that message, and extraction after a turn records the op as `no_embedding` without failing the turn ([OQ-98](../open-questions.md)). The model must return vectors of `AR_PGVECTOR_DIMENSIONS` numbers; another length is refused with the fix (set the model's embedding dimensions, or choose another model).

Similarity is the larger of the cosine of the two vectors and the share of the query's words the fact contains. Two vectors are compared only when one model wrote both, so a fact embedded by an earlier model, and every fact while no model is set, is matched by words alone.

When the `embed` alias is pointed at another model, the product embeds again every fact the new model did not write, beside the request that made the change, and saves them as it goes; until that finishes those facts are matched by words. A model that fails leaves the alias changed and the facts matched by words; the next alias change or `uv run python scripts/reembed_memory.py --tenant <slug>` tries again ([OQ-102](../open-questions.md)).

## 7. Metrics

`ar_memory_recall_seconds`, `ar_memory_recalled_facts`, `ar_memory_extraction_ops_total{op,result}`, `ar_memory_facts{scope}` (rollup gauge), `ar_memory_pending_review`.

## 8. Test plan

- Unit: scoring function, rule 5 filters (table of sensitive examples), dedupe/supersede logic.
- Integration: recall respects scope and RLS (user A cannot recall user B's facts even with same agent); extraction against `fake-llm` scripted outputs (add/update/delete/noop); low-trust labelling after a tool call; disabled at each of tenant/user/agent level → no recall, no extraction; delete-all.
- Eval (M13): memory suite: preference remembered across conversations; injection attempt via tool output does not create a fact.
