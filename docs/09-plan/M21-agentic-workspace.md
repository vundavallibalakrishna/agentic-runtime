# M21 — Agentic workspace

The product is a generic agentic platform. A customer connects an LLM, defines agents, and gives them tools, connectors and skills. GRC document work is something a customer can build later. The GRC pack stays in the repository and is parked.

## Tasks

### M21-T01 Park the GRC pack

- **Depends on:** M20-T04
- **Do:** Add `AR_GRC_PACK_ENABLED` (default `false`). When it is off, do not install GRC templates, routines or seeded catalogues for the dev tenant, and do not show GRC navigation. Leave `packs/grc` and its migrations in place. Core does not import `ar_pack_grc`.
- **Done when:** A signed-in user does not see a GRC link, and `/grc` is not a product screen. Pack unit tests still install the pack themselves and pass.
- **Tests:** `packs/grc/tests/unit/test_m21_parked.py`

### M21-T02 Chat-first workspace

- **Depends on:** M21-T01
- **Do:** Chat stays the home screen. A conversation can pick an agent and a model alias. The thread shows the plan, each tool call, its result, and a retry. Errors are visible. Navigation still reaches agents, tools, skills, connectors, runs and settings.
- **Done when:** The chat composer has an agent picker and a model picker, and a streamed run shows tool progress.
- **Tests:** `apps/web/e2e/m21-workspace.spec.ts`

### M21-T03 Agent loop

- **Depends on:** M21-T02
- **Do:** When the selected model is a real provider, run plan, act, check, retry. Limits for steps, time, cost and tool calls come from the agent budget. Tool results are wrapped before they re-enter the prompt. A failed call is returned to the model for another attempt. A call that changes stored data uses the existing approval gate. The default assistant binds the read-only control tools with `max_tool_calls` 8. Every step is a run event and an audit row.
- **Done when:** A scripted real-provider turn records a failed tool call, a retry, a check, and an approval wait.
- **Tests:** `libs/ar_domain/tests/unit/test_m21_loop.py`

### M21-T04 Agent builder and model setup

- **Depends on:** M21-T03
- **Do:** The new-agent screen can create an agent from a form (name, instructions, model) and publish it. The editor can change the name, instructions, model, tools, connectors, skills and limits, then open that agent in chat. Model connection stays on Admin → Models: an OpenAI-compatible endpoint, a test call, and an encrypted key that is not returned.
- **Done when:** A user can create an agent in the UI and chat with it on the model they connected.
- **Tests:** the workspace Playwright spec and the M21 checklist's real-model section.

## Out of scope

MCP client and OpenAPI import (M22). Deleting the GRC pack. General tools are M21b.
