# Detail screens and flow review — 27 October 2026

Follow-up: the local coverage, worker startup and embedded-chat gaps below are resolved in the [28 October full-stack review](full-stack-review.md). Hosted CI remains unverified.

Task: M2.5-T01a. The review extends the management-page layout pass to implemented detail screens and their failure, pending, completed and read-only states.

## Changes

| Area | Result |
|---|---|
| Agent editor | Instructions lead; publishing, versions and test chat form a compact side column. Back navigation, retry, keyboard tabs and read-only controls are consistent. Failed saves stop validation and publication without discarding edits. |
| Agent builder | Starting a new request clears the previous proposal. Validation failures prevent applying a draft; creation and refinement show pending state. |
| Skill editor | Instructions and preview share the page; versions and usage have bounded panels and empty states. Failed saves stop publication. Asset uploads preserve unsaved instructions. Readers can inspect published content and advanced fields without edit actions. |
| Approval and review details | The statement or proposed action leads a bounded reading column. Comments precede decisions. Pending actions disable repeat submissions. Completed items no longer show decision forms. Fetch errors offer retry. |
| Routine detail | Pause/resume reflects current status. Run-now links to the resulting trace. Upcoming runs and accepted events have formatted dates and explicit empty states. |
| Knowledge detail | Documents, Search, Sources and Jobs use keyboard-accessible tabs. Fetch and upload failures offer recovery; a failed upload retains the selected file. Search clears old results before retrying. Readers do not see management actions. |
| Source creation | A bounded, labelled form validates the name and URL. The web allowlist follows the entered host. Other source kinds expose configuration and saved credential references instead of silently submitting an empty web configuration. |
| Run inspector | Summary, trace and activity are separate. Loading, empty activity and error/retry states do not overlap. |
| Profile and usage | Costs convert micros to currency correctly. Linking/unlinking has pending/error feedback, and usage fetch failures are visible. |
| Chat | Stop targets the current run and handles completion races. New chat cancels stale stream/history reads, clears conversation attachments and removes the old conversation from the URL. This also handles an initial deep-linked history request. Failed conversation creation retains the typed draft. Citation previews use a focus-trapped dialog with Escape dismissal. Workspace fetches have loading and retry states. |
| Platform health | Failed API metadata requests no longer show a healthy card. Loading and retry are explicit; the page has a Back to chat action. |
| SSO and home | The old root starter page redirects to Chat. Signed-out home and detail links open Sign in instead of an empty workspace with an authentication error. Keycloak sign-in and sign-out were exercised for admin, builder, member and approver. |
| Local policy and computer | OPA loads the authenticated tenant bundle through Compose. Bundle authentication compares the actual secret with constant-time comparison; masked tokens are rejected. Sandbox roots resolve macOS temporary-directory aliases before confinement checks. |

The management layouts remain covered by [screen-layout-review](screen-layout-review.md). Advanced standing approvals label unavailable tools, show expiry and revocation, and link to the related routine. The new detail fixtures separate layout/state testing from the live API journeys; they do not substitute for the live flow tests.

## How to test visually

Use the existing checkout's dependencies and `.env` described in [workspace-polish](workspace-polish.md#how-to-test-visually). The local app is `http://localhost:3000`, API `8005`, fake model `8099`, model gateway `8006`. This remains the supported memory-backed review mode: restarting the API resets temporary demo edits and sessions. The PostgreSQL volume is retained.

After stopping this project's running app processes:

```bash
make up COMPOSE='docker compose -f compose.yaml -f deploy/compose/data/local-legacy.yaml'
AR_DURABLE_STATE=memory AR_TEMPORAL_ADDRESS=localhost:1 OTEL_SDK_DISABLED=true \
  uv run honcho start -f Procfile.dev \
  api model-gateway mcp-gateway sandbox-manager channels \
  mcp-sql mcp-openapi fake-llm web
```

`local-legacy.yaml` is specific to the retained PostgreSQL volume in this checkout; a fresh checkout uses `make up` without it. OPA uses `AR_PORT` and `AR_OPA_BUNDLE_TOKEN` from the same environment as the API. Its bundle readiness endpoint is `/health?bundles` on the configured OPA host port.

