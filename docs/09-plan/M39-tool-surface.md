# M39 — Tool surface

Goal: a model can choose and use every tool from its description alone, and has the file primitives a
general agent needs. Source: [the tool review](../testing/tools-review-2026-11-05/tools-review.md),
sections B and C and finding A15.

Depends on: M38. Tasks are split into full task entries when the milestone starts.

## M39-T01 Described tools, with a lint

Split from the review's one item because the connector catalogue is 92 tools and 267 undescribed
parameters, far more than the 66 core built-ins: **T01** describes the core built-ins and ships the lint and
the prompt; **T01a** describes the connectors and removes the deferred exclusion
([OQ-116](../open-questions.md)).

**Do:**

- Every core built-in tool (files, records, conversations, control, sandbox, browser, general, data,
  documents, image, knowledge, memory, skills) has a description on each parameter, an enum where the values
  are closed, an item schema for every array, and a top-level description that says what the tool does, when
  to use it and what it returns. Parameters are described at the source in `tools/seed_tools.py`.
- `scripts/check_tool_descriptions.py` seeds the built-in catalogue (no demo tenant, no fixtures) and fails
  when a parameter has no description or an array has no item schema, naming `server.tool.parameter`. It runs
  in the `docs` CI job. The connector server is the one deferred server, pinned in the script so nothing else
  can be added to it silently.
- `prompts/text/tool_use.md` is rewritten to tell the model to choose and fill a tool from its description
  and its parameter descriptions, prefer the most specific tool, pass allowed enum values and every required
  parameter, and never invent a tool or value a description does not offer.

**Done when:** the lint passes on the core catalogue and fails on a missing description; every core built-in
parameter is described; the prompt leans on the descriptions.

**Tests:** `test_m39_tool_descriptions.py` — every built-in parameter is described, the lint catches a missing
description and a missing item schema and checks nested object and array schemas, the connector server is the
only deferred one, and the lint script exits 0 on the real catalogue.

## M39-T01a Described connectors

**Do:** every connector tool's parameters get a description, an enum where closed, and an item schema for
arrays, at their source in the connector catalogue. The `connectors` server leaves `DEFERRED_SERVERS` in
`scripts/check_tool_descriptions.py`, so the lint then covers the whole catalogue.

**Done when:** `DEFERRED_SERVERS` is empty and the lint passes over every built-in and connector tool.

**Tests:** `test_m39_tool_descriptions.py` asserts `DEFERRED_SERVERS` is empty and the lint covers the
connectors.

## M39-T02 One workspace

Owner chose the `general.*` surface over `sandbox.*` (2026-11-08). The sandbox (Computer) file and command
tools are retired from the model's view; a stored agent that still binds them resolves to the general
equivalents. The execution of `general.code`/`shell` moves into the container in M40-T01; this task is the
tool-surface and alias change, not that reroute ([OQ-117](../open-questions.md)).

**Do:**

- A binding of the `sandbox` server (or a specific `sandbox.*` tool) resolves to the general computer tools:
  `exec`→`shell`, `read_file`/`write_file`/`list_files` by the same name, `export_file`→`write_file`; a
  whole-server bind maps to `general` `shell`/`read_file`/`write_file`/`list_files`. The model is never
  offered a `sandbox.*` tool. A stored sandbox binding entitles only those general computer tools, not the
  general network tools (`tools/pipeline.py` `_bound`, `_entitled`).
- The seeded revenue-analyst binds `general`, and the demo chart flow calls `general.shell`; the showcase
  Writer and its skill's `required_tools` move to `general`.
- A tool result's image files render inline in chat for any tool (not only a `chart` presentation), so a
  `code`/`shell` run that draws an image shows it, keeping the command output (`tool-call-card.tsx`).

**Done when:** no agent is offered a `sandbox.*` tool, a stored sandbox binding still runs on the general
computer tools, and the demo analyst charts through `general.shell`.

**Tests:** `test_m39_one_workspace.py` — a whole and a specific sandbox binding resolve to the general names,
a sandbox binding entitles the computer tools but not `general.http`, and the analyst is offered
`general.shell`; `test_m6_sandboxes.py` charts through `general.shell`.

## M39-T03 File primitives

**Do:**

- Add `general.edit_file` (replace an exact string; `oldString` must appear once unless `replaceAll` is
  set), `general.grep` (lines matching a regular expression, as `path:line: text`), `general.glob` (paths
  matching a glob), `general.move` (rename or relocate), and `general.delete` (remove a file or folder), each
  confined to the working folder with a described schema. `general.read_file` takes a line range: `offset`
  is the first line and `limit` the number of lines.
- The write primitives carry a write risk class (`edit_file`, `move`, `delete` are `W1`, like `write_file`);
  the read primitives are `R0`.
- A move or a delete is durable: `snapshot_workspace` now drops the saved row of a file no longer on disk, so
  the restore of the next tool call does not write a moved-from or deleted file back (the fix is in the
  durability layer, for every caller, not in the tools).
