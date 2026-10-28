# M21b — General tools

A small set of platform tools so an agent can do most tasks without a dedicated connector. Each tool is registered, schema-checked, granted per agent, policy-gated, traced, audited and limited. GRC stays parked.

This milestone is one pull request. The tools share one workspace and one policy path, so splitting them would land a chat that cannot finish a task.

## Tasks

### M21b-T01 Sandbox and workspace

- **Depends on:** M21-T04
- **Do:** `general.code` and `general.shell` run in a per-run workspace. Network is off unless the agent turns it on, and then only through the egress allow list. `general.read_file`, `general.write_file` and `general.list_files` use that workspace. Uploaded attachments are copied in. Produced files are downloadable.
- **Done when:** A command cannot see platform secrets or the host filesystem when user namespaces are available, and a path outside the workspace is rejected.
- **Tests:** `libs/ar_common/tests/unit/test_isolate.py`, `libs/ar_domain/tests/unit/test_m21b_tools.py`

### M21b-T02 Fetch, search and HTTP

- **Depends on:** M21b-T01
- **Do:** `general.fetch` returns cleaned page text and marks it as untrusted data. `general.search` calls a pluggable provider (Brave or Tavily) and returns a configuration error when no key is set. `general.http` sends a request, takes auth from a named secret, redacts that secret, and waits for approval unless the method is GET or HEAD.
- **Done when:** A prompt-injection string in a fetched page is wrapped as data, a missing search provider does not invent hits, and a POST pauses for approval.
- **Tests:** `libs/ar_domain/tests/unit/test_m21b_tools.py`

### M21b-T03 Builder and chat

- **Depends on:** M21b-T02
- **Do:** The tools screen lists the general tools and edits egress hosts and the search provider. The agent builder switches each tool on or off and sets timeout, network and extra hosts. Chat renders code output, file downloads, page title and snippet, search hits, and the HTTP method and status.
- **Done when:** Playwright covers the tools screen, the builder and a chat tool card in light and dark at desktop and mobile widths.
- **Tests:** `apps/web/e2e/m21b-tools.spec.ts`

## Out of scope

MCP client and OpenAPI import (M22). Document tools, knowledge, connector libraries, orchestration, and exposing agents. A full headless browser is not added; `general.fetch` is the page tool.