1. Open `/login`. Use **Continue with SSO**, enter `admin@dev.local` then `dev-password`. Expect Chat, not the old starter page. Repeat with `builder@dev.local`, `member@dev.local` and `approver@dev.local`; the account menu signs out. The four development sign-in buttons remain available.
2. On Chat, send a message, regenerate, then send a slow answer and Stop. Open another conversation or start New chat while loading history; old content must not replace the new conversation. Attach a file and inspect Artifacts/Workspace and View trace.
3. Open Agents, create an agent in natural language, review/refine/apply the draft, edit instructions, validate and publish. Open Advanced and navigate tabs with arrow keys. Review versions, rollback and bundle dry-run/import. A failed draft save must retain edits and prevent publication.
4. Open Tools and Connections. Register the demo server, discover tools, connect, then chat with Desk to file a ticket. Pending actions disable repeat clicks and failures remain visible.
5. Ask Desk to create a pet. Open Approvals, inspect the proposed call, add a comment and approve. Return to the conversation and see its result. Open Reviews and sign the seeded review; the completed detail retains its status without a decision form. A W3 delete exercises identity confirmation and the approver handoff. Activated policies can take up to 15 seconds to reach OPA; the UI states this, and the real-sidecar test polls the decision before issuing the delete.
6. Open Knowledge and a collection. Inspect all four tabs, upload a text document, search it and open a citation in Chat. Press Escape to close the citation preview. Connect a web source using a valid URL; other connector kinds require their actual configuration and saved credentials.
7. Ask the assistant to remember a preference, start another chat and confirm recall. Delete the preference in Memory, then approve the seeded shared lesson in the Assistant editor. Member login must not expose another user's private memories.
8. Open Skills and Brand guidelines. Review instructions, preview, assets and dependent agents. Create/publish a skill, use Research lead, inspect its child runs, and ask Writer for a document. A reader can inspect a skill but cannot save or publish it.
9. Create a routine, inspect upcoming runs, run it now, follow the trace, pause and resume it. Open Channels, test a connection and inspect posts. Link/unlink the seeded account code through Profile.
10. Open Usage, export CSV, inspect quotas, and try the isolated quota-probe agent with a zero allowance. The blocked message explains the quota, and displayed costs use currency units rather than raw micros.
11. Repeat the detail pages at 1280px and 375px in Light and Dark. Back actions remain in the header; panels stack; content does not widen the viewport. Slow or fail a detail request and use Try again. No publish, approve, sign or run controls should appear for an unloaded record.

## Verification environment

Final browser testing uses a disposable memory API on `8305`, real OPA on `58181`, and a production web build on `3100`. PostgreSQL tests use a disposable container on `55435` and the optional Qdrant service on `6333`. Repository checks run in a copy without the developer `.env`, using dedicated Python dependencies. This avoids both local-secret configuration interference and migrations against the retained development database. After verification, restarting the local app on `3000` loads the backend fixes and resets its temporary memory-mode sessions and edits.

The OPA bundle fix was also exercised with a separate real OPA container on `58181`: bundle readiness succeeded, the authenticated bundle loaded, and a W2 call returned `require_approval`. The endpoint regression rejects missing, incorrect and masked bearer tokens and verifies ETag/304 behavior.

Run the browser checks against a fresh seeded review API:

```bash
AR_PORT=8305 AR_WEB_HOST_PORT=3100 AR_OPA_URL=http://127.0.0.1:58181 E2E_SCREENSHOT_DIR=/tmp/ar-ui-review \
  pnpm --filter @ar/web exec playwright test \
  'm[2-9]-|m1[0-2]-|chat-recovery' --workers=1 --reporter=line
AR_PORT=8305 AR_WEB_HOST_PORT=3100 AR_OPA_URL=http://127.0.0.1:58181 E2E_SCREENSHOT_DIR=/tmp/ar-ui-review \
  pnpm --filter @ar/web exec playwright test detail-screens screen-layouts auxiliary-screens --workers=1
AR_PORT=8005 AR_WEB_HOST_PORT=3000 AR_E2E_KEYCLOAK=1 \
  pnpm --filter @ar/web exec playwright test m2-chat --grep keycloak --workers=1
```

## Completed checks

- Full Playwright suite against the production build and real OPA: 36 passing checks, including seeded live journeys from chat through agent creation, tools, approvals, knowledge, computers, memory, skills, routines, channels and quotas. The conditionally enabled SSO case in this run was separately exercised with Keycloak enabled. After the final deep-link recovery fix, all three chat-recovery checks passed again.
- Frontend unit suite: 31 passing tests, including failed-save publication guards, upload retry, completed approval state, read-only skills and micros-to-currency conversion.
- Production web build, TypeScript, Biome and Knip: passed. Biome retains the existing non-failing image-element advisory in the artifact preview.
- Layout/state suite: 10 passing tests covering 16 management routes and seven detail routes in both themes at 375px and 1280px, plus builder/source/profile and loading/error/retry checks. No axe violations or page overflow in those views.
- Keycloak: all four seeded roles complete sign-in and sign-out.
- After restarting the app on `3000`, all eight home/chat/recovery/SSO smoke checks passed. API, web and authenticated OPA bundle readiness passed. The final standing-approval unavailable/revoked state also passed its focused mobile accessibility regression.
- `make test`: 371 Python tests passed; combined coverage 85.02%; OPA tests passed with 95.61% coverage; frontend tests passed. The latest additional skill-reader regression is included in the separately rerun 31-test frontend suite.
- `make check`: lint/import/dependency checks, mypy on 467 files and TypeScript passed. All 357 selected Python tests passed, but unit-only coverage was 84.75%, below the required 85%; the target therefore remains red. The threshold was not changed.

The plan entry remains `in_progress` because the repository-wide gate and CI definition of done are not yet satisfied. The earlier full Temporal-worker startup failures in [workspace-polish](workspace-polish.md#existing-full-stack-startup-issues) are outside this memory-mode UI verification. External provider credentials, real-model quality and production deployments are not certified by the seeded demo journeys. The existing widget route is a static host integration shell; authenticated embedded chat is not covered by the signed-in workspace journeys.

## Captures

- [Agent editor, desktop light](detail-screens/detail-agent-light-1280.png)
- [Approval, mobile dark](detail-screens/detail-approval-dark-375.png)
- [Skill editor, desktop dark](detail-screens/detail-skill-dark-1280.png)
- [Collection, mobile light](detail-screens/detail-library-light-375.png)
- [Run inspector, desktop light](detail-screens/detail-run-light-1280.png)
