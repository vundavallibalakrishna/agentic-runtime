# Full-stack recovery review — 28 October 2026

Task: M2.5-T01b. This closes the local coverage, Temporal-startup and embedded-chat gaps recorded in [the detail-flow review](detail-flow-review.md). It also repairs failures exposed by running against the retained PostgreSQL database.

## Changes

- Temporal workflows import activity dependencies outside the deterministic sandbox and use JSON-compatible payload annotations. Runtime, ingest and system workers connect to the configured namespace and poll their task queues.
- The worker loads conversations, versions, messages and related context created after it started. Durable writes finish before HTTP success, survive retry, and preserve database edits during startup. Cancellation stops the activity and persists a terminal event; exhausted retries cannot leave a run indefinitely active.
- Login resolves persisted tenant/user IDs and effective role grants. Suspended identities fail closed. This supports older seeded databases whose IDs differ from the current demo IDs. Development key repair preserves the private/encryption keys and repairs their JWKS and shell quoting.
- Embedded chat now has a responsive, accessible conversation UI, restricted sessions, short-lived host authentication, exact framing origins, agent/conversation isolation, stream recovery and sign-in retry. Host credentials stay out of URLs and browser storage. Channel setup includes the portal origin and agent, with a usable embed snippet.
- Channel post selection is explicit. Tool submission displays the second-reviewer requirement as a pending review state without bypassing authorization.
- Routines and accepted events persist before runs reference them. Manual, signed-webhook and scheduled runs dispatch to Temporal. System activities reload the durable state, prepare a complete chat turn, and commit completion. Schedule edits, pause/resume and deletion affect the real Temporal schedule; signing keys persist through SecretStore. The run stream can follow work created by a different process.
- Chat uses the model gateway's `/v1/chat/completions` endpoint. Verification observed requests reach the gateway and fake model successfully.

## Local startup

The reviewed checkout is running at `http://localhost:3000`, with API `8005`, Temporal `7234` / UI `8233`, PostgreSQL `5433`, and Keycloak `8180`. `.env` holds the selected host ports and local secrets; it is not committed.

For a fresh checkout:

```bash
make bootstrap
make dev AUTO_PORTS=1 QDRANT=1
```

This machine retains a PostgreSQL 18 cluster at the volume root. Its ignored `deploy/compose/data/local-legacy.yaml` sets `services.postgres.environment.PGDATA: /var/lib/postgresql`. Preserve that override when restarting these dependencies:

```bash
make up QDRANT=1 COMPOSE='docker compose -f compose.yaml -f deploy/compose/data/local-legacy.yaml'
make migrate seed
AR_DURABLE_STATE=postgres OTEL_SDK_DISABLED=true uv run honcho start -f Procfile.dev
```

The full Procfile starts the API, three workers, model/MCP gateways, sandbox manager, channels, demo MCP servers, fake model and web. `OTEL_SDK_DISABLED=true` avoids exporting to an absent optional local collector. Do not reset the existing database to resolve a startup issue.

Seeded sign-in: `admin@dev.local`, `builder@dev.local`, `member@dev.local`, `approver@dev.local`; password `dev-password`. Both local buttons and **Continue with SSO** were exercised. The retained dev tenant's Enterprise capability and tenant feature now allow widget setup. New Enterprise/Self-hosted plans allow the capability; each tenant still opts in.

## Repeatable checks

The delivered smoke script creates uniquely named verification records, publishes an agent, streams its worker reply, indexes an uploaded document, runs a routine manually and through its Temporal schedule, and checks pause/resume. It leaves the routine paused and the records available for inspection:

```bash
uv run python scripts/full_stack_smoke.py
AR_PORT=8005 AR_WEB_HOST_PORT=3000 AR_E2E_KEYCLOAK=1 \
  E2E_SCREENSHOT_DIR=/tmp/ar-live-review \
  pnpm --filter @ar/web exec playwright test e2e/widget.spec.ts e2e/m2-chat.spec.ts \
  --grep 'keycloak|host token|dropped event|administrator|expired host|actual frame' --workers=1
```

Repository checks ran in a disposable copy without the developer `.env`. Test PostgreSQL was isolated on `55435`; Qdrant was on `6333`. The environment keeps migration tests and temporary database fixtures away from the retained development database. OPA and Helm were present on `PATH`.

```bash
export AR_DATABASE_URL=postgresql+asyncpg://test:test@127.0.0.1:55435/test
export AR_QDRANT_URL=http://127.0.0.1:6333
export OTEL_SDK_DISABLED=true
make check
make test
```

