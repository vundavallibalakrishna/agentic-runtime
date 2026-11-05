# M39 — Tool surface

Goal: a model can choose and use every tool from its description alone, and has the file primitives a
general agent needs. Source: [the tool review](../testing/tools-review-2026-11-05/tools-review.md),
sections B and C and finding A15.

Depends on: M38. Tasks are split into full task entries when the milestone starts.

## M39-T01 Described tools, with a lint

**Do:** every tool has a description on each parameter, enums where the values are closed, item schemas for
arrays, the required fields, a note on when to use it and when not to, and the shape of its result. A script
in the `docs` CI job fails when a parameter has no description. Rewrite `prompts/text/tool_use.md`.

## M39-T02 One workspace

**Do:** `general.*` and `sandbox.*` read and write the same workspace for a conversation. The duplicate file
and command tools are retired with an alias for stored agent versions.

## M39-T03 File primitives

**Do:** `edit_file` (replace an exact string), `grep` (search by content), `glob` (search by name), `move`,
`delete`, and `read_file` by line range. Deletes and overwrites follow the write risk classes.

## M39-T04 Tools load on demand

**Do:** above a tool-count threshold the model gets the core tools and a search tool. A found tool's schema
is added to the next model call. Ranking uses the tenant's embedding model when one is set.

## M39-T05 The model chooses a skill

**Do:** the system prompt lists the agent's skills by name and description. `skills.load` is bound by
default. The keyword match before the turn stays as a hint and no longer loads a skill body.

## M39-T06 MCP client depth

**Do:** one session for each server and run, `tools/list` pagination, and every content block of a result
(text, image, resource) kept.
