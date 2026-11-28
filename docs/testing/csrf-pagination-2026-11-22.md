# CSRF and bounded Runs/chat history

Owner scope: repair CSRF and server-side pagination for **Runs and chat history first**, keep changes small, and preserve existing services. Branch: `codex/csrf-pagination`, based on `b3ccb9be`.

## Reuse and implementation

The existing `/api/v1/conversations` and `/api/v1/runs` handlers now use `ConversationRepository.page` under `tenant_session`, the caller's `chat:use` permission and Postgres RLS. They reuse `Page`, the existing HMAC cursor codec and cursor signing setting. SQL applies caller, tenant, preview/deleted visibility, search and status before `LIMIT limit+1`. Timestamp/UUID ordering handles timestamp ties. Cursors bind caller, resource and filters. Model and preview enrichment reads only the selected run page. Migration 0075 adds the two concurrent caller-order indexes; downgrade removes only those indexes. The unused full-list `ChatService` methods were removed. Unit stand-ins live only in `ar_testing` and are installed by test setup.

The web screens reuse `ListPagination` through one shared `useCursorPage` reader. Only one page of records is kept; Previous retains cursor boundaries, search/filter/size/account changes reset them, aborted responses cannot replace the new result, transient refresh errors retain acknowledged rows, and session/cursor failures clear them. Invalid-cursor Retry returns to page one. Chat retains an opened title independently of the currently visible history page. Runs uses the complete existing status vocabulary. The status selector aligns with the search input; page counts handle singular rows.

Startup metadata reads reuse existing hydration functions with explicit agent, model and settings projections. Session reads use the existing identity repository. This prevents the shell, upload-limit reader and chat bootstrap from hydrating unrelated conversation/message/run history before the bounded page request. Other detail and write routes retain the existing read-model architecture; this is not a claim that every catalogue or every tenant operation is now bounded. Framework access logs and SQL exception parameters no longer expose list search/cursor values; existing structured HTTP telemetry remains.

CSRF was an installation-origin mismatch: the staging API advertised port 3000 while the separate browser preview used a different origin. The isolated API now has `AR_PUBLIC_URL=http://ui-fixes.localhost:3110`; its explicit additional local origin is `http://127.0.0.1:3110`. Token and Origin checks remain enforced. No Origin stripping, token bypass or sign-in bypass was added. This configuration repair belongs to the prepared installation; no customer credentials or generated deployment secrets are committed.

## Isolation and live evidence

The managed worktree is `/Users/balakrishnavundavalli/.codex/worktrees/csrf-pagination/ui-clarity`. Preview: `http://ui-fixes.localhost:3110`. The API is on 29100; the `ar-ui-fixes` Compose project has its own named networks, database (25443), Valkey (26390), Temporal (27244) and object store (29333). The old `codex/ui-clarity` checkout, UI on 3102 and `ar-cert6` services were preserved. The old database was read only to create the private isolated copy; 47 actual stored objects were copied read only into its own object store. Scheduled system-worker activity remains stopped in the copied installation.

Normal browser sign-in and chat creation returned 200 and the saved conversation was read back with 200, then reopened through the UI. A valid session/token with an untrusted Origin returned `403 csrf_failed` and did not change the conversation count. The saved acknowledgement was reused for subsequent checks rather than repeating creation after a verifier assertion failed. Private credentials are read from the prepared environment, never from a committed test or report.

The production browser check read 25 + 22 conversations and two distinct pages of 25 runs from the actual copied installation. For both resources it verified disjoint IDs, searched an older page's ID through the server, then used the screen's Next and search controls. No browser requests were intercepted and no visual rows were fabricated. These live datasets are separate from the 100,000-record integration proof below.

## Validation

