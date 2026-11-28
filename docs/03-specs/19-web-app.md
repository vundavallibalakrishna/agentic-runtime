# Spec 19: Web app (`web`)

Deployable `web` (`apps/web`, package `@ar/web`, port 3000): Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query 5, zustand (stream state), nuqs (URL state), react-hook-form + zod, `@ar/api-client` (generated from the `api` OpenAPI by hey-api). The web app is a thin client of the BFF (`api`): it never holds tokens; auth is the `ar_session` HttpOnly cookie + `ar_csrf` double-submit header. PRD: all feature files in [01-prd](../01-prd/README.md). Conventions: [coding-standards-typescript](../08-quality/coding-standards-typescript.md).

## 1. Architecture

- **Routing/rendering**: App Router with route groups `(auth)`, `(app)`, `(admin)`, `(platform)`, `widget`. Pages are React Server Components only for the shell/layout and static parts; data-heavy views are client components using TanStack Query. No server-side data fetching with user credentials except the session gate in `src/proxy.ts`.
- **Session gate**: a workspace request with no `ar_session` cookie is redirected to `/login`. A request that carries one is confirmed with `GET /api/v1/auth/session` at most once per `AR_SESSION_GATE_TTL_S` (default 15 seconds); concurrent requests share that confirmation. A Next.js prefetch (`next-router-prefetch`, `next-router-segment-prefetch`, or `Purpose: prefetch`) does not start a session call. A `401` redirects to sign-in. A `429`, a `5xx`, or an unreachable API lets the page load so the client can show a retry; it is not a sign-out. The cookie stays the opaque server-side session id. The shell and the open page share one client read of that session for the same interval.
- **API access**: same-origin. In production the ingress routes `/api/*`, `/scim/*`, `/channels/*` to their services and everything else to `web`. The web server proxies `/api`, `/v1` and `/.well-known/agent-card.json` to `API_PROXY_URL` (or `AR_API_URL`, or `http://127.0.0.1:$AR_PORT`) when the request arrives. The address is not captured at image build.
- **Client**: `src/lib/api.ts` creates the hey-api client with `credentials: "include"`, injects `X-CSRF-Token` from the `ar_csrf` cookie on unsafe methods, `Idempotency-Key` (uuid v4) on POSTs that create things or post messages, and maps RFC 9457 errors to `ApiError {status, code, title, detail, errors[]}`. 401 → redirect to `/login?return_to=…`; 403 `tenant_suspended` → `/suspended`.
- **Query keys**: `src/lib/query-keys.ts` (one factory per resource: `qk.agents.list(filters)`, `qk.agents.detail(id)`, …). Mutations invalidate by prefix. Default `staleTime` 30 s; lists use `keepPreviousData`.
- **Streaming**: `src/lib/sse.ts` uses `fetch` + `eventsource-parser` (supports cookies, `Last-Event-ID` resume, abort). `useRunStream(runId)` and `useConversationStream(conversationId)` feed the zustand store `useRunStreams` (reducer normative in [stream-events §6](../05-contracts/stream-events.md#6-client-reducer-normative-for-the-web-app)); reconnect with exponential backoff (0.5 s → 10 s) and resume from the last seq.
- **Notifications**: `useNotifications()` subscribes to `GET /api/v1/notifications/events` once per tab (BroadcastChannel leader election to keep a single connection across tabs).
- **Permissions**: `SessionInfo.permissions` (from `GET /api/v1/auth/session`) drives navigation and `<Can permission="agents:publish">` guards; the server remains authoritative.
- **i18n**: `next-intl` with `en` (default) and message catalogs in `apps/web/messages/{locale}.json`; all user-visible strings go through `t()`. Dates via `date-fns` in the user's timezone. RTL not required in v1.
- **Theming**: light/dark/system (class strategy), tenant branding (`settings.branding.primary_color`, logo) applied via CSS variables.
- **Accessibility**: WCAG 2.2 AA; axe checks in Playwright for every page; full keyboard navigation; live regions for streaming text (`aria-live="polite"`, throttled).
- **Security**: CSP with nonces (`script-src 'self' 'nonce-…'`), `frame-ancestors 'none'` (except `/widget/*`), Markdown rendered with `react-markdown` + `rehype-sanitize` (no raw HTML), links from agent output open with `rel="noopener noreferrer nofollow"` and show the full URL on hover; images in agent output only from same-origin file URLs (blocks exfiltration via image URLs, [prompt-injection §6](../06-security/prompt-injection.md)).

## 2. Directory layout (`apps/web/src`)

```text
app/
  layout.tsx                    # html, providers, theme
  (auth)/login/page.tsx
  (auth)/select-tenant/page.tsx
  (auth)/invite/[token]/page.tsx
  (auth)/suspended/page.tsx
  (app)/layout.tsx              # AppShell: sidebar, top bar, command palette, notifications
  (app)/chat/page.tsx
  (app)/chat/[conversationId]/page.tsx
  (app)/agents/page.tsx
  (app)/agents/new/page.tsx
  (app)/agents/[agentId]/page.tsx
  (app)/agents/[agentId]/edit/page.tsx
  (app)/agents/[agentId]/evals/page.tsx
  (app)/tools/page.tsx
  (app)/tools/new/page.tsx
  (app)/tools/[serverId]/page.tsx
  (app)/connections/page.tsx
  (app)/knowledge/page.tsx
  (app)/knowledge/[collectionId]/page.tsx
  (app)/knowledge/[collectionId]/sources/new/page.tsx
  (app)/routines/page.tsx
  (app)/routines/new/page.tsx
  (app)/routines/[routineId]/page.tsx
  (app)/skills/page.tsx
  (app)/skills/[skillId]/page.tsx
  (app)/approvals/page.tsx
  (app)/approvals/[approvalId]/page.tsx
  (app)/runs/[runId]/page.tsx
  (app)/memory/page.tsx
  (app)/files/page.tsx
  (app)/settings/profile/page.tsx
  (app)/settings/notifications/page.tsx
  (admin)/admin/layout.tsx      # requires any admin permission
  (admin)/admin/{users,teams,roles,sso,models,policies,channels,sandboxes,secrets,usage,quotas,audit,api-keys,webhooks,evals,settings,support-access}/page.tsx
  (platform)/platform/{tenants,models,plans,health}/page.tsx
  widget/[integrationId]/page.tsx
components/
  ui/                           # shadcn primitives (generated, not edited by hand except tokens)
  shell/                        # AppShell, Sidebar, TopBar, CommandPalette, NotificationBell, TenantSwitcher, UserMenu
  chat/                         # see §4
  agents/ tools/ knowledge/ routines/ skills/ approvals/ runs/ memory/ files/ admin/ platform/
  common/                       # DataTable, EmptyState, ErrorState, ConfirmDialog, CodeEditor, JsonView, MarkdownView, Can, PageHeader, CopyButton, RelativeTime, StatusBadge, RiskBadge, UserPicker, AgentPicker, ToolPicker, CronInput
lib/                            # api.ts, sse.ts, query-keys.ts, permissions.ts, format.ts, markdown.ts, idempotency.ts
stores/                         # useRunStreams.ts, useComposerDrafts.ts, useUiPrefs.ts
hooks/                          # useSession, useRunStream, useConversationStream, useNotifications, useCan, useDebounce
messages/                       # i18n catalogs (en.json)
```

## 3. Pages

Each page lists: route, access, API calls, main components, URL state.

Shared loaded-list pagination always preserves the returned range/count. Known single-page results omit navigation and the page indicator. A non-compact pager retains its size selector when the result exceeds the smallest offered size, even when a larger selected size fits everything on one page. Known lists fitting the smallest size need only their count. Unknown-total cursor pages retain navigation and non-compact size selection, since one small page cannot establish the stream total. These controls bound client-rendered rows and do not establish server-side pagination.

New-work agent pickers in Chat, Routines, Schedules and channel configuration offer only returned metadata marked `status: published` and `disabled: false`. This is an availability hint; the API remains authoritative for permissions, visibility and lifecycle changes after the read. An unavailable agent requested in the chat URL requires an explicit replacement or a confirmed available default. Saved conversation speaker names resolve against the full returned catalogue, including archived agents. Management references and version-specific evaluations retain their own selection rules; widget selection uses its authorised session list. Missing availability metadata is not assumed runnable. See OQ-166 for the separate routine validation gap.

### 3.1 Auth
| Route | Purpose | API |
|---|---|---|
| `/login` | An email + password form that posts to `POST /api/v1/auth/login`; a wrong password is shown in place, success redirects into the app. | `GET /api/v1/meta` (branding, self-signup flag) |
| `/select-tenant` | For users in multiple tenants (platform admins) | `GET /api/v1/auth/session`, `POST /api/v1/auth/switch-tenant` |
| `/invite?token=…` | Accept an invitation: shows the address and the workspace, takes a name and a password twice, then points to sign-in. Opens without a session | `POST /api/v1/auth/invitation`, `POST /api/v1/auth/invitation/accept` |
| `/forgot-password`, `/reset-password?token=…` | Ask for a reset link; choose a new password with the mailed link. Both open without a session | `POST /api/v1/auth/password-reset`, `POST /api/v1/auth/password-reset/confirm` |
| `/suspended` | Tenant suspended notice | – |

### 3.2 Chat (`/chat`, `/chat/[conversationId]`) — `chat:use`
Layout: left **ConversationList** (search `q`, filters agent/pinned/shared; infinite scroll; actions rename/pin/archive/delete/share), center **ChatThread**, right collapsible **WorkspacePanel** (tabs: Plan, Files, Computer, Sources).
- `/chat`: **AgentPicker** (usable agents, starter prompts of the selected agent) + **Composer**; first send calls `POST /api/v1/conversations` with `message` then `router.replace('/chat/{id}')`.
- `/chat/[conversationId]`: `GET /api/v1/conversations/{conversation_id}`, `GET …/messages` (paged upwards), `useConversationStream(id)` live; posting `POST …/messages`; regenerate/edit/activate branch; cancel (`POST /api/v1/runs/{run_id}:cancel`); feedback; share dialog (`…/shares`); export (`…/export`).
- URL state: `?run=` (focus a run in the Run drawer), `?panel=files|computer|plan|sources`.

Opening a saved chat from its query URL or history reads its returned `activeRunId`. A working run reconnects through the existing SSE reader; paused approval/input states show Inbox and run-detail guidance. Run metadata is checked before choosing that behaviour, and generation stays held during restoration or an unconfirmed read. Refresh reads current state and reconnects working runs without replaying a message, edit, regenerate or resume request. Switching chats cancels the scoped reader; stale replies cannot replace another chat. No active run is inferred when the snapshot returns none.

Normal message submission and New chat creation acquire the shared synchronous request guard before posting. A newly created conversation continues its own request; navigation cancels other requests. Creation and message posts send an `Idempotency-Key` through the existing contract. Progress distinguishes opening, sending and generation. Transcript rows come from the saved conversation read after an acknowledged run reference; no temporary local reply is presented before that read. Only an acknowledged message clears its unchanged submitted draft and submitted file selection; newer text remains. File selection/removal is locked while the send awaits acknowledgement, then available for the next message during reply generation. An unconfirmed send retains its draft/files and holds generation until read-only Refresh checks the conversation/run. Refresh never replays the message. A failed attempt to create another chat preserves an existing approval/input hold. Empty-chat recovery hides inactive suggestions and retains a named keyboard-focusable scroll region.

Main-chat file uploads use a single guarded sequential batch with actual filename/index progress and an explicit Stop upload control. Generation waits while the batch is pending. Only confirmed ready metadata enters the selection; the first refusal, incomplete receipt or non-ready status stops the remaining batch, preserves earlier confirmed files and holds generation until the person reselects files or explicitly continues with the current selection. Stop retains confirmed files and returns focus to the composer; it promises no server rollback. Conversation changes, unmount and explicit new-draft reset cancel the browser request and ignore stale responses. Reloading the same saved chat preserves its file selection and pending batch. Library-picker drafts reset with the attachment context. Widget uploads retain their separate authorised endpoint and session boundary.

Chat Stop acquires a synchronous request guard and shows separate requesting and acknowledged-cancellation progress. An acknowledgement does not mean the run is cancelled: the existing event reader and saved metadata determine its actual outcome. Reopening an active run whose metadata reports cancellation requested retains that progress without posting Stop again. A refused or incomplete acknowledgement keeps the active reader and exposes the error with an explicit retry. If a read confirms the run already ended, the UI holds new generation until read-only Refresh loads the saved transcript; it does not invent a completed reply. Conversation changes/unmount discard scoped feedback and late replies. Successful explicit recovery returns focus to the composer only if focus has not moved elsewhere.

The shared ReferencePicker treats a later disabled prop as a closed dialog: pending metadata reads stop, unapplied multiple selections are discarded and selection handlers remain guarded. Re-enabling does not reopen it or change its controlled saved value. This applies to all existing picker callers.


Saved review output is a collapsed disclosure with its returned row count. Opening it mounts search over returned values, 25/50/100-row pages and independent column pages for wide results. Duplicate record IDs do not merge rows. Structured values render as JSON; long cells expose their full value through a bounded keyboard-scrollable disclosure. Empty search and fieldless records have separate explanations. These are presentation controls over existing saved message content; they do not establish server-side pagination.

The main chat's Sources and Why actions share the message action row. Source search/verification filtering and the shared pager bound the list; source previews use a named keyboard scroll region and retain the current list position on return. Why reads the saved grounding endpoint only when opened for a saved assistant reply, including replies without citations. Loading, unavailable details (404), request/validation failure with retry and a returned report with no claims are distinct. Closing or changing message identity aborts the read. Returned mode, claim search/status filtering and paging never infer a successful check from a failed read. Full saved claim metadata mounts only on expansion. Dialog closure restores focus to its action. These presentation bounds do not establish server-side 100,000-record transport.


The earlier `/documents/compare` (including `comparisonId` query references), `/documents/checks/[checkId]` and `/documents/rewrites/[rewriteId]` URLs share a compatibility entry explaining that document work continues in chat. They do not load removed result APIs or offer standalone acceptance/rejection. Existing saved tool-result formats remain readable with bounded search/paging; they do not reinstate the retired task workflow (OQ-154).

### 3.3 Agents
| Route | Access | Content |
|---|---|---|
| `/agents` | `agents:read` | Catalog grid/table: search, filters (status, visibility, owner, team), "New agent". `GET /api/v1/agents` |
| `/agents/new` | `agents:create` | Template picker (blank/assistant/researcher/analyst/support) or "Describe your agent" (`POST /api/v1/agents:draft-from-description`), slug/name form → `POST /api/v1/agents` → edit page |
| `/agents/[agentId]` | visible | Overview: persona, description, starter prompts, "Chat" button, versions (editors), where-used, usage summary (`GET /api/v1/usage/summary?agent_id=`) |
| `/agents/[agentId]/edit` | editors | **AgentBuilder** (§5) with tabs `?tab=instructions|model|tools|knowledge|skills|memory|subagents|sandbox|budget|channels|safety|yaml|versions|memory-review`, live **PreviewChat** pane (conversation pinned to the draft version), Validate / Publish / Disable buttons |
| `/agents/[agentId]/evals` | `evals:manage` / `evals:run` | Suites for the agent, cases editor, run history, comparison view (§4 of spec 18) |

### 3.4 Tools and connections
| Route | Access | Content |
|---|---|---|
| `/tools` | `tools:read` | Tool servers table (kind, status, owner, version, tool count, disabled), filters; flattened Tools tab (`GET /api/v1/tools`) |
| `/tools/new` | `tools:create` | Wizard: kind (Remote MCP / OpenAPI / SQL) → connection details (URL, auth mode, credential provider or secret; OpenAPI file upload + operation selection; SQL data connection selection or create) → discover → governance per tool (risk class, classification, preview template editor, timeouts) → submit for review |
| `/tools/[serverId]` | `tools:read` | Tabs: Overview, Versions (diff viewer of manifests), Tools (schemas, risk, test console `POST /api/v1/tools/{tool_id}:test`), Review (reviewers approve/reject with notes), Usage, Settings (kill switch, deprecate) |
| `/connections` | any | The user's credential connections (`GET /api/v1/connections`): connect (OAuth popup or API key dialog), revoke; `?provider=` highlights a provider (deep-link from chat "Connect") |

Connections groups Service credentials, Personal accounts and Database connections into tabs, with creation forms in disclosures. Lists reuse RecordList for bounded 25/50/100-row rendering, full-loaded-list name/type/reference search, returned/derived status filters and Clear filters. Personal connection status comes from the actual active grant; a derived index avoids scanning all grants for every rendered provider. An initial provider query opens Personal accounts and searches the returned catalogue without starting sign-in. These are UI rendering bounds, not transport pagination.

Sections request metadata only under the existing endpoint permissions: `connections:manage_own` for services, that permission plus `tools:read` for personal-provider metadata, and `tools:read` for databases. Database create/test additionally require `tools:create`. A failed section read exposes Retry, keeps the other successful sections available and never claims an empty catalogue. Initial loading precedes empty states. API authorisation remains authoritative.

Service test and secret rotation use inputs local to the selected saved row, independent from a new-connection draft. Cancel/success clears those inputs; replacement uses a password field and testing begins from that row's saved probe URL. OAuth service authorisation uses the existing authorize endpoint and only exposes a returned HTTP(S) sign-in address. Local expiry input serializes as an ISO instant with an offset. Database numeric inputs can be cleared, validate positive whole values and impose no upper caps absent from the existing contract. Existing save-then-test behaviour reports an acknowledged save separately from a failed test. All actions share one synchronous guard and abort their browser wait on unmount; late receipts cannot start a follow-up test. Refresh lists reads saved metadata without replaying writes.


### 3.5 Knowledge
| Route | Content |
|---|---|
| `/knowledge` | Collections grid (`GET /api/v1/knowledge/collections`), create dialog |
| `/knowledge/[collectionId]` | Tabs: Documents (table, upload dropzone → files API → `POST …/documents`), Sources (status, sync now, pause/resume, last job), Jobs (history with failures), Search playground (`POST /api/v1/knowledge/search` with debug scores), Settings (visibility, ACL mode, sensitivity, reindex) |
| `/knowledge/[collectionId]/sources/new` | Source wizard per kind with config form generated from `GET /api/v1/schemas/KnowledgeCollection`, secret picker, schedule (CronInput), "Test" (`:test`) |

Collection detail Documents, Sources and Jobs reuse the shared RecordList over the shared list pager: 25/50/100 rendered rows, search across returned names/status/type/references, returned-status filtering and Clear filters. Filtering precedes paging; empty lists and no matches are distinct. The existing search playground bounds returned passages and labels them with the submitted question; editing the next question does not relabel or reset the saved result page. Library-document and service-connection choices use the existing searchable ReferencePicker and their existing endpoints, loaded on opening with error/Retry and Cancel/focus restoration. Selector failures are not converted to empty lists. No selector reads are issued for read-only collection views. These are UI bounds; endpoint transport remains separate.

Collection navigation resets scoped drafts, results and selections and cancels reads/actions. Existing collection actions share one synchronous guard. A ready file receipt must include its actual ID before indexing. Read-only reload preserves existing controls and selected files, disables conflicting actions while loading and never replays a write. URL fields use native URL controls. On phones the file chooser and upload button occupy separate rows. Backend permissions, ingestion, search and persistence remain authoritative.


### 3.6 Routines
| Route | Content |
|---|---|
| `/routines` | Table: name, agent, trigger summary, status, last run, next run; filters |
| `/routines/new` | Optional query `conversation_id` + `message_id` (from the message action "Make this a routine") prefills agent and instructions. Form: agent, instructions (Markdown editor), trigger (schedule with CronInput + `POST /api/v1/routines:preview-schedule`; webhook shows URL+secret once after save; channel event; email; file arrival; db change; manual), event filter (JMESPath with sample tester), deliveries (with "pre-approve" toggle requiring permission), budget, concurrency |
| `/routines/[routineId]` | Overview + run history (`GET /api/v1/runs?routine_id=`), events log, "Run now"/"Test run", pause/resume, webhook secret rotation, transfer (admins) |

Routine detail events reuse the shared list pager: 25 rows initially, search across returned source/status/event/run references and timestamps, returned-status choices and explicit Clear filters. Filtering precedes paging; changing filters returns to page one. An empty recorded history stays distinct from a filter with no matches. These are loaded-list rendering bounds, not server transport pagination. Routine navigation resets scoped filters, action feedback and one-time secrets; reads/actions abort on unmount and duplicate action clicks share one synchronous guard. Upcoming routine instants, schedule previews and schedule activity use the same viewer-local date formatter with an explicit time-zone label. The saved cron/trigger time zone remains authoritative and unchanged.

Schedules create/run/pause/resume share one synchronous request guard. Progress names the action/target, then identifies read-only refresh after an acknowledgement. Creation needs a returned saved ID; Run now needs a returned run ID; pause/resume need the same saved ID and expected status. An unconfirmed receipt/refusal holds further mutations until both saved list and activity are read. Refresh never replays a POST and returns to the original known request target even if another row was inspected. An unavailable original target cannot be silently replaced by another schedule. Confirmed run links and acknowledgements survive a subsequent read failure; submitted creation drafts clear only after acknowledgement. Initial identity/catalogue failures remain recoverable through reads and do not enable creation prematurely. Navigation aborts pending list/activity/action reads and ignores late results.

Webhook credentials appear under the acknowledged schedule's name and can be explicitly hidden; selecting a different schedule clears that one-time receipt. The existing list and activity pagers have independent Clear filters controls; empty lists omit inactive filters. These are loaded-row rendering bounds, not server transport pagination.



### 3.7 Skills
`/skills` (catalog), `/skills/[skillId]` (Markdown editor with preview, assets manager (upload/delete), required tools picker, versions, where-used, publish, republish dependants).

### 3.8 Approvals
`/approvals` — tabs **To decide** (default), **Requested by me**, **All** (`approvals:read_all`); `/approvals/[approvalId]` — **ApprovalDetail**: preview fields, diff, arguments (JSON view, exact), model justification labelled "Agent's reason (unverified)", policy reasons, decisions so far, Approve/Reject with comment (session confirmation through `POST /api/v1/auth/step-up` when required), link to the conversation.

The queue offers quick decisions/selection only in To decide; Requested/All retain detail navigation without inactive selection controls. Before each quick decision, the existing detail endpoint must confirm pending status, eligibility, the same nonempty arguments hash and any session-confirmation requirement omitted by the summary contract. Individual and selected decisions share one synchronous, cancellable action path. A bulk rejection is sequential, stops at the first unconfirmed result and applies only matching receipts. Its confirmed count remains explicit; unfinished selection/comment survive for read-only recovery, without automatic replay. A quorum vote is remembered only within this mounted view; backend prior-vote eligibility remains OQ-167. Missing exact identity explains the held controls and detail/admin follow-up (OQ-169), rather than sending an empty guessed identity.

Queue refresh preserves successful rows and checks both requested lists. Failed writes hold further actions until read-only refresh succeeds; incomplete revocations cannot be labelled recorded. Acknowledged decisions/revocations remain visible if follow-up reads fail. Comment help identifies its scope, search/status clear together, standing expiry uses the shared viewer-zone formatter, and selection lookup/receipt application avoid scanning the entire selection for every loaded row or re-mapping the full catalogue per bulk receipt. Existing pagers bound returned queue/standing rows, with no claim of server transport at that scale.

Approval detail uses the API’s `canDecide` flag and exact returned `argsHash` before offering a decision. One synchronous request guard covers session confirmation and deciding; leaving the request aborts scoped reads/actions. Confirmation must explicitly return `steppedUp: true` (the current API also serialises it as `"true"`) before the protected request is sent. Progress distinguishes confirmation, the decision and the following metadata read. A matching decision receipt can remain pending when other reviewers are required; that reviewer’s recorded decision remains visible and cannot be submitted again within the same detail context. Missing/mismatched receipts hold further writes until a read-only refresh; accepted receipts survive a failed follow-up read. Backend duplicate-vote eligibility on reopening remains OQ-167. Policy reasons use loaded-list search and bounded paging, and Advanced JSON has a keyboard-accessible scroll frame. These presentation bounds do not establish transport pagination.

Reply acceptance uses the same acknowledged session-confirmation helper, scopes pending requests to the message/content hash, and stops a pending confirmation when chat becomes busy. It validates the returned accepted/in-review state and the exact content hash when one was supplied. An attempted save without a confirmed receipt holds further acceptance and offers the existing conversation reader as read-only recovery; no acceptance is replayed. The same-chat composer draft remains. A failed recovery read uses the existing chat error/retry state. Review timestamps use the shared viewer-local formatter with a time-zone label; absent/invalid times are explicitly unavailable. The API continues to own eligibility, content identity, quorum and persistence. Configured OTP/redirect completion is not established by this presentation change.

### 3.9 Runs
`/runs/[runId]` — **RunInspector**: header (status, agent/version, trigger, user, budget vs usage bars, duration, trace/langfuse links), timeline of steps (`/steps`), tool calls with redacted args/results and policy decisions (`/tool-calls`), child runs tree (`/children`), bounded raw event pages (SSE `GET /events`, `Last-Event-ID` cursor; page-local search/type filtering, lazy payload disclosure, explicit stop/retry for active reads), cancel button. Accessible from chat (step chip), routines, admin.

The current run inspector separates Activity, Subagents, Events and Graph. Search/type filters and the shared row pager bound activity, while subagents have independent search/status/paging. The graph is mounted only in its tab and represents the current filtered pages, as its visible explanation states. Run reference/status, returned agent/trigger/duration and usage appear above the tabs. A step budget bar appears only when both actual usage and a positive returned budget exist. Cancellation is available for an active run owned by the current person with `chat:use`; pending/error feedback remains local to that action. Each refresh finishes before the next live poll is scheduled; failed detail reads retain successful sections and expose retry. Navigation/retry aborts outdated reads. These presentation limits do not establish server-side pagination or 100,000-record transport.

### 3.10 Memory, files, settings
- `/memory`: the user's facts table (`GET /api/v1/memory`) with scope/agent filters, edit/delete, "Add memory", "Delete all"; toggle memory in profile.
- `/files`: the user's files (uploads/artifacts/exports) with previews, download, delete.
- `/settings/profile`: display name, locale, timezone, theme, memory toggle, linked channel identities (`/api/v1/me/channel-identities`, link via `?link=` token → `POST …:link`), personal API keys (`api_keys:manage_own`), data export (`GET /api/v1/me/export`).
- `/settings/notifications`: per-channel toggles.

The current Profile view separates personal usage from linked chat accounts so each has independent loading/error/refresh. Both loaded lists reuse RecordList search, returned-method/period filters and the shared bounded pager. Identity references/times are disclosed separately from the main account row; unlink controls name their target. A connect code is concealed, retains an ordinary form submission path and survives refused/unconfirmed links. A supplied link query is consumed into local form state and removed from the visible URL while preserving other query/hash state. Permission/ownership checks precede private link reads; explicit read-access failures clear stale accounts. A valid owned link receipt and saved-list verification are distinct; unlink success requires the saved row to be absent. Failed/unconfirmed actions hold further writes until a read-only refresh checks actual state, without replay or permanent assumptions about the desired result. Usage totals require returned metadata rather than invented zeros, currency-unset spend is explicit, cost limits use workspace-currency values and reset instants show the viewer's zone. These controls do not establish server-side large-list transport or configured channel linking. Friendly service labels need the existing personal projection enriched under OQ-171; do not substitute an admin read or infer vendors from ids.

Personal memory uses the existing scoped list and mutation endpoints with explicit submitted search (including its service-owned semantic search), scope/category filters, clear and bounded pages. A result label names its loaded query; stale results remain visible with context during refresh. Add/edit drafts survive reads and filters, and the editor is independent of row visibility with keyboard focus restoration. The personal toggle displays acknowledged storage, not an optimistic value. Create/edit/delete/preference receipts are validated before success; known recorded changes remain distinct from failed follow-up reads. Scoped synchronous guards, read permission checks, cancellation and read-only recovery prevent duplicate or replayed changes. Missing metadata does not become empty/enabled defaults, and explicit access loss removes protected data. The existing 500-character fact limit counts Unicode characters; receipt checks accept the service's documented whitespace normalization. Workspace facts are read-only in this personal view and the bulk deletion path is withheld under OQ-172 because the current service's selection includes workspace facts. This is a UI gate, not a repaired API authorisation policy or a transport-scale claim.

Advanced organisation-memory controls use the existing tenant settings reader/writer and distinguish the tenant's master memory permission from automatic remembering. Personal and agent settings may further restrict both. Saved preferences, drafts and confirmed-save feedback are separate. Only changed enabled/extraction/instruction fields are patched; unrelated or concurrently changed fields are not resent. A matching full saved-settings receipt is required before success. Refused/incomplete saves preserve edits and hold changes until read-only Refresh checks metadata without replay; Use saved settings is a local reset. Read/manage permissions gate private controls and explicit access failures remove stale data. Missing metadata never becomes an invented enabled/default state. Guidance supports the API's 2,000 Unicode-character limit with a visible count and invalid-state feedback. The organisation card mounts only after Advanced first opens and stays hidden/mounted across Simple switches to retain its draft. This UI does not establish successful live extraction/recall or override agent/personal policy.

### 3.11 Admin (`/admin/*`)
| Route | Permission | Content |
|---|---|---|
| `/admin/users` | `users:read` | Users table, invite, suspend, attributes editor, erase (step-up) |
| `/admin/teams` | `teams:manage` | Teams + members + leads |
| `/admin/roles` | `roles:manage` | System and custom roles (permission matrix editor), role assignments |
| `/admin/sso` | `tenant:manage` | Domains + verification, SCIM tokens (IdP federation removed with Keycloak, [OQ-122](../open-questions.md)) |
| `/admin/models` | `models:read` | Providers, models, aliases (incl. platform rows read-only), alias test console, kill switch |
| `/admin/policies` | `policies:read` | Policies list, rule editor (form + YAML), tests, simulate, activate; standing approvals |
| `/admin/channels` | `channels:manage` | Integrations, manifest download, test, identities |
| `/admin/sandboxes` | `sandboxes:manage` | Templates, live sandboxes |
| `/admin/secrets` | `secrets:manage` | Secrets (metadata), rotate; credential providers; data connections |
| `/admin/usage` | `usage:read` | Usage charts (recharts) by day/agent/user/model, CSV export, observability overview |
| `/admin/quotas` | `usage:read` | Quotas CRUD (`quotas:manage`) with current consumption |
| `/admin/audit` | `audit:read` | Audit search, event detail, verify chain, exports |
| `/admin/api-keys` | `service_accounts:manage` | Service accounts and their keys |
| `/admin/webhooks` | `webhooks:manage` | Webhooks, deliveries, redeliver, test |
| `/admin/evals` | `evals:manage` | Reusable suites (red team), feedback inbox (`GET /api/v1/feedback`) |
| `/admin/settings` | `tenant:manage` | Tenant settings (retention, egress allowlist, budget caps, features, branding, approvals, security, memory, SIEM) |
| `/admin/support-access` | `tenant:manage` (SaaS only) | Support-access grants: grant (step-up), list, revoke (`/api/v1/tenant/support-access`) |

The Quotas screen requires an explicit limit, distinguishes per-person from combined workspace scope and retains the existing named-target picker. Spend is entered/displayed in workspace currency units and converted exactly into the unchanged integer-micros wire contract. Warning/enforcement create overrides inherit the service default when unset; limit-only edits omit unchanged behavior. Read/action metadata, identity and acknowledgements are checked; missing counters/policy do not become zero/block/80. Known data and editable drafts survive transient failure, while further writes wait for read-only verification after unconfirmed actions. Removal names the rule, begins on Cancel and confirms absence in the saved list before reporting removal. Permission/plan restrictions stay enforced. Search/combined filters and bounded pages precede row rendering, processing is memoized, resets show returned zone-labelled instants, and the stacked-layout shortcut focuses the form. Currency/default-origin display metadata remains OQ-174; the UI does not infer a currency or policy from another rule. The existing model-price conversion is moved into the same shared exact decimal helper; unsupported precision/range is rejected rather than rounded or silently made zero. No new endpoint or wire unit is introduced.

Evaluation run history distinguishes initial/retained/error reads and clears protected state on account/workspace or permission changes. Saved-run details must match the selected identity/agent scope before case results are shown. Missing verdicts or list metadata never become failures or empty lists; fractional saved pass rates avoid whole-percent rounding. Verified ongoing runs refresh automatically only after successful reads; errors pause updates until manual refresh and retain explicitly stale known state. Browser waits abort on Close/unmount without cancelling the server run. History and result filters/page sizes use the shared bounded pager and Clear restores search focus/page one. Instants include the viewer zone; output is escaped and mounted only while its keyboard-scrollable disclosure is open. Closing the inspector returns focus without an extra history request.


View cases and Add case share one suite-scoped workspace over existing endpoints, using the same case validator/disclosure as Feedback. Search/check-type filters and bounded pages operate over actual saved inputs/checks; compact rows retain exact accessible identity and show details lazily. Text-case creation captures explicit message/contained-text/case-sensitivity, validates the acknowledgement and verifies saved name/input/assertion contents independently. Definite refusals recover through read-only checks without replay, while ambiguous creates remain held in the mounted editor. Known acknowledgements survive failed readback, input resets are explicit and Close remains reachable without promising rollback. Saved cases are not evaluation outcomes. The case, run-result and feedback dialog footers occupy separate layout space outside scrolling content so they cannot cover focused errors. Case defaults and opaque saved context remain service-owned; no prepared cases, generated contracts or backend behavior change is added.

The evaluation Feedback inbox uses independent refresh/retained read states, combined search/rating filters and bounded pages, zone-labelled dates and an actionable true-empty state. Copying requires a fresh session/source-chat/message check, explicit destination and the existing evaluation owner/broad-reader eligibility hint. A returned case acknowledgement is distinct from saved name/input/assertion readback; unknown requests stay held for that destination in the mounted view and are never replayed by refresh. Saved assertions are inspectable as escaped lazy text, with lexical overlap labelled not judged. Closing aborts the browser wait without undoing a sent request. OQ-175 records the owning source-access/branch/provenance/idempotency gaps; no backend fix or cross-reload retry guarantee is claimed.

The current Computers page separates saved starting templates from existing instances, with independent read states, retained successful data and shared bounded search/filter/paging. Missing metadata is an error, not an empty list. Template creation uses service defaults for unset CPU, memory and package policy; Advanced allows positive whole resource overrides and explicit default/allow/block package choices. Switching modes preserves drafts and indicates hidden overrides. Slugs normalize to lowercase under the existing service rule. A matching saved receipt is separate from list verification; refused/unconfirmed actions keep editable drafts and hold further writes until read-only refresh checks saved state without replay. Stop controls require the existing route permission and a non-terminal instance, name the exact id, and open a focus-managed confirmation describing workspace/snapshot removal. A stacked-layout create shortcut focuses the template form; recorded instance errors are disclosed lazily as escaped text. The selected target remains independent from list filters; only a matching terminal receipt confirms completion. Requests are scoped/cancellable, and explicit access loss clears protected views. Browser cancellation is not a rollback guarantee. These controls do not certify durable template history (OQ-173), actual stop/save execution or server-scale transport.

The current Users screen is a read-only directory over the existing users projection. It checks `users:read` before requesting private rows, exposes independent Refresh/Retry, retains the last confirmed list through transient failure and clears it on explicit access loss. Name/email search and a filter built from returned account statuses run before the shared bounded pager. Status and recorded last-sign-in instants appear in the table; null sign-in metadata means no recorded sign-in, not proof of never signing in. Instants include the viewer's zone, and the phone table has a named keyboard-scrollable frame with a sideways-scroll hint. Invalid/missing metadata is an error rather than an invented empty list. Role assignments are not inferred from the current projection. This directory does not implement the invite/suspend/attributes/erase controls described in the target route table, or establish server-side pagination/100,000-record transport.

The Models registry groups returned model metadata under providers with search by provider/model/upstream identifier and a model-type filter. Provider groups, expanded model rows and additional aliases use the shared pager; model rows mount on disclosure expansion. A single matching provider starts expanded. Additional aliases can be searched by alias or assigned model. Filtering precedes client paging, and clearing filters returns to page one. Detailed setup instructions live within Add a provider, initially open for an empty provider catalogue. Model defaults and alias editing reuse the shared searchable/paged picker over the metadata already loaded by the page. Provider context and upstream identifiers disambiguate choices. A default choice keeps its existing immediate-save behaviour; an alias-editor choice remains a draft until Save. Standard alias type/capability requirements are read from the existing metadata for both creation and editing, and an unavailable current assignment remains visible. The picker returns focus to its trigger and aborts stale metadata reads. These are UI bounds; existing endpoint transport and other agent/alias selection surfaces require their own scale proof.

The Usage screen distinguishes applied reporting filters from unsaved date/group drafts. Date controls validate their order; Apply and Use default range perform explicit reads. A retained report keeps its loaded-filter context when a subsequent read fails. Quantity/cost totals require returned metadata, and absent currency is explicit. Returned groups use local search and the shared bounded pager; the quantity chart follows that same page while report totals cover the full applied range. CSV export uses the applied report filters independently of list search/page, checks HTTP status and CSV content type, preserves the returned bytes and exposes shared error guidance instead of downloading an error response. Reads/downloads are scoped and cancellable; explicit permission loss clears private views. Operations has independent loading/retry and is explicitly all-time, matching its existing unfiltered endpoint; failure is not reported as zero. These presentation limits do not establish server pagination or large-record transport.

### 3.12 Platform (`/platform/*`, realm role `platform_admin`)
`/platform/tenants` (list, create, suspend/resume/delete), `/platform/models` (platform providers/models/aliases), `/platform/plans` (plans + limits), `/platform/health` (`GET /api/v1/platform/health`, platform usage).

### 3.13 Widget
`/widget/[integrationId]`: minimal chat (Composer + ChatThread) for the integration's agents after `POST /api/v1/widget/sessions`.

The existing widget renderer bounds saved-message DOM with the shared pager (25 messages per page). Page 1 contains the newest messages; each page reads chronologically, with Older/Newer and a return-to-latest action. Small conversations show no pager. This is a presentation bound, not server-side history pagination. Upload/reload progress disables conflicting actions, and only returned ready uploads become attachments. Integration navigation resets local chat identity/draft state; reauthentication clears the previous session's draft/files on success. Missing integration policy has actionable unavailable guidance and retry. The existing parent/origin/nonce/session/CSRF protocol remains authoritative. File previews/downloads remain uncertified pending the restricted read contract in OQ-165.


## 4. Chat components (normative behaviour)

| Component | Behaviour |
|---|---|
| `ChatThread` | Virtualised (TanStack Virtual) list of `MessageItem`s for the active branch; auto-scroll when at bottom; "Jump to latest" button; loads older pages on scroll top. |
| `MessageItem` | Renders `ContentPart[]`: Markdown text (GFM, code blocks with shiki highlighting + copy, Mermaid diagrams rendered client-side with `securityLevel: 'strict'`, KaTeX math), `file` parts as `ArtifactCard`, citation indexes preserved in a compact Sources action with searchable/paged previews (title, snippet, page/anchor and document link); branch switcher `< 2/3 >` when siblings exist; actions: copy, regenerate (assistant), edit (user), feedback (👍/👎 with reasons dialog), "Inspect run". |
| `StreamingMessage` | Shows live text from `useRunStreams`, a blinking caret, `reasoning.delta` in a collapsible "Thinking" section when enabled. |
| `RunActivity` | Compact, collapsible timeline per run between user and assistant message: steps, `ToolCallCard`s (name, risk badge, args preview, status, duration, expandable result preview), `SubagentCard` (nested timeline loaded lazily), memory recalled/saved chips, compaction notice, warnings. |
| `ApprovalCard` | Inline in the thread for `tool_call.approval_required` when the viewer is eligible: preview, Approve/Reject (calls `:decide` with `args_hash`), otherwise "Waiting for approval by …". Updates on `approval_resolved`. |
| `InputRequestCard` | For `input.required`: form generated from `requested_schema` (zod from JSON Schema subset: string, number, integer, boolean, enum, required), Accept/Decline → `POST /api/v1/runs/{run_id}:input`. |
| `ConnectCard` | For `tool_call.failed` with `connect_url`: "Connect <provider>" opens `/connections?provider=…` in a popup; on success the user can click "Retry" which posts "Connected, please continue." |
| `Composer` | Textarea with Markdown shortcuts, Enter to send / Shift+Enter newline, attachments (drag/drop/paste; uploads via files API with progress; image thumbnails), slash commands (`/new`, `/agent <slug>`), stop button while a run is active, per-conversation draft persistence (`useComposerDrafts`, localStorage), character counter near limit. Disabled with tooltip when `run_in_progress` and the user did not choose "Interrupt". |
| `WorkspacePanel` | Tabs: **Plan** (`plan.updated`), **Files** (conversation files + artifacts, preview viewers for image/PDF/CSV/XLSX/MD/code), **Computer** (sandbox status, file tree via `/api/v1/sandboxes/{sandbox_id}/files`, terminal-like log of `sandbox.output` events, latest `browser.screenshot` with URL bar), **Sources** (all citations of the conversation). |
| `AgentHeader` | Agent avatar/name/version badge (draft badge in preview), disabled banner, memory indicator. |

## 5. AgentBuilder

- Form state: react-hook-form with zod schema generated from the `AgentDefinition` JSON Schema (`GET /api/v1/schemas/Agent`, codegen at build time into `@ar/api-client/schemas`); autosave of the draft (`PUT /api/v1/agents/{agent_id}/versions/draft` with `If-Match`) debounced 1.5 s; conflict (412) shows a merge dialog (reload theirs / overwrite).
- Tabs map 1:1 to definition sections; **Tools** tab: ToolPicker grouped by server with risk badges and per-tool overrides (require approval always, pinned); **YAML** tab: Monaco editor with schema validation (two-way sync with the form); **Versions**: list, diff (YAML diff), rollback.
- Validation panel shows `:validate` errors/warnings with links to fields.
- Publish dialog: change note, shows eval gate status, warnings (W3 tools, high risk tier needs second person).
- PreviewChat: same chat components, conversation created with `agent_version_id = draft id`; "Reset preview" creates a new conversation.

### 5.1 Natural-language builder

`/agents/new` opens on a single field. The placeholder is a complete instruction ("create an agent that reviews vendor SOC 2 reports and flags gaps"). Submit calls `POST /api/v1/builder/sessions` and streams the builder's reply beside a preview card. The card shows persona, tools, knowledge, policies, and routines from `proposal`, plus validation warnings. The user either sends a refinement ("add a weekly routine and require approval before email") or chooses **Edit in form** or **Edit as YAML**, which calls `:apply` and opens §5 on the draft. Template cards are below the field, not above it. Specified in [spec 05 §11](05-agent-registry.md#11-natural-language-builder). Plan: M3-T10.

## 6. State management rules

- Server state: TanStack Query only; no copies of server data in zustand.
- Stream state: `useRunStreams` keyed by run id: `{status, messages, toolCalls, approvals, inputRequests, subagents, plan, usage, lastSeq}`; cleared 5 min after a terminal event when no component subscribes; on terminal event the conversation messages query is invalidated so persisted messages replace streamed ones.
- URL state: nuqs for filters, tabs, and selected items (shareable links).
- Forms: react-hook-form + zod; server validation errors (`errors[].loc`) mapped to fields.

## 7. Performance budgets (web)

LCP < 2.0 s on `/chat` (cold, desktop, 4G fast), INP < 200 ms, JS ≤ 250 KB gzip for the `(app)` shell route, streaming render at 60 fps for 100 tokens/s (coalesced updates via `requestAnimationFrame`). Monaco, Mermaid, React Flow, recharts loaded with `next/dynamic` only on pages that need them. Details: [performance-budgets](../08-quality/performance-budgets.md).

## 8. Configuration

| Variable | Default | Purpose |
|---|---|---|
| `AR_PUBLIC_URL` | `http://localhost:3000` | Canonical URL |
| `AR_API_INTERNAL_URL` | `http://localhost:8000` | Server-side session fetch and dev rewrites |
| `AR_SESSION_GATE_TTL_S` | `15` | How long a confirmed session satisfies the web gate without another API call. `0` confirms on every real navigation. Prefetches still do not start a call |
| `NEXT_PUBLIC_AR_BUILD_SHA` | from CI | Shown in About |

## 9. Test plan

- Unit/component (vitest + Testing Library + msw): reducer for every stream event type (fixture streams from `packages/api-client/fixtures/streams/*.jsonl`), Composer behaviours, ApprovalCard decisions, form schema mapping, permission guards.
- Storybook for all `components/chat`, `components/common` with interaction tests.
- E2E (Playwright, full stack via `make test-e2e` with the test model server): login (password form), create agent from template, publish, chat with streaming, attach file, tool call with approval, knowledge upload + cited answer, routine test run, admin creates policy and sees approval required, accessibility checks (axe) on every page, visual snapshots of key pages (light/dark).

## 10. Records, reviews and guest routes

Core guest entry at `/guest` separates Request a link and Use a link into keyboard-accessible panes. The former asks for the invited email and does not claim to create an account; the latter collects the link token and optional authenticator code. Values survive pane switches, task-specific notices/errors do not, and pending requests disable conflicting controls. A successful request response is not an email-delivery or content-access guarantee. The legacy core `/guest/portal` address shows shared-content-unavailable guidance, asks the person to use the host's original content link and offers keyboard-accessible return to `/guest`. It makes no catalogue/content read and does not infer whether the person has guest grants. The installed-pack catalogue is never rendered as granted records. Pack content, grant validity and downloads remain uncertified under OQ-161; the entry UI must not invent granted content or bypass the owning pack's authentication/read contract.


Added by M5-T08, M7-T11, M13-T07 and M14. Each page has loading, empty and error states and is permission-gated.

| Route | Permission | Contents |
|---|---|---|
| `/reviews` | `reviews:read` or a pending item | Queue tabs **To decide**, **Prepared by me**, **All** |
| `/reviews/[reviewItemId]` | object-level | Statement, content hash, chain, decide or delegate, step-up when required |
| `/admin/evidence` | `evidence:read` | Evidence table, verify action, custody drawer |
| `/admin/legal-holds` | `holds:manage` | Matters, scope, release (step-up) |
| `/admin/retention` | `retention:manage` | Schedule editor |
| `/admin/ai-governance` | `ai_governance:read` | Agent cards, oversight, incidents |
| `/admin/guests` | `guests:manage` | Invitations, grants, revoke |
| `/admin/binders` | `binders:export` | Selection, build, download |
| `/admin/content-packs` | `packs:manage` | Install, upgrade, uninstall |
| `/guest/login` | public | Magic link and TOTP |
| `/guest/portal` | public guide | Unavailable-address guidance and return to guest access; granted content belongs to the owning signed pack |

The run inspector (`/runs/[runId]`) gains a **Record** tab (`run_records:read`) and the chat citation drawer gains a **Why** panel bound to `GET .../messages/{message_id}/grounding`. Pack routes render only when `GET /api/v1/tenant/packs` lists that pack as enabled ([spec 21 §6](21-records-governance.md#6-pack-extension-points)).

AppShell's main is a positioned scrolling boundary. Visually hidden labels and other absolute descendants must stay contained within it; a fixed-frame workspace page must not create document-level blank overflow. Shared picker dialogs use real triggers for focus restoration and the existing portal for overlays.

Reply-acceptance settings on Reviews retain the original tenant/queue endpoints. Only message queues are selectable through the shared searchable, paged reference picker; Off is an explicit choice. Saved configuration, unavailable saved identity and unsaved selection are distinct. Unchanged or unavailable choices cannot be saved; Use saved setting discards only the local draft. Private reads require tenant-read and review-read permissions; the editor additionally requires tenant-manage. Missing metadata does not become Off. Reads/writes are scoped and guarded against duplicate/late completion, and explicit access failures remove stale controls. A matching returned saved setting is required before showing success. Refused/incomplete acknowledgements preserve selection and hold further changes until read-only Refresh checks saved metadata, without replaying the PATCH. Diagnostics use the shared error guidance; mutation errors receive focus. These UI bounds do not establish server pagination or configured live review/signing.

## 11. Presentation quality bar

Every page this spec names meets [ux-quality](../08-quality/ux-quality.md): skeleton loading, empty state with one next action, plain-language error with retry, light and dark, 375 px and 1280 px, axe clean, keyboard access. Onboarding after first login is the natural-language field in §5.1, not a settings form.

The shared DetailState/ErrorState presentation accepts the original API error as well as local text. Chat, policy/privacy settings, approval actions and model administration retain API metadata for this presentation. Known verification, authentication, throttling and service errors show a translated next step first; original status/code/message remain behind a keyboard-accessible Technical details disclosure with bounded scroll. A replacement error collapses prior diagnostics. Business permission/validation messages and local errors keep their own wording; text is never used to guess an error code. Disclosure performs no requests, changes no session/security policy and does not replay a mutation. Model probe request failures are incomplete tests, separate from actual returned model results. Model-default status cells reserve room for long attention badges beside their action controls.

## 12. Simple and advanced settings

`/admin/settings` and `/settings/profile` have a mode switch, remembered per user.

- **Simple** shows plain-language choices that map to one or more settings (for example "Keep deleted chats for" with a few durations). Saving writes the documented defaults for every field the screen does not show.
- **Advanced** shows every field and a raw JSON editor for `tenants.settings` (tenant admin) or the agent definition (builder). Raw JSON uses camelCase. Invalid JSON does not save.

A pack settings link from `spec.extension.ui.settings` uses the same two modes against that pack's `configSchema`. Properties with `x-ar-simple: true` are the Simple set.

Policy settings separates Tool rules, Website access and Data masking into keyboard-accessible tabs. The existing panels remain mounted but inactive panels are hidden, preserving unsaved values across tab changes. Simple/Advanced remains page-wide; a supplied Advanced JSON document disables the replaced simple rule controls and must be a JSON object before submission. The tool check explicitly uses the active saved rules and empty arguments, and its result/error names the checked tool without changing the draft.

Policy creation, simulation and activation share one synchronous scoped request guard. Reads/actions abort on unmount. Creation requires a saved draft identity; activation requires the returned version metadata (never a guessed version), explicit session-confirmation acknowledgement, and a matching active-version receipt. A refused/incomplete save preserves the draft and holds further policy writes until read-only Refresh policies checks the saved catalogue and any known target. Acknowledged saves clear only submitted unchanged fields and survive follow-up read failure. Local JSON and checker failures remain separate from list errors. Filters clear together and the existing pager bounds returned metadata; the service’s fixed catalogue/rule limits and unpaged transport remain OQ-168.

Website access and masking each keep scoped reads/writes and explicit saved-response validation. Missing metadata is an error, not an empty/default configuration; tenant read permission is checked before private reads. Explicit authentication/access/not-found failures remove stale protected controls. Refused/unconfirmed writes retain drafts and hold further changes until read-only refresh succeeds, without replay. Saved notices describe recorded configuration, rather than certifying network reachability or the next model/tool execution. Operation status stays near the form actions; mutation errors and differing effective masking receive focus so long forms cannot hide feedback. New edits clear old saved feedback.

Website-host search/paging operates over unique returned allowlist membership while preserving the API list in writes. Masking kinds are grouped by returned detection method, including unknown methods, with whole-loaded-list search and shared bounded pages. Choices survive paging/filtering. Confidence accepts the API’s full 0–1 precision: an explicit edit chooses a fixed value and clearing sends null. Unchanged privacy fields are omitted, preserving default-following and unrepresented settings; Simple saves only the switch and retains hidden Advanced drafts. Refresh keeps unacknowledged drafts, while Use saved values explicitly restores the last confirmed view without writing. A valid save receipt survives failed effective-state reads, and a differing effective projection is distinct from failed persistence. Reset names only the list/confidence it changes; exclusions remain honoured pending OQ-170. These controls do not establish large-setting transport or positive execution proof.

### Run inspector presentation consistency

Chat’s compact run facts and the full inspector share `useRunInspection`. Primary metadata remains visible when a step/tool/child read fails; those sections expose their own error/retry instead of claiming an empty result. Reads are aborted on navigation/retry, polls wait for the current reads and stop on terminal status or failure, and cancellation pauses reads before using the saved response. Chat waits for the reply to settle before background polling, keeps tool search/status controls in a compact disclosure, bounds tool rows, and keeps View trace near the header.

The full inspector reuses the chat `ToolCallCard` for returned redacted arguments, results and failure messages. Collapsed cards do not mount result content. Query/table/pivot/sample rows use the shared searchable pager and keyboard-accessible table frame; this bounds rendering without claiming API transport at that size. Structured values render as JSON instead of JavaScript object labels. The reading note supports the existing producer’s used-tool names, preserves supplied legacy reading-plan fields and omits absent fields rather than filling a sentence with blanks. No public API or content-part contract is changed.
