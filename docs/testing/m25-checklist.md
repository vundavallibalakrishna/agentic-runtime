# M25 checklist

Proof date: 2026-11-04. Chat model: Qwen/Qwen3-32B through DeepInfra (`https://api.deepinfra.com/v1/openai`). Embeddings: `BAAI/bge-m3` on the same base URL. The provider key was read from `AR_CERT_LLM_API_KEY` at runtime and is not in this file.

Isolated Postgres was `127.0.0.1:55449`. The API listened on `18125`. Temporal was pointed at a closed port so the turn stayed in this process. The operator Postgres on 5432 and the processes on 8000, 8001 and 8013 were not used.

Public files: GNU GPL 3.0, RFC 9110, and NIST SP 800-53 Rev. 5 (492 pages). A short note written for this run held the code `ND-1844-QUILL`.

- [x] The knowledge base stored `embeddingModel` `BAAI/bge-m3`, not `fake-embed`
- [x] Indexing wrote 3304 chunks and 3304 embedding rows. The NIST file is 492 pages
- [x] The agent answered "The warehouse code for the north dock is ND-1844-QUILL [1]." The retrieval trace used 1282 characters and the top chunk is page 1, anchor `p1-s0`
- [x] The same question to an agent with the knowledge base detached did not contain `ND-1844-QUILL`. It said the document was not available
- [x] "Write the weekly status note for the docks" loaded `weekly-status` because the description matched `note, status, weekly`. The answer began with `STATUS-OK` and then three sentences
- [x] A second conversation answered "You can call me Captain Bala." After the memory row was edited, the next conversation answered "I should call you Captain Rivera"
- [x] The account-management question on the 492-page PDF cited page 47. Retrieval used 7311 characters, under the 12000 character budget
- [x] After the API process was replaced, search still returned `ND-1844-QUILL`, the skill was still listed, and the memory row still said Captain Rivera
- [x] Retrieval eval, 4 questions, real embeddings: 3 recalled in the top 5, 3 of those with a page or anchor. Recall 0.75. The missed question was the GPL phrase "freedom, not price", which was not in the top 5. Dock code page 1 anchor `p1-s0`. RFC 9110 page 1 anchor `p1-s0`. NIST AC-2 page 63 anchor `p63-s136-1`
- [x] Playwright screenshots: knowledge, collection, memory, skills, skill editor, agent knowledge tab, and chat, light and dark, desktop and mobile. Walkthrough: `walkthrough.webm`

Unit tests reject a fake embedding alias when no real provider is configured, keep a real provider off `fake-embed`, and show a cross-tenant 404.