- Real Postgres integration creates 100,000 conversations and 100,000 runs in a test-owned database. It traverses all conversation pages without duplicates; checks literal search, filtered run pages, caller/tenant isolation, cursor tampering/scope changes, and the caller-page query plan. Metadata projections issue no conversation/run/message SELECTs. The final combined repository/projection, route-dispatch, API and identity run passed all 27 tests.
- Migration 0075 (numbered 0061 on the original branch, renumbered when it was rebased onto main) was upgraded, downgraded and upgraded again on the isolated copied database.
- The final standalone production server passed real-browser Runs/chat checks in light and dark at 1440px and 390px: eight checks, zero axe violations in main content and no document horizontal overflow.
- Web regression tests cover cursor navigation and search resets, scope changes, stale responses, bounded/valid envelopes, transient/session/cursor errors, chat history and Runs filters. All 91 web files / 849 tests passed with four workers. A first highly concurrent run timed out in the existing 100,000-kind masking test; the bounded-worker full rerun passed.
- Python mypy passed all 797 source files; full lint passed with existing nonblocking advisories. OpenAPI and both clients were regenerated with `make gen`.
- Full `make test` backend run: 1,960 passed, 30 failed, 4 existing skips, 712.85 seconds. It was not green. Five failures exposed missing-router handling and the shared database import in this change; those were corrected and all 26 affected middleware/architecture/read-model tests pass. The domain-name check also scanned generated custom `.next-*` folders; archived inactive builds and kept the running standalone artifact under the standard excluded `.next` directory, then reran the check successfully. Migration metadata and the existing single-head assertion now identify 0061.
- Broader failures include optional Qdrant checks without an endpoint/database environment, a Docker sandbox check, document conversion, and DSN/connection checks. The document failure was reproduced against a read-only export of parent revision `b3ccb9be`; three representative DSN/connection checks pass individually on both parent and changed revisions; their failures in the broad run remain an ordering/environment investigation. Running the new pagination integration tests together with all affected DSN modules and model/connection tests passes all 72 checks. These results are not described as green or as full-platform certification. `make check` was attempted; lint/type checks pass, while its full Python test gate is not certified. No CI run or push was performed. The redundant standalone unit run was interrupted; it is not counted as a passing check.

## How to test visually

The prepared private Compose configuration is `/tmp/ui-fixes-resolved.json`; it contains credentials and must not be committed or printed. Start only this project's API if necessary:

```sh
docker compose -p ar-ui-fixes -f /tmp/ui-fixes-resolved.json up -d --no-deps --no-build api
```

The production preview is built from this worktree with:

```sh
AR_NEXT_DIST=.next AR_API_URL=http://127.0.0.1:29100 pnpm --filter @ar/web build
cp -R apps/web/.next/static apps/web/.next/standalone/apps/web/.next/
cp -R apps/web/public apps/web/.next/standalone/apps/web/
PORT=3110 HOSTNAME=127.0.0.1 AR_API_URL=http://127.0.0.1:29100 node apps/web/.next/standalone/apps/web/server.js
```

Do not start another listener while the prepared preview is already running. Sign in using the same local account copied into the isolated database; credentials remain private. For a new installation, use the normal documented tenant seed with an owner-chosen password, configure its exact browser origin, and use independently allocated dependencies.

1. Open `http://ui-fixes.localhost:3110/login` and sign in normally. Chat opens with a bounded recent-history list.
2. In Conversations, choose Next, then Previous. Each page requests at most 25 items; navigation returns to page one correctly. Search a known older title or full conversation ID; the server can find it beyond the first page. Clear search to return to page one.
3. Open a saved chat, move through history pages, and check that the selected chat title stays visible in the conversation area. Open a different saved chat and confirm its messages/title replace the previous selection.
4. Open Runs. Choose Next/Previous and change Rows per page. Search an older run ID; change Status and clear it. Requests carry the server filter and a bounded limit; changing filters resets cursor navigation. A matching status never displays the no-matches notice.
5. In chat, choose New chat once. It should save normally, appear in history and reopen after refresh. Do not repeat a write merely because a browser verifier times out: inspect its saved acknowledgement first.
6. Review light/dark and narrow layouts. Search and status fields align, page controls remain accessible, and empty/error/loading states offer the appropriate recovery without presenting failed reads as empty data.

Focused repeatable checks:

```sh
uv run pytest libs/ar_domain/tests/integration/test_conversation_pages.py services/api/tests/unit/test_page_route_dispatch.py services/api/tests/unit/test_m2_api.py -q
pnpm --filter @ar/web test --maxWorkers=4
```