The complete seeded UI regression suite used a memory-mode API on `8305` and a production web build on `3100`. This keeps repeatable tool/approval/knowledge fixtures separate from real user data. Set the proxy at both build and runtime:

```bash
AR_PORT=8305 AR_PUBLIC_URL=http://localhost:3100 AR_DURABLE_STATE=memory uv run ar-api
AR_PORT=8305 AR_WEB_HOST_PORT=3100 API_PROXY_URL=http://127.0.0.1:8305 pnpm --filter @ar/web build
AR_PORT=8305 AR_WEB_HOST_PORT=3100 API_PROXY_URL=http://127.0.0.1:8305 pnpm --filter @ar/web start
AR_PORT=8305 AR_WEB_HOST_PORT=3100 E2E_SCREENSHOT_DIR=/tmp/ar-ui-review \
  pnpm --filter @ar/web exec playwright test --workers=1
```

Run the servers in separate terminals. Do not build into the `.next` directory used by the running development server.

## Results

| Check | Result |
|---|---|
| `make check` | Passed: formatting, lint, import boundaries, dependency declarations, mypy (473 source files), TypeScript, 460 Python tests and 85.21% unit-only coverage; 35 frontend/client unit tests |
| `make test` | Passed: 478 Python tests, 85.77% combined coverage, OPA tests (95.61% coverage), 33 web unit tests |
| Production web build | Passed |
| Full Playwright suite | 42 passing checks, including M2–M12 seeded journeys, loading/empty/error/retry states, keyboard/access checks and light/dark layouts at 375px and 1280px |
| Live SSO and widget | Six checks passed on the durable stack, including all four SSO roles, real worker reply, stream recovery, portal creation, token expiry and framing rejection |
| Real PostgreSQL regressions | Restart persistence, encrypted widget credentials, suspended users, auth audit, deletion, retained login identities and separate API/system/runtime routine stores passed |
| Full-stack smoke | Agent publication and runtime completion, document ingestion, manual/scheduled routine execution and schedule pause/resume passed |
| Worker startup | Runtime, ingest and system connected and polling; no startup traceback |

Coverage thresholds were not lowered and no tests were skipped to satisfy the gates. The SSO browser case is opt-in in the general suite and was separately run with Keycloak enabled.

## How to test visually

1. Open `/login`, use SSO for each seeded role, sign out, and sign back in as admin. Confirm the user's actual role and permitted navigation.
2. On Chat, send a message, inspect its trace, stop a slow answer, reload its history, and send another message. The completed/cancelled state and reply remain after refresh.
3. On Agents, use the natural-language builder, review/apply a draft, edit and publish it, then open its chat. Version and read-only/error states follow the [detail-flow walkthrough](detail-flow-review.md#visual-walkthrough).
4. On Tools, submit a server for review. When self-review is disabled, see the pending-review message. Use a separate reviewer for approval. Inspect Connections, approvals, reviews and policy simulation using the seeded UI suite's fixtures.
5. On Knowledge, upload a text file, open the collection's documents and jobs, and search it. The document becomes indexed; failed/empty states remain recoverable. Review Memory, Skills and the child-run trace through the existing seeded journeys.
6. On Routines, open the paused `Local verification …` routine created by the smoke script. Inspect its manual and scheduled events, follow each run and read the assistant's output. Pause/resume changes the corresponding entry in Temporal UI. Leave verification schedules paused.
7. On Channels, choose **Website widget**, provide a name, exact portal origin, server-side signing key and allowed agent, then create it. The host's backend supplies a short-lived JWT through the documented handshake. Open the embedded assistant; send, stop and start a new chat. An expired token offers retry; a disconnected stream reloads the same conversation. Switching the recent-post selector changes the integration shown.
8. Review Usage and quotas, then repeat the management/detail pages in Light and Dark at desktop and mobile widths. Panels stack without horizontal overflow. The existing screen and detail walkthroughs cover all implemented M2–M12 pages.

## Scope of verification

This is a local-stack verification using `fake-llm` and seeded connector fixtures. It does not certify real-model answer quality, external provider credentials, external channel delivery or production deployment. Hosted CI has not been run for this local commit. The milestone records retain that distinction rather than claiming the full CI definition of done.

## Captures

- [Embedded chat, desktop light](full-stack/widget-light-1280.png)
- [Embedded chat, mobile dark](full-stack/widget-dark-375.png)
