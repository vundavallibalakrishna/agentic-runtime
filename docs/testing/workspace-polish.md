# Workspace presentation review — 26 October 2026

Task: M2.5-T01a. The requested direction is a calm, premium workspace with crisp typography and restrained colour.

## What changed

- Warm neutral tokens, subtle elevation, and finished light and dark surfaces.
- Grouped sidebar navigation, route breadcrumbs, permission-gated actions, mobile search, a focus-trapped mobile menu, keyboard-accessible account menu, and a skip link.
- A composed chat welcome with starter cards, a raised composer, and conversation history that can be opened on mobile.
- Agent cards with consistent metadata and actions, a prominent natural-language creation entry, card-shaped loading skeletons, empty filter recovery, and error retry.
- Existing chat, creation, editing, publication, rollback and bundle actions remain available. All new UI text is in the English message catalogue.

## How to test visually

The UI review server is at **http://localhost:3000**. The API uses **8005**, model gateway **8006**, Postgres **5433**, Valkey **6380**, and Temporal **7234**, selected to avoid other projects' occupied ports. The seeded tenant is `dev`; the assistant uses `fake-llm`, so no external model API key is required.

This review session uses the supported in-process, memory-backed development mode from OQ-31. New demo conversations and agent edits reset when the API restarts. The existing PostgreSQL volume is retained. The system and ingestion workers are not part of this review session.

From the repository root, dependencies can be installed with:

```bash
make bootstrap
```

This checkout had been moved from a different parent directory. Reinstalling Python dependencies repaired stale executable paths:

```bash
uv sync --all-packages --all-groups --all-extras --reinstall
```

After stopping any existing instance of this project's app processes, start the UI review services:

```bash
AR_DURABLE_STATE=memory AR_TEMPORAL_ADDRESS=localhost:1 OTEL_SDK_DISABLED=true \
  uv run honcho start -f Procfile.dev \
  api model-gateway mcp-gateway sandbox-manager channels \
  mcp-sql mcp-openapi fake-llm web
```

`OTEL_SDK_DISABLED` avoids exporting to the optional observability collector while it is not running. Application logs are still enabled. The explicit Temporal address makes the review mode independent of the running development Temporal server; memory mode does not attach Temporal.

1. Open `/login`, select **Sign in as admin@dev.local**, and check the chat welcome, recent conversations, and empty composer. SSO uses the seeded password `dev-password`, but SSO was not revalidated in this change.
2. Click **Write something**. A response prefixed `fake:` streams in. Use **Regenerate**, send another message, and use **Stop**.
3. Open the account menu and choose **Dark**, **Light**, or **System**. Both explicit themes should retain readable contrast, borders, and focus outlines; the default remains System.
4. Open Search or press Command/Ctrl+K. Search for **New chat** from Agents and run it; the app opens a fresh chat. Command/Ctrl+Shift+O also runs this action.
5. Open **Agents**. Inspect cards, search, change the status filter, favourite an agent, and use its Chat action. A search with no matches offers **Clear filters**.
6. Choose **New agent**, describe an assistant, review its draft, refine it, and apply it. Template, form, YAML, test chat, publish, rollback and bundle paths were exercised by the existing M3 suite.
7. At 375px, open and close the navigation drawer using Escape. Focus returns to the menu control. Open conversation history using **Show conversations**. The composer stays reachable, and neither reviewed page scrolls horizontally.
8. Sign in as `member@dev.local`; administrative navigation and agent creation controls are absent. Loading, empty and error/retry states are also exercised with controlled network responses in `workspace-polish.spec.ts`.

Earlier feature walkthroughs remain in the milestone checklists under `docs/testing/`.

## Existing full-stack startup issues

The initial `make dev AUTO_PORTS=1` attempt found an existing PostgreSQL 18 cluster at the root of its named volume. The ignored local file `deploy/compose/data/local-legacy.yaml` sets `PGDATA: /var/lib/postgresql` for that volume. No volume was removed. Its containers can be started with:

```bash
make up COMPOSE='docker compose -f compose.yaml -f deploy/compose/data/local-legacy.yaml'
```

A local unquoted PEM assignment was shell-quoted without changing the key. Migrations and seeding then completed. The full app launcher subsequently failed:

- System and ingestion workers: Temporal sandbox import errors involving `urllib.request.Request`; the system worker exited with status 138.
- Runtime worker: loading a newly created conversation raised `KeyError` during `execute_chat_turn`, preventing the full-stack chat response.

Those backend problems are not fixed by this presentation change. Full-stack development still requires follow-up; the working UI review mode is explicit above.

## Verification

- Web unit tests: **25 passed**.
- TypeScript: passed.
- Biome on changed frontend files: passed.
- Production web build: passed.
- Playwright selection (`workspace-polish`, `m2-chat`, `m3-builder`): **10 reported passed**. This includes one existing Keycloak test that returns early unless `AR_E2E_KEYCLOAK=1`; no SSO claim is made. The other nine tests executed their journeys.
- Axe: zero violations on Chat and Agents in light/dark at 375 and 1280 pixels, plus the existing builder/editor checks.
- `make check`: Python lint/import/dependency checks and frontend lint/knip ran; the target stopped at missing host `opa`.
- `make test`: **360 passed, 10 failed**, Python coverage **84.31%**, below the 85% gate. Failures include environment-sensitive port expectations, unavailable Qdrant/DB configuration, missing OPA, macOS sandbox path handling, and backend API/policy cases. No Python source was changed.

The task stays `in_progress` in the plan because repository-wide gates are not green. UI verification is complete.

## Captures

| View | Light | Dark |
|---|---|---|
| Chat, desktop | [1280px](workspace-polish/chat-light-1280.png) | [1280px](workspace-polish/chat-dark-1280.png) |
| Chat, mobile | [375px](workspace-polish/chat-light-375.png) | [375px](workspace-polish/chat-dark-375.png) |
| Agents, desktop | [1280px](workspace-polish/agents-light-1280.png) | [1280px](workspace-polish/agents-dark-1280.png) |
| Agents, mobile | [375px](workspace-polish/agents-light-375.png) | [375px](workspace-polish/agents-dark-375.png) |