- `files.read`'s `offset`/`limit` are documented as bytes, matching its behaviour; the line-range semantics
  are `general.read_file`'s.

**Done when:** an agent can edit, search, move and delete workspace files, read a file by line range, and a
move or delete stays done across the turn's later tool calls.

**Tests:** `test_m39_file_primitives.py` — edit (unique, ambiguous, missing, replaceAll), grep, glob, move
(source gone), delete (gone for later calls), read by line range, and path-escape refusal.

## M39-T04 Tools load on demand

Split: **T04** offers the core tools and a search tool above the threshold, adds a found tool's schema to the
next call, and scopes a search to the agent's grants (F45); **T04a** moves the tool vectors from each
process's memory to a durable per-tenant-and-model table so the first turn after a restart is not ranked by
words ([OQ-106](../open-questions.md)).

**Do:**

- When `resolve_catalog` marks the turn `tool_search_active` (over 30 tools, or search mode on), the agent
  loop sends only the core tools — `files.read`, `files.list`, `control.plan_update` — and the search tool
  (`control.search`, always injected so a search is possible), not the whole catalogue. The full catalogue
  stays in `by_name`, so a tool the model names still resolves.
- After the model calls `control.search`/`tools.search`, the found tools' schemas are added to the model's
  next call (`agent_loop._add_found_tools`), so the model can call what it found.
- `control.search` ranks only the tools the agent is granted, plus the always-available `files.*`/`control.*`,
  so a search never leaks another agent's tools (F45, `handlers._granted_names`). Ranking still uses the
  tenant's embedding model when one is set (M38a-T06).
- `prompts/text/tool_use.md` tells the model to search for a tool it does not see, then call the one named.

**Done when:** an agent with more than thirty tools is sent the search tool and the core tools, finds a tool
by searching, and calls it; and a search returns only that agent's tools.

**Tests:** `test_m39_deferred_tools.py` — a 90-tool agent is sent the search tool (not the catalogue) and a
searched tool joins the next call; a small agent is not deferred; a search is scoped to the agent's grants.

## M39-T04a Durable tool vectors

**Do:** a revision adds a per-tenant-and-model table of tool-text embeddings with `tenant_id` + RLS and
grants; `tools/search.py` reads and writes it instead of the process cache, so the first search after a
restart is ranked by meaning, not words (OQ-106). Embedding stays on its own thread; a search before the
vectors are ready is still ranked by words and says so.

**Done when:** the first turn of a new process ranks by meaning once the vectors exist, and no vector lives
only in process memory.

**Tests:** `test_m39_tool_vectors.py`; `test_migrations.py` up and down.

## M39-T05 The model chooses a skill

**Do:**

- The system prompt already lists the agent's skills by name and description (`capabilities_block`). The
  keyword match before the turn (`skills/match.py`) no longer loads a skill's body: it returns a hint, and
  `workspace/turn.py` adds a line naming the skill and telling the model to load it with `skills.load`.
- `skills.load` is bound by default: it joins `_IMPLICIT`, so it is always entitled, and the agent loop
  offers it whenever the agent has a skill, whether or not the agent binds the skills server (it survives the
  deferred-loading path through `_CORE_WHEN_SEARCHING`).

**Done when:** an agent with a skill is sent the skill list and `skills.load`, the pre-turn match only hints,
and the model loads the body itself.

**Tests:** `test_m39_model_chooses_skill.py` — the match hints without loading, `skills.load` is entitled by
default, and a skilled agent is offered `skills.load`; `test_m25_embed_http.py` asserts the hint, not the
body.

## M39-T06 MCP client depth

Split: **T06** keeps every content block and follows `tools/list` pages in one session; **T06a** reuses one
MCP session across a run's tool calls ([OQ-118](../open-questions.md)), which needs the run on the call and a
session cache.

**Do:**

- `remote_mcp._result_text` keeps every content block of a `tools/call` result — all text blocks joined, an
  image named by its type, a resource by its text or uri — and keeps the whole `result` in `structured`, so
  nothing is dropped (A15 kept only the first text block). `_blocks_text` does the join.
- `list_remote` follows `nextCursor`: it sends `tools/list` pages in one streamable session (initialising
  once, reusing the `mcp-session-id`) and accumulates the tools. `_next_cursor` and `_tools_page` read a page;
  `_rpc`/`_post_streamable` take an optional `session` dict to hold the session across the pages.

**Done when:** a tool result with several content blocks reaches the model whole, and a server that pages its
tool list is fully discovered over one session.

**Tests:** `test_m39_mcp_depth.py` — a result keeps all four of its blocks and reports an error flag; a paged
`tools/list` is discovered over one session.

## M39-T06a One MCP session per run

**Do:** a `tools/call` reuses the server's session across a run instead of opening and initialising a new one
each call. The run id reaches `call_remote`, a per-`(server, run)` session id is cached on the store, and an
expired session re-initialises once. `tools/list` pagination (T06) already shares a session within the call.

**Done when:** several tool calls to one MCP server in a run initialise the session once.

**Tests:** `test_m39_mcp_session.py`.
