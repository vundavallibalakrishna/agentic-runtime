# M11 — Channels

Goal: agents where people work. The same agents answer in Slack and Microsoft Teams threads (with streaming updates, files, citations, approval and input cards), reply to email, are callable through an OpenAI-compatible endpoint, and embed in internal web apps through a widget.

Exit criteria: with Slack and Teams test doubles (and a real Slack workspace in the manual release checklist), a user mentions the agent, receives a streamed answer in the thread, an approver approves a W2 call from a Slack button, and a routine from M10 delivers to a Slack channel; an OpenAI SDK client streams from `/api/v1/openai/chat/completions`.

---

### M11-T01 · Revision 0018 `channels` and integration management API
- **Depends on:** M10-T04
- **Areas:** `ar_domain/channels/**`, migration 0018, `ar_api/routers/{channel_integrations.py,me_channel_identities.py}`
- **Spec:** [spec 16 §5](../03-specs/16-channels.md#5-integration-management-api-served-by-api), [schema §14](../04-data/schema.md#14-channels-ar_domainchannels)
- **Do:** Tables of schema §14; `GET/POST /api/v1/channel-integrations`, `GET/PATCH/DELETE /api/v1/channel-integrations/{integration_id}`, `POST /api/v1/channel-integrations/{integration_id}:test`, `GET /api/v1/channel-integrations/{integration_id}/manifest` (Slack YAML manifest, Teams app zip), `GET /api/v1/channel-integrations/{integration_id}/identities`, `DELETE /api/v1/channel-integrations/{integration_id}/identities/{identity_id}`; `GET /api/v1/me/channel-identities`, `POST /api/v1/me/channel-identities:link` (link code, `AR_CHANNEL_LINK_TTL_S`), `DELETE /api/v1/me/channel-identities/{identity_id}`; plan features `teams_channel`, `email_channel`, `widget`; `channel_integration.updated` event.
- **Done when:** bot credentials are stored only as secrets; manifest endpoints produce importable artefacts.
- **Tests:** integration per endpoint; manifest snapshot tests.

### M11-T02 · `channels` service core and internal endpoints
- **Depends on:** M11-T01
- **Areas:** `services/channels/src/ar_channels/{main.py,registry.py,inbound.py,streaming.py,render/{markdown.py,slack.py,teams.py,email.py},internal_routes.py}`, `ar_api/internal/{channels_inbound.py,channels_approvals.py,channels_integrations.py}`, `ar_domain/channels/service.py`
- **Spec:** [spec 16 §1, §3–4, §8–9](../03-specs/16-channels.md#3-inbound-processing), [internal-apis §6, §8](../05-contracts/internal-apis.md#8-channels-internal-endpoints-base-httpchannels8004)
- **Do:** Integration registry loaded from `GET /internal/v1/channels/integrations` (reload on `ar:invalidate:channel_integration:*` and `POST /internal/v1/integrations:reload`); `api` internal endpoints `POST /internal/v1/channels/inbound` (`handle_inbound`: identity resolution, agent routing, `channel_threads`, file download via `GET /internal/v1/files/{download_ref}`, post message), `POST /internal/v1/channels/approval-decisions`; channels internal endpoints `POST /internal/v1/outbound`, `POST /internal/v1/notify`, `POST /internal/v1/integrations/{integration_id}:test`; reply streaming from `ar:run:{run_id}:events` with throttled updates; Valkey dedupe of inbound event ids; leader locks.
- **Done when:** a fake adapter (in-memory) passes the full inbound → stream → final reply cycle; unknown users get a link prompt.
- **Tests:** integration with fake adapter; identity resolution matrix; dedupe test.

### M11-T03 · Slack adapter
- **Depends on:** M11-T02
- **Areas:** `ar_channels/adapters/slack/**`
- **Spec:** [spec 16 §2–4](../03-specs/16-channels.md#2-public-endpoints-on-channels-ingress-path-prefix-channels), [request-flows §8](../02-architecture/request-flows.md#8-slack-message)
- **Do:** `POST /channels/slack/events`, `POST /channels/slack/interactions`, `POST /channels/slack/commands` (signature verification, 3 s ack), Socket Mode per integration on the leader replica; mrkdwn rendering and message splitting; files upload; approval buttons (eligible approvers only; W3 → "Open in web" for step-up); input modals from `requested_schema`; connect-account buttons; `channel_event` forwarding for routines.
- **Done when:** recorded Slack payload fixtures produce the expected API calls (asserted against a fake Slack Web API server).
- **Tests:** contract tests with fixtures; signature tests; approval-button flow integration.

### M11-T04 · Microsoft Teams adapter
- **Depends on:** M11-T02
- **Areas:** `ar_channels/adapters/teams/**`
- **Spec:** [spec 16 §2–4](../03-specs/16-channels.md#4-reply-streaming)
- **Do:** `POST /channels/teams/messages` using the Microsoft 365 Agents SDK (JWT validation of Bot Framework tokens), personal/channel/group chats, typing + `updateActivity` streaming, Adaptive Cards for final answers, approvals and inputs, attachments as web links (v1).
- **Done when:** recorded activity fixtures produce the expected outgoing activities against a fake connector service.
- **Tests:** contract tests; token validation tests.

### M11-T05 · Email channel
- **Depends on:** M11-T02
- **Areas:** `ar_channels/adapters/email/**`
- **Spec:** [spec 16 §3–4](../03-specs/16-channels.md#3-inbound-processing)
- **Do:** IMAP polling (`AR_CHANNELS_EMAIL_POLL_S`), SPF/DKIM `Authentication-Results` check against verified tenant domains, thread mapping by `References`/`In-Reply-To`, replies via SMTP with sanitised HTML and attachments, `email` routine trigger forwarding.
- **Done when:** a GreenMail round trip (send → agent reply in the same thread) passes.
- **Tests:** integration with GreenMail container; spoofed sender rejected.

### M11-T06 · OpenAI-compatible API and widget
- **Depends on:** M11-T02
- **Areas:** `ar_api/routers/{openai_compat.py,widget.py}`, `apps/web/src/app/widget/[integrationId]/**`, `apps/web/public/widget.js`
- **Spec:** [spec 16 §6–7](../03-specs/16-channels.md#6-api-channel)
- **Do:** `POST /api/v1/openai/chat/completions` (model = agent slug, streaming chunks mapped from run events, tools not accepted from clients, `user` field ignored in favour of the principal), `GET /api/v1/openai/models`; `POST /api/v1/widget/sessions` (host-signed JWT, `ar_widget_session` cookie, `frame-ancestors` from `allowed_origins`), widget page and loader script.
- **Done when:** the official openai Python SDK streams a reply; the widget works in an allowed origin and is refused in others.
- **Tests:** SDK-based integration test; widget CSP tests; Playwright widget embed page.

### M11-T07 · Notification fan-out to channels
- **Depends on:** M11-T03, M11-T04
- **Areas:** `ar_system/workflows/notification_fanout.py`
- **Spec:** [spec 20 §2](../03-specs/20-notifications-events.md#2-notifications), [spec 09 §7](../03-specs/09-policy-approvals.md#7-approval-notifications-and-channels)
- **Do:** Extend `NotificationFanoutWorkflow` with Slack/Teams DMs through `POST /internal/v1/notify` according to user notification preferences; approval notifications carry action buttons; delivery failures fall back to email.
- **Done when:** an approval request reaches the approver's Slack DM with working buttons.
- **Tests:** Temporal tests with fake channels server.

### M11-T08 · Web: channel admin and account linking
- **Depends on:** M11-T06, M11-T07
- **Areas:** `apps/web/src/app/(admin)/admin/channels/**`, `apps/web/src/app/(app)/settings/profile/**`
- **Spec:** [spec 19 `/admin/channels`, `/settings/profile`](../03-specs/19-web-app.md)
- **Do:** Integrations list and setup wizards (Slack, Teams, email, widget) with manifest download, test button, routing rules, identities table; profile section to link/unlink channel identities.
- **Done when:** an admin can set up a Slack integration end to end using only the UI and the generated manifest.
- **Tests:** Vitest; Playwright setup flow with fake Slack; axe.
