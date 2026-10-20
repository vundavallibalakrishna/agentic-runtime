# Spec 19: Web app (`web`)

Deployable `web` (`apps/web`, package `@ar/web`, port 3000): Next.js 16 App Router, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query 5, zustand (stream state), nuqs (URL state), react-hook-form + zod, `@ar/api-client` (generated from the `api` OpenAPI by hey-api). The web app is a thin client of the BFF (`api`): it never holds tokens; auth is the `ar_session` HttpOnly cookie + `ar_csrf` double-submit header. PRD: all feature files in [01-prd](../01-prd/README.md). Conventions: [coding-standards-typescript](../08-quality/coding-standards-typescript.md).

## 1. Architecture

- **Routing/rendering**: App Router with route groups `(auth)`, `(app)`, `(admin)`, `(platform)`, `widget`. Pages are React Server Components only for the shell/layout and static parts; data-heavy views are client components using TanStack Query. No server-side data fetching with user credentials except `GET /api/v1/auth/session` in the root layout (forwarding the cookie) to decide redirects and render the shell.
- **API access**: same-origin. In production the ingress routes `/api/*`, `/scim/*`, `/channels/*` to their services and everything else to `web`. In dev, `next.config.ts` rewrites `/api/:path*` → `http://localhost:8000/api/:path*`.
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

### 3.1 Auth
| Route | Purpose | API |
|---|---|---|
| `/login` | Tenant discovery by email domain or slug, then redirect to `GET /api/v1/auth/login?tenant=…&return_to=…` (Keycloak). Shows SSO buttons per tenant IdPs. | `GET /api/v1/meta` (branding, self-signup flag) |
| `/select-tenant` | For users in multiple tenants (platform admins) | `GET /api/v1/auth/session`, `POST /api/v1/auth/switch-tenant` |
| `/invite/[token]` | Accept invitation → login | `POST /api/v1/invitations/{token}:accept` |
| `/suspended` | Tenant suspended notice | – |

### 3.2 Chat (`/chat`, `/chat/[conversationId]`) — `chat:use`
Layout: left **ConversationList** (search `q`, filters agent/pinned/shared; infinite scroll; actions rename/pin/archive/delete/share), center **ChatThread**, right collapsible **WorkspacePanel** (tabs: Plan, Files, Computer, Sources).
- `/chat`: **AgentPicker** (usable agents, starter prompts of the selected agent) + **Composer**; first send calls `POST /api/v1/conversations` with `message` then `router.replace('/chat/{id}')`.
- `/chat/[conversationId]`: `GET /api/v1/conversations/{conversation_id}`, `GET …/messages` (paged upwards), `useConversationStream(id)` live; posting `POST …/messages`; regenerate/edit/activate branch; cancel (`POST /api/v1/runs/{run_id}:cancel`); feedback; share dialog (`…/shares`); export (`…/export`).
- URL state: `?run=` (focus a run in the Run drawer), `?panel=files|computer|plan|sources`.

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

### 3.5 Knowledge
| Route | Content |
|---|---|
| `/knowledge` | Collections grid (`GET /api/v1/knowledge/collections`), create dialog |
| `/knowledge/[collectionId]` | Tabs: Documents (table, upload dropzone → files API → `POST …/documents`), Sources (status, sync now, pause/resume, last job), Jobs (history with failures), Search playground (`POST /api/v1/knowledge/search` with debug scores), Settings (visibility, ACL mode, sensitivity, reindex) |
| `/knowledge/[collectionId]/sources/new` | Source wizard per kind with config form generated from `GET /api/v1/schemas/KnowledgeCollection`, secret picker, schedule (CronInput), "Test" (`:test`) |

### 3.6 Routines
| Route | Content |
|---|---|
| `/routines` | Table: name, agent, trigger summary, status, last run, next run; filters |
| `/routines/new` | Optional query `conversation_id` + `message_id` (from the message action "Make this a routine") prefills agent and instructions. Form: agent, instructions (Markdown editor), trigger (schedule with CronInput + `POST /api/v1/routines:preview-schedule`; webhook shows URL+secret once after save; channel event; email; file arrival; db change; manual), event filter (JMESPath with sample tester), deliveries (with "pre-approve" toggle requiring permission), budget, concurrency |
| `/routines/[routineId]` | Overview + run history (`GET /api/v1/runs?routine_id=`), events log, "Run now"/"Test run", pause/resume, webhook secret rotation, transfer (admins) |

### 3.7 Skills
`/skills` (catalog), `/skills/[skillId]` (Markdown editor with preview, assets manager (upload/delete), required tools picker, versions, where-used, publish, republish dependants).

### 3.8 Approvals
`/approvals` — tabs **To decide** (default), **Requested by me**, **All** (`approvals:read_all`); `/approvals/[approvalId]` — **ApprovalDetail**: preview fields, diff, arguments (JSON view, exact), model justification labelled "Agent's reason (unverified)", policy reasons, decisions so far, Approve/Reject with comment (step-up prompt if required: opens `POST /api/v1/auth/step-up` flow in a popup), link to the conversation.

