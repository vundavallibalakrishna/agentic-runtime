# M25 — Knowledge, memory and skills

Depends on M24. A tenant builds a knowledge base from the document library, a file, a URL or a connection. An agent can use one or more of those bases. Retrieval is hybrid and keeps the page and section anchor. Memory and skills are visible, editable and durable.

The GRC pack stays parked. This milestone does not import it.

## Embeddings

The default embedding model is `BAAI/bge-m3` (1024 dimensions). The same id is self-hostable on any OpenAI-compatible embeddings server (Hugging Face text-embeddings-inference or vLLM) and is hosted by providers such as DeepInfra. Point the tenant provider at that base URL. A registered model with `kind=embedding` overrides the default. The rerank default is `BAAI/bge-reranker-v2-m3`, called at `{base}/rerank` or, for a DeepInfra base ending in `/openai`, at the sibling `/inference/{model}` endpoint. If the provider has no rerank route, the candidate window is reordered by token overlap and the trace says so.

`embed` and `fake-embed` are not called once a non-fake provider is saved. A process that only has the seeded fake-llm provider still uses the deterministic test vector so local demo and unit tests run offline. Unit tests may inject `store.embed_client`. pgvector remains the default store. Qdrant stays behind `AR_VECTOR_BACKEND=qdrant` and the conformance suite.

Revision `0027` adds nullable `knowledge_collections.embedding_model`.

## M25-T01 Knowledge bases

**Spec:** [10-knowledge](../03-specs/10-knowledge.md), [24-documents](../03-specs/24-documents.md), [m25-knowledge](../06-security/m25-knowledge.md).

**Do:**

- Create a collection and add a library document, an upload, a URL or a connection.
- Chunk the text. Keep the page and the section anchor.
- Hybrid search (vector plus keyword) then rerank. Stop at 12,000 characters.
- Re-index one document when its text changes. Unchanged text is not embedded again.
- Record a retrieval trace on the answer.

**Done when:** a question returns the passage that contains the answer, another tenant receives 404, and a restart still searches the same chunks.

**Tests:** `libs/ar_domain/tests/unit/test_m25_workspace.py`, `services/api/tests/unit/test_m25_api.py`.

## M25-T02 Memory

**Spec:** [11-memory](../03-specs/11-memory.md).

**Do:**

- Keep conversation history in Postgres.
- Compact with the agent's `context.keep_messages` and `context.compaction_threshold`. The summary replaces older turns in the prompt.
- Memory entries stay visible. A person can edit or delete them. Nothing is stored that the memory screen cannot show.

**Done when:** a preference created in the memory screen is used in a later conversation, and editing it changes the next conversation.

**Tests:** `test_m25_workspace.py`.

## M25-T03 Skills

**Spec:** [14-skills](../03-specs/14-skills.md).

**Do:**

- A skill has a name, a description, instructions, optional helper files and optional examples.
- Import markdown with front matter, or a zip that contains `SKILL.md`. Export the same shape.
- An attached skill loads when its description matches the task. The run records the skill and the reason.
- A skill does not execute code. Helper files are text the sandbox tools can read.

**Done when:** a matching task loads the skill and a non-matching task does not.

**Tests:** `test_m25_workspace.py`.

## M25-T04 Screens and proof

**Spec:** [ux-quality](../08-quality/ux-quality.md).

**Do:**

- Knowledge screen: create, add documents, status, chunk counts, re-index, retrieval test.
- Memory screen: entries, edit, delete, scope.
- Skills screen: list, editor, import, export. The agent editor attaches knowledge bases and skills.
- Chat shows a citation card, the retrieval trace and a loaded-skill line.

**Done when:** Playwright captures light and dark at desktop and mobile, and the checklist records the Qwen3-32B run.

**Tests:** `apps/web/e2e/m25-workspace.spec.ts`.

## Out of scope

Connector libraries (M26, M27), orchestration (M28) and exposing agents (M29). The GRC pack stays parked.
