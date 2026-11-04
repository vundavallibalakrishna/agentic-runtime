# M25 knowledge, memory and skills

## Untrusted documents

Passages placed in a prompt are wrapped with `ar_common.wrapping.wrap_untrusted` and marked `source="knowledge"`. The model is told to treat them as data. A citation card is built only from chunks the retriever returned. A question with no attached knowledge base is told that the documents are absent and not to invent a citation, a page or a private code.

Fetched URLs go through the same public-host check as other outbound HTTP. Private and link-local addresses are rejected. A connection secret is used as a request header and is stripped from the indexed text if it appears there. The secret is not a field of the knowledge API.

## Memory

Entries the product stores are rows on the memory screen. Explicit phrases ("remember that", "I prefer") create a visible row. A person can edit or delete that row. Compaction stores a summary of older turns on the conversation. The summary is not a hidden fact: the memory screen remains the list of facts, and the chat shows when earlier turns were folded.

## Skills

Imported markdown and zip entries are author content, size-capped (2 MB archive, 200 KB file). Paths cannot escape the skill folder. A skill has no execution step of its own. Helper file text is stored on the skill version. The sandbox tools already available to the agent are the only way that text is executed, and only if the person runs one of those tools.

## What was tested

Unit tests cover a refused fake embedding when a real model is requested and no provider exists, a real provider selecting `BAAI/bge-m3`, library indexing with anchors, an unchanged re-index, a changed re-index, a private URL rejection, a cross-tenant 404, skill import and a description match, compaction that keeps four messages, and a prompt that stays inside 12,000 characters. The HTTP test repeats the cross-tenant 404 for a collection and a skill export. The checklist records the Qwen3-32B run.
