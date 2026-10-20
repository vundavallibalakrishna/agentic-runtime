# PRD 11 — Channels

Users reach agents from the web app, Slack, Microsoft Teams, email, the REST API, an OpenAI-compatible endpoint and an embeddable widget for signed-in users. Spec: [spec 16](../03-specs/16-channels.md), [spec 20](../03-specs/20-notifications-events.md). Plan: [M11](../09-plan/M11-channels.md).

### US-CH-01 · Connect a Slack workspace (P0)
As a **tenant admin**, I want to install the agent app in our Slack workspace.
- `POST /api/v1/channel-integrations` (kind `slack`) with bot token and signing secret stored as secrets; `GET …/manifest` provides the app manifest to paste; `:test` verifies credentials; default agent, keyword/channel routing and allowed channels are configurable.
- Spec: spec 16 §5. Plan: M11-T01, M11-T03, M11-T08.

### US-CH-02 · Chat with agents in Slack (P0)
As a **member**, I want to DM the bot or @mention it in a channel and get a streamed answer in the thread.
- DMs, mentions and threads the bot participates in are handled; the reply updates in place at most every 1.5 s, long answers continue in follow-up messages, citations as footnote links, files attached to my message are passed to the agent.
- Each Slack thread maps to one conversation visible in the web app; approvals, input requests and "Connect" buttons work in Slack; step-up approvals show "Open in web".
- Spec: spec 16 §2–4. Plan: M11-T02, M11-T03.

### US-CH-03 · Chat with agents in Microsoft Teams (P1)
As a **member**, I want the same experience in Teams (personal chat, channel @mentions, group chats).
- Typing indicator, message updates every 2 s, Adaptive Card final answer with citations; attachments as links to the web app; approvals and input requests as cards.
- Spec: spec 16 §2–4. Plan: M11-T04.

### US-CH-04 · Link my channel identity (P0)
As a **member**, I want my Slack/Teams account linked to my platform user so that the agent acts as me.
- Automatic match by verified email; otherwise the bot replies with a link (valid `AR_CHANNEL_LINK_TTL_S`) to complete linking while signed in; I can see and unlink identities (`GET /api/v1/me/channel-identities`, `DELETE …/{identity_id}`); unlinked users cannot run agents.
- Spec: spec 16 §3, §5. Plan: M11-T02, M11-T08.

### US-CH-05 · Email an agent (P1)
As a **member**, I want to email an agent address and get the answer by reply.
- Messages from verified tenant domains with SPF or DKIM pass are processed; the thread maps to a conversation; reply is sent on completion with sanitised HTML and attachments ≤ 20 MiB (else links).
- Spec: spec 16 §3–4. Plan: M11-T05.

### US-CH-06 · Use agents from my own application (P0)
As an **integrator**, I want REST and OpenAI-compatible access so that existing clients and SDKs work.
- REST: `POST /api/v1/runs` ([US-RUN-06](05-runs-subagents.md#us-run-06--start-runs-from-the-api-p0)). OpenAI-compatible: `POST /api/v1/openai/chat/completions` with `model` = agent slug (streaming supported), `GET /api/v1/openai/models` lists usable agents; API keys of service accounts authenticate; tool calls are executed server-side by the agent (not returned to the client).
- Spec: spec 16 §6. Plan: M11-T06.

### US-CH-07 · Embed a chat widget in an internal portal (P1)
As a **tenant admin**, I want to embed an agent in our intranet for signed-in employees.
- Embed script + iframe; the host signs a short-lived JWT (HS256 widget secret or RS256 via JWKS) mapping to an existing active user; no anonymous users; `allowed_origins` drive `frame-ancestors`; requires plan feature `widget`.
- Spec: spec 16 §7. Plan: M11-T06.

### US-CH-08 · Receive notifications in my channels (P0)
As a **member**, I want approval requests, routine results and alerts delivered in-app and, per my settings, by email, Slack or Teams.
- Notification preferences on my profile (`PATCH /api/v1/me` `settings.notifications`); in-app notification centre with unread count; channel delivery via `NotificationFanoutWorkflow`.
- Spec: spec 20, spec 16. Plan: M1-T14, M11-T07.
