# M8 — Memory & context management

Goal: agents remember what matters and handle long conversations. Users see and control their memory; agent-scope memory goes through review; long conversations are compacted without losing decisions and facts.

Exit criteria: telling an agent "I prefer answers in bullet points" is remembered in a new conversation; the user deletes it in settings and it is no longer applied; a 200-turn scripted conversation never exceeds the context window and keeps referenced file ids.

---

### M8-T01 · Revision 0015 `memory` and memory API
- **Depends on:** M2-T06
- **Areas:** `ar_domain/memory/**`, migration 0015, `ar_api/routers/memory.py`
- **Spec:** [spec 11 §1–2, §5](../03-specs/11-memory.md#5-public-api), [schema §9](../04-data/schema.md#9-memory-ar_domainmemory)
- **Do:** `memory_facts` with pgvector HNSW index (1024); service rules of spec 11 §2 (scopes, limits, PII guard, provenance); endpoints `GET/POST /api/v1/memory`, `PATCH/DELETE /api/v1/memory/{fact_id}`, `DELETE /api/v1/memory` (forget all); agent memory `GET/POST /api/v1/agents/{agent_id}/memory`, `POST /api/v1/agents/{agent_id}/memory/{fact_id}:approve`, `:reject`, `PATCH/DELETE /api/v1/agents/{agent_id}/memory/{fact_id}`; team memory `GET/POST /api/v1/teams/{team_id}/memory`, `DELETE /api/v1/teams/{team_id}/memory/{fact_id}`.
- **Done when:** users only ever see their own `user`/`agent_user` facts; agent-scope writes by non-editors land as `pending_review` with `memory.fact_proposed`.
- **Tests:** integration per endpoint; scope visibility matrix tests.

### M8-T02 · Memory tools and recall
- **Depends on:** M8-T01, M4-T04
- **Areas:** `ar_mcp_gateway/builtins/memory.py`, `ar_runtime/activities/recall_memory.py`, `ar_domain/memory/recall.py`
- **Spec:** [spec 11 §3](../03-specs/11-memory.md#3-recall-memoryservicerecallctx-query-scopes-top_k), [spec 08 §9](../03-specs/08-tool-registry-mcp.md#9-built-in-tool-schemas-platform-servers-executed-in-process-by-mcp-gateway-unless-noted)
- **Do:** `memory.search`, `memory.save`, `memory.forget`; `recall_memory` activity at run start (embedding purpose `memory_recall`, `AR_MEMORY_RECALL_MIN_SIM`, top-k per scope, injected into the memory section of context assembly as untrusted-but-user-owned data with provenance).
- **Done when:** recall respects agent `memory` settings (off, read-only, auto) and user memory toggle.
- **Tests:** integration with pgvector; Temporal run with recalled facts in the prompt snapshot.

### M8-T03 · `MemoryExtractionWorkflow`
- **Depends on:** M8-T02, M1-T06
- **Areas:** `ar_system/workflows/memory_extraction.py`, `ar_system/prompts/memory_extraction.md`, `ar_system/subscribers/memory_extraction.py`
- **Spec:** [spec 11 §4](../03-specs/11-memory.md#4-extraction-memoryextractionworkflow), [prompt-injection §5](../06-security/prompt-injection.md#5-memory-poisoning)
- **Do:** Outbox subscriber on `run.completed` with the start conditions; activities `extract_memory_candidates` (JSON schema output) and `apply_memory_ops` (confidence threshold, dedupe `AR_MEMORY_DEDUPE_SIM`, supersede chain); never extract from tool output or retrieved content (only user turns + final assistant text); instructions-category facts from extraction require user confirmation (`pending_review` for `instruction`).
- **Done when:** a scripted conversation produces the expected ops; injected text inside a tool result never becomes a memory.
- **Tests:** Temporal tests with fake-llm scripts; poisoning test from prompt-injection §5.

### M8-T04 · Context compaction
- **Depends on:** M3-T03
- **Areas:** `ar_runtime/activities/{needs_compaction.py,compact_context.py}`, `ar_runtime/prompts/compaction.md`
- **Spec:** [spec 07 §5](../03-specs/07-agent-runtime.md#5-context-management)
- **Do:** `needs_compaction` (token estimate via `/v1/tokenize` with fallback), `compact_context` (rolling summary with purpose `compaction`, `summary_through_message_id`, in-run tool-result folding), `context_length_exceeded` failure path, `context.compacted` event.
- **Done when:** the 200-turn exit scenario passes; summaries keep file ids and citations (asserted on fake-llm input).
- **Tests:** Temporal long-conversation test; prompt snapshot.

### M8-T05 · Web: memory settings and review
- **Depends on:** M8-T03
- **Areas:** `apps/web/src/app/(app)/memory/**`, `apps/web/src/components/agent-builder/MemoryReview/**`, `apps/web/src/components/chat/MemoryIndicator/**`
- **Spec:** [spec 19](../03-specs/19-web-app.md)
- **Do:** User memory page (list by scope, edit, delete, forget all, toggle), agent memory review queue in the builder, "memory updated" indicator in chat with undo.
- **Done when:** M8 exit scenario works through the UI.
- **Tests:** Vitest; Playwright remember → delete → not applied; axe.
