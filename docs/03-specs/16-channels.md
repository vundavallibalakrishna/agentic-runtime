# Spec 16: Channels (`channels`, `ar_domain.channels`)

Deployable `channels` (`services/channels`, package `ar_channels`, port 8004) handles Slack, Microsoft Teams and email I/O. It does **not** import `ar_domain`; it talks to `api` internal endpoints and reads run streams from Valkey. Integration management endpoints, the API channel (REST + OpenAI-compatible facade) and the web widget are served by `api`. Owns `channel_integrations`, `channel_identities`, `channel_threads` ([schema §14](../04-data/schema.md#14-channels-ar_domainchannels)). PRD: [11-channels](../01-prd/11-channels.md).

## 1. Responsibilities

1. Receive inbound messages/events from Slack (Events API over HTTP or Socket Mode), Teams (Bot Framework activities via the Microsoft 365 Agents SDK), email (IMAP polling); verify authenticity; normalise; forward to `api`.
2. Map external users to platform users (`channel_identities`) and threads to conversations (`channel_threads`).
3. Stream agent replies back (progressive message updates), upload artifacts, render citations, and present approval buttons.
4. Outbound sends for routine delivery and notifications (`/internal/v1/outbound`, `/internal/v1/notify`).
5. API channel: programmatic runs (`POST /api/v1/runs`, [spec 06](06-conversations-runs.md)) and an OpenAI-compatible facade; generated SDKs.
6. Embeddable web widget for internal portals (feature `widget`).

## 2. Public endpoints on `channels` (ingress path prefix `/channels`)

#### POST /channels/slack/events
Slack Events API. Verifies `X-Slack-Signature` (v0 HMAC-SHA256 of `v0:{ts}:{body}` with the integration signing secret; `ts` within 300 s); responds to `url_verification`; dedupes by `event_id` (Valkey `ar:chan:dedupe:{event_id}` 1 h); acknowledges within 3 s and processes asynchronously. Integration resolved by `team_id` + `api_app_id` (`/internal/v1/channels/integrations` cache).

#### POST /channels/slack/interactions
Block actions (approval buttons, "Connect" links), shortcuts, modal submissions. Same verification.

#### POST /channels/slack/commands
Slash command `/agent [agent-slug] <prompt>` (command name configurable per integration, default `/agent`).

#### POST /channels/teams/messages
Bot Framework activities; validates the JWT (`Authorization: Bearer`) against Bot Framework OpenID metadata (issuer, audience = bot app id, signing keys cached 24 h); handles `message`, `invoke` (`adaptiveCard/action` for approvals), `conversationUpdate` (welcome message on install).

Socket Mode (Slack, `config.socket_mode: true`) is used when the deployment has no public ingress: one websocket per integration held by the leader replica (Valkey lock `ar:chan:leader:{integration_id}`, TTL 30 s, renewed every 10 s).

Email: `aioimaplib` IDLE/poll (every 60 s) of the configured mailbox; outbound via `aiosmtplib`. No public endpoint.

## 3. Inbound processing

`ChannelInboundMessage {integration_id, kind: slack|teams|email, event_id, external_user_id, external_user_email?, external_channel_id, external_thread_id, external_message_id, is_dm, mentions_bot, text, files: [{download_ref, name, mime_type, size_bytes}], command?: {name, agent_slug?}}`

Rules (in `channels`):
- Slack: respond to DMs, `app_mention`s and messages in threads the bot participates in; ignore bot messages (including its own), edits (v1), and channels not allowed by `config.allowed_channel_ids` (empty = all).
- Teams: personal chat, channel @mentions, group chats where mentioned.
- Email: messages to the integration address; reject unless `Authentication-Results` shows SPF or DKIM pass for a verified tenant domain (`tenant_domains`), else bounce politely (once per sender per day).

Forward to `api` `POST /internal/v1/channels/inbound` which (in `ar_domain.channels.service.handle_inbound`):
1. Resolves the user: `channel_identities` by `(integration_id, external_user_id)`; else by verified email match (`match_method='email'`, Slack `users.info` / Teams `aadObjectId` → email provided by `channels`); else returns `{action: "link_required", link_url}` → `channels` replies (ephemeral in Slack) with a link to `/settings/profile?link={signed_token}`.
2. Selects the agent: `command.agent_slug` → `agent_routing` match (`channel_id`, `keyword` prefix) → `default_agent_id`; the agent must have `channels.<kind>: true` and be visible to the user.
3. Finds/creates the conversation via `channel_threads (integration_id, external_channel_id, external_thread_id)` (Slack thread `ts` or message `ts` for new threads; Teams `conversation.id` + reply chain id; email root `Message-ID`). Shared-channel conversations are owned by the user who started the thread; other participants' messages in the thread are attributed to them (`author_user_id`) but runs execute **as the message author** (each message's run uses its author's identity and permissions).
4. Downloads files (via `channels` signed download proxy `GET /internal/v1/files/{download_ref}`, which fetches with the bot token) into `files(kind='upload')`.
5. Posts the message and starts the run exactly like the web (`conversations.service.post_message`, channel = kind); busy conversation → queue the message as a follow-up run (`interrupt=false`, waits up to 2 min) else reply "Still working on the previous request".
6. Returns `{conversation_id, run_id}`.

## 4. Reply streaming

`channels` subscribes to `ar:run:{run_id}:events` (Valkey `XREAD`) and renders:
- Slack: placeholder message "…" in thread → `chat.update` at most every 1.5 s with accumulated Markdown converted to Slack mrkdwn (`ar_channels.render.slack`), split at 3,500 chars into continuation messages; tool activity as a context block (`Using jira.search_issues…`); final message with citations as numbered footnote links; artifacts uploaded with `files.uploadV2` (≤ 10 per message, others linked to the web UI); feedback buttons (👍/👎 → `PUT /api/v1/messages/{message_id}/feedback` via internal call); "Open in web" button.
- Teams: typing indicator → message → `updateActivity` every 2 s; Adaptive Card for final answer with citations; attachments as links (Teams file upload requires consent flow; v1 links to the web UI with presigned access via the user's session).
- Email: single reply on completion (Markdown → HTML via `markdown-it` equivalent `mistune`, sanitised), attachments ≤ 20 MiB total, else links.
- `tool_call.approval_required`: Slack/Teams interactive approval message to eligible approvers who are the requester in this thread (others get DMs via `/internal/v1/notify`); buttons carry `{approval_id, args_hash}`; decisions posted to `api` `/internal/v1/channels/approval-decisions`. Step-up approvals show only "Open in web".
- `input.required`: Slack modal / Teams card with fields generated from `requested_schema` (string, number, boolean, enum; others → "Open in web").
- `tool_call.failed` with `connect_url`: "Connect <provider>" button.
- Terminal events: final update; failures show a short error and "Open in web".

## 5. Integration management API (served by `api`)

Permission `channels:manage`.

#### GET /api/v1/channel-integrations
Item `ChannelIntegration {id, kind, name, config (non-secret), default_agent: {id, name}|null, agent_routing, status, status_detail, created_at, identities_count}`.

#### POST /api/v1/channel-integrations
Body `{kind, name, config, credentials: {...} (stored as secret: Slack `bot_token`, `signing_secret`, `app_token`(socket); Teams `app_id`, `app_password`, `tenant_id`; email `imap_host`, `imap_port`, `smtp_host`, `smtp_port`, `username`, `password`, `address`), default_agent_id?, agent_routing?}`. Emits `ar:invalidate:channel_integration:{id}`; `channels` reloads.

#### GET /api/v1/channel-integrations/{integration_id}
The list item plus `recentPosts` (at most five, body truncated to 280 characters). Credentials are never returned.
#### PATCH /api/v1/channel-integrations/{integration_id}
#### DELETE /api/v1/channel-integrations/{integration_id}
#### POST /api/v1/channel-integrations/{integration_id}:test
Calls `channels` `POST /internal/v1/integrations/{id}:test` (Slack `auth.test`, Teams token acquisition, IMAP login + SMTP NOOP) → `{ok, detail}`.

#### GET /api/v1/channel-integrations/{integration_id}/manifest
Slack: generated app manifest (YAML) with scopes (`app_mentions:read`, `chat:write`, `files:read`, `files:write`, `im:history`, `im:read`, `im:write`, `users:read`, `users:read.email`, `commands`, `channels:history`, `groups:history`) and request URLs; Teams: app package (zip with `manifest.json` and icons). Used by admins to install the app in their workspace.

#### GET /api/v1/channel-integrations/{integration_id}/identities
Linked users. 
#### DELETE /api/v1/channel-integrations/{integration_id}/identities/{identity_id}

#### GET /api/v1/me/channel-identities
The caller's links. Permission `chat:use` (a member links their own account; `channels:manage` stays on the admin catalogue). The install manifest uses `channels:manage`.
#### POST /api/v1/me/channel-identities:link
Body `{token}` (the signed link token from the bot message, `AR_CHANNEL_LINK_TTL_S=900`) → creates `channel_identities (match_method='manual_link', verified_at=now)`.
#### DELETE /api/v1/me/channel-identities/{identity_id}

## 6. API channel

- REST: `POST /api/v1/runs` and the conversation endpoints with API keys (`ark_…`) or service account keys. OpenAPI document at `GET /api/v1/openapi.json`; generated SDKs: Python `agentic-runtime-client` (from `openapi-python-client`, package `ar_client`) and TypeScript `@ar/api-client` (hey-api), published from CI.

#### POST /api/v1/openai/chat/completions
OpenAI Chat Completions-compatible facade for existing client libraries. Auth: API key, permission `chat:use`. The JSON for this facade stays snake_case (`finish_reason`, `data`) so the official SDK can read it; other public JSON stays camelCase. `model` = agent slug (must be published, visible, `channels.api: true`). The `user` field is ignored; the principal wins. The last `user` message becomes the input; earlier messages are used only when `X-AR-Conversation-Id` is absent and are prepended to the input as a transcript (`<prior_messages>` block, untrusted). `X-AR-Conversation-Id` continues a conversation. `stream: true` → OpenAI-style SSE chunks (`choices[0].delta.content`) mapped from `message.delta`; tool activity is not exposed (only final text; approvals cause `finish_reason: "approval_required"` with a `ar_approval_url` extension field). `tools`/`functions` in the request are rejected (400). Response includes `usage` and header `X-AR-Run-Id`.

#### GET /api/v1/openai/models
Agents usable via the facade (`{data: [{id: slug, object: "model", owned_by: "tenant"}]}`).

## 7. Web widget (feature `widget`)

The host embeds `<script src="{AR_PUBLIC_URL}/widget.js" data-integration="{id}"></script>`. The loader opens a minimal chat iframe at `/widget/{integration_id}` with loading, empty, error/retry, streaming, cancellation and reconnect states. Both themes follow the system preference. Escape closes the iframe and returns focus to the launcher.

The host server signs a JWT using the integration's HS256 secret or RS256 key with registered HTTPS JWKS URL `config.jwksUrl`. Claims are `{sub: email, name, exp, aud: "ar-widget:{integration_id}"}`. Expiry must be in the future and no more than ten minutes away; future `iat`/`nbf`, unsupported algorithms and invalid signatures are rejected. The user and tenant must already exist and be active. JWKS fetching uses the shared SSRF guard and does not follow redirects.

The host listens for `ar-widget:token-request` and calls `event.detail.respond(jwt)` after obtaining a short-lived token from its own authenticated backend. The signing secret never enters browser code. The iframe sends a nonce in `ar-widget:ready`; credentials are accepted only from `window.parent`, an exact configured origin and that nonce. The loader validates the iframe source and origin before answering. Tokens never enter URLs or browser storage.

`config.allowedOrigins` contains exact HTTPS origins, or HTTP loopback origins for development. Paths, wildcards, credentials and CSP delimiters are invalid. The actual Next response sets `Content-Security-Policy: frame-ancestors` to this allowlist; unavailable policies deny framing. A browser origin cannot be granted by matching only a prefix.

The server issues an opaque encrypted server-side session with `ar_widget_session; HttpOnly; Secure; SameSite=None; Partitioned; Path=/api/v1/widget`. Its lifetime cannot exceed the host token. The session grants only `chat:use` for configured default/routing agents and a single conversation created in that session. It is ignored on workspace endpoints. Workspace cookies cannot authenticate widget endpoints. Mutation requests require the session's CSRF token. Expiry, integration status, tenant and user status, and the agent allowlist are checked on every request. Reauthentication rotates the session; it does not expose historical workspace conversations. Successful authentication records `auth.login` with channel `widget` before releasing the cookie.

#### GET /api/v1/widget/integrations/{integration_id}
Public framing policy for an active enabled widget: `{allowedOrigins, name}`. Returns `404` for disabled or unavailable integrations.

#### POST /api/v1/widget/sessions
Public host-token exchange. Body `{integrationId, token}` → `204` plus restricted cookie; invalid authentication returns `401`. No-store response.

#### GET /api/v1/widget/session
Permission `chat:use`, restricted widget session only. Returns `{integrationId, name, agents: [{id, name}], csrfToken, conversationId}`. No-store response.

#### POST /api/v1/widget/conversations
Permission `chat:use`. Body `{agentId}` creates the session's conversation. An agent outside the integration allowlist returns `404`. Updating the session does not extend its expiry.

#### GET /api/v1/widget/conversations/{conversation_id}
Permission `chat:use`. Returns the bound conversation and messages. Unrelated conversations, owners or tenants return `404`.

#### POST /api/v1/widget/conversations/{conversation_id}/messages
Permission `chat:use`. Body `{text}` (1–32000 characters) starts the ordinary agent workflow and returns `202` with `{message, run}`.

#### GET /api/v1/widget/runs/{run_id}/events
Permission `chat:use`. Streams the ordinary SSE run events, only for the session's conversation.

#### POST /api/v1/widget/runs/{run_id}:cancel
Permission `chat:use`. Signals cancellation through the ordinary run handler, only for the session's conversation.

## 8. Configuration (`channels`)

| Variable | Default | Purpose |
|---|---|---|
| `AR_CHANNELS_PORT` | `8004` | |
| `AR_API_INTERNAL_URL` | `http://api:8000` | |
| `AR_VALKEY_URL` | | Streams, dedupe, leader locks |
| `AR_CHANNELS_SLACK_UPDATE_INTERVAL_MS` | `1500` | |
| `AR_CHANNELS_TEAMS_UPDATE_INTERVAL_MS` | `2000` | |
| `AR_CHANNELS_EMAIL_POLL_S` | `60` | |
| `AR_CHANNEL_LINK_TTL_S` | `900` | |
| `AR_PUBLIC_URL` | | Links to the web UI |

## 9. Failure modes

| Failure | Behaviour |
|---|---|
| Slack/Teams rate limit (429) | Respect `Retry-After`; coalesce updates; never drop the final message (retry up to 10 min). |
| `api` unavailable | Reply "Temporarily unavailable, please retry"; Slack events are acknowledged (no Slack redelivery storms). |
| Valkey stream expired before reply finished | Fetch final message via `api` internal run read. |
| Leader replica dies (socket mode) | Lock expires in ≤ 30 s; another replica connects. |

## 10. Metrics

`ar_channel_inbound_total{kind,result}`, `ar_channel_reply_latency_seconds{kind}` (inbound → first visible reply), `ar_channel_outbound_total{kind,result}`, `ar_channel_rate_limited_total{kind}`, `ar_channel_link_required_total{kind}`.

## 11. Test plan

- Unit: signature verification (Slack vectors), Teams JWT validation with a local JWKS, Markdown → mrkdwn/Adaptive Card rendering snapshots, message splitting, thread key derivation, email auth header parsing.
- Integration: Slack events replayed from fixtures through `channels` → `api` (testcontainers) → `fake-llm` → updates captured by a fake Slack Web API (respx); approval button round-trip; link-required flow; email round trip via a GreenMail container (SMTP + IMAP; Mailpit is used for local-dev outbound mail capture only); OpenAI facade compatibility using the official `openai` Python client against `api` (stream and non-stream).