### 3.9 Runs
`/runs/[runId]` — **RunInspector**: header (status, agent/version, trigger, user, budget vs usage bars, duration, trace/langfuse links), timeline of steps (`/steps`), tool calls with redacted args/results and policy decisions (`/tool-calls`), child runs tree (`/children`), raw events table (`/events?Accept=json`), cancel button. Accessible from chat (step chip), routines, admin.

### 3.10 Memory, files, settings
- `/memory`: the user's facts table (`GET /api/v1/memory`) with scope/agent filters, edit/delete, "Add memory", "Delete all"; toggle memory in profile.
- `/files`: the user's files (uploads/artifacts/exports) with previews, download, delete.
- `/settings/profile`: display name, locale, timezone, theme, memory toggle, linked channel identities (`/api/v1/me/channel-identities`, link via `?link=` token → `POST …:link`), personal API keys (`api_keys:manage_own`), data export (`GET /api/v1/me/export`).
- `/settings/notifications`: per-channel toggles.

### 3.11 Admin (`/admin/*`)
| Route | Permission | Content |
|---|---|---|
| `/admin/users` | `users:read` | Users table, invite, suspend, attributes editor, erase (step-up) |
| `/admin/teams` | `teams:manage` | Teams + members + leads |
| `/admin/roles` | `roles:manage` | System and custom roles (permission matrix editor), role assignments |
| `/admin/sso` | `tenant:manage` | IdPs (OIDC/SAML), domains + verification, SCIM tokens |
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

### 3.12 Platform (`/platform/*`, realm role `platform_admin`)
`/platform/tenants` (list, create, suspend/resume/delete), `/platform/models` (platform providers/models/aliases), `/platform/plans` (plans + limits), `/platform/health` (`GET /api/v1/platform/health`, platform usage).

### 3.13 Widget
`/widget/[integrationId]`: minimal chat (Composer + ChatThread) for the integration's agents after `POST /api/v1/widget/sessions`.

## 4. Chat components (normative behaviour)

| Component | Behaviour |
|---|---|
| `ChatThread` | Virtualised (TanStack Virtual) list of `MessageItem`s for the active branch; auto-scroll when at bottom; "Jump to latest" button; loads older pages on scroll top. |
| `MessageItem` | Renders `ContentPart[]`: Markdown text (GFM, code blocks with shiki highlighting + copy, Mermaid diagrams rendered client-side with `securityLevel: 'strict'`, KaTeX math), `file` parts as `ArtifactCard`, citations as superscript `[n]` with hover cards (title, snippet, open link); branch switcher `< 2/3 >` when siblings exist; actions: copy, regenerate (assistant), edit (user), feedback (👍/👎 with reasons dialog), "Inspect run". |
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
| `NEXT_PUBLIC_AR_BUILD_SHA` | from CI | Shown in About |

## 9. Test plan

- Unit/component (vitest + Testing Library + msw): reducer for every stream event type (fixture streams from `packages/api-client/fixtures/streams/*.jsonl`), Composer behaviours, ApprovalCard decisions, form schema mapping, permission guards.
- Storybook for all `components/chat`, `components/common` with interaction tests.
- E2E (Playwright, full stack via `make test-e2e` with `fake-llm`): login (Keycloak test realm), create agent from template, publish, chat with streaming, attach file, tool call with approval, knowledge upload + cited answer, routine test run, admin creates policy and sees approval required, accessibility checks (axe) on every page, visual snapshots of key pages (light/dark).

## 10. Records, reviews and guest routes

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
| `/guest/portal` | guest session | Granted evidence and binders only |

The run inspector (`/runs/[runId]`) gains a **Record** tab (`run_records:read`) and the chat citation drawer gains a **Why** panel bound to `GET .../messages/{message_id}/grounding`. Pack routes render only when `GET /api/v1/tenant/packs` lists that pack as enabled ([spec 21 §6](21-records-governance.md#6-pack-extension-points)).

## 11. Presentation quality bar

Every page this spec names meets [ux-quality](../08-quality/ux-quality.md): skeleton loading, empty state with one next action, plain-language error with retry, light and dark, 375 px and 1280 px, axe clean, keyboard access. Onboarding after first login is the natural-language field in §5.1, not a settings form.

## 12. Simple and advanced settings

`/admin/settings` and `/settings/profile` have a mode switch, remembered per user.

- **Simple** shows plain-language choices that map to one or more settings (for example "Keep deleted chats for" with a few durations). Saving writes the documented defaults for every field the screen does not show.
- **Advanced** shows every field and a raw JSON editor for `tenants.settings` (tenant admin) or the agent definition (builder). Raw JSON uses camelCase. Invalid JSON does not save.

A pack settings link from `spec.extension.ui.settings` uses the same two modes against that pack's `configSchema`. Properties with `x-ar-simple: true` are the Simple set.
