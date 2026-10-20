# PRD 07 — Memory

Agents remember useful facts about users, agents and teams across conversations, under user control and with poisoning defences; long conversations stay within the model context via compaction. Spec: [spec 11](../03-specs/11-memory.md), [spec 07 §5](../03-specs/07-agent-runtime.md#5-context-management), [prompt-injection §5](../06-security/prompt-injection.md#5-memory-poisoning). Plan: [M8](../09-plan/M08-memory-context.md).

### US-MEM-01 · The agent remembers my preferences (P0)
As a **member**, I want agents to remember things I tell them ("I work in the Pune office", "reply in short bullet points") so that I don't repeat myself.
- When memory is enabled (tenant, user and agent all on), facts are recalled into the `<memory trust="user_data">` context block; the UI shows `memory.recalled` / `memory.saved` indicators with the fact text.
- Explicit "remember that…" saves immediately (`memory.save`); automatic extraction after the turn (`MemoryExtractionWorkflow`) reads only my text and the final answer.
- Spec: spec 11 §1–4. Plan: M8-T01, M8-T02, M8-T03.

### US-MEM-02 · I control my memory (P0)
As a **member**, I want to see, edit, delete and turn off what agents remember about me.
- `/memory` page lists my `user` and `agent_user` facts with source and date; edit (`PATCH /api/v1/memory/{fact_id}`), delete, "Forget everything" (`DELETE /api/v1/memory`), and a toggle to disable memory for my account.
- Deleted facts are never recalled again (hard delete of the vector and row).
- Spec: spec 11 §2 rule 6, §5. Plan: M8-T01, M8-T05.

### US-MEM-03 · Agent and team knowledge from conversations (P1)
As a **builder** or **team lead**, I want agents to learn shared facts (e.g. "the finance close is on the 5th working day") with review.
- Model writes to `agent` or `team` scope land as `pending_review`; reviewers (`memory:manage_agent` holders for the agent, team leads) approve or reject; only active facts are recalled.
- Spec: spec 11 §2 rule 4, §5. Plan: M8-T01, M8-T05.

### US-MEM-04 · Memory cannot be poisoned by tools or documents (P0)
As a **security officer**, I want memory to be resistant to injected instructions.
- Extraction never reads raw tool outputs or retrieved documents; facts saved during a run with untrusted content since the last user message get `trust_level='low'`, are labelled when recalled and are never stored as `instruction`.
- Red-team cases for cross-user leakage and poisoning pass ([eval-strategy §2](../08-quality/eval-strategy.md#2-repository-suites-evals)).
- Spec: spec 11 §2 rules 2–3. Plan: M8-T03, M14-T01.

### US-MEM-05 · No sensitive data in memory by default (P0)
As a **data protection officer**, I want memory to avoid secrets and sensitive personal data.
- Secrets/credentials are never stored; DPDP-sensitive categories (health, religion, caste, sexual orientation, biometric, financial account numbers) are stored only on explicit user request.
- Memory is included in data export and erased by `ErasureWorkflow`.
- Spec: spec 11 §2 rule 5, [data-protection](../06-security/data-protection.md). Plan: M8-T03, M14-T02.

### US-MEM-06 · Long conversations keep working (P0)
As a **member**, I want very long conversations to continue without errors or the agent forgetting the task.
- When the context exceeds `compaction_threshold` of the model window, older turns are summarised (`context.compacted` event) and tool results are truncated to `tool_result_max_tokens`; the plan and pinned facts are preserved.
- Spec: spec 07 §5. Plan: M8-T04.
