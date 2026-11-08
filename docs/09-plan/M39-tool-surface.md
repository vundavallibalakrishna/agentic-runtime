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

**Do:** above a tool-count threshold the model gets the core tools and a search tool. A found tool's schema
is added to the next model call. Ranking uses the tenant's embedding model when one is set
(`tools/search.py`, M38a-T06). Because every turn then ranks tools, the vectors move from each process's
memory to a table for each tenant and model, so the first turn after a restart is not ranked by words
(OQ-106). A search returns only tools the agent is granted (F45).

## M39-T05 The model chooses a skill

**Do:** the system prompt lists the agent's skills by name and description. `skills.load` is bound by
default. The keyword match before the turn stays as a hint and no longer loads a skill body.

## M39-T06 MCP client depth

**Do:** one session for each server and run, `tools/list` pagination, and every content block of a result
(text, image, resource) kept.
