# M11 visual checklist

Slack is a workspace the admin can open, test and extend. A linked identity shows on the profile. Posts are durable rows (`channel_posts`), flushed with the catalogue. The plan gate refuses a widget until the feature is on.

Seed data is the dev tenant: integration **Workspace Slack** (bot token `xoxb-demo`), identity `U-ADMIN` for `admin@dev.local`, and one post: "The weekly digest is ready for #platform." The assistant answers Slack, Teams and email. Widget stays off on the default plan.

## Start

```bash
make bootstrap
make dev
make seed
```

Web: http://localhost:3000. API: http://localhost:8000. Dev login: **Sign in as admin@dev.local** on `/login` (`POST /api/v1/auth/dev-login`). No model API key. `fake-llm` answers chat.

Host ports come from `.env`. `make ports-check` names a busy port. `make dev AUTO_PORTS=1` moves it. Defaults: Postgres 5432, Valkey 6379, Temporal 7233, API 8000, web 3000.

Earlier screens stay where they were: Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Approvals, Runs, Models, Computers, Users. Their checklists are `docs/testing/m2.5-checklist.md` through `docs/testing/m10-checklist.md`.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open the account menu and choose **Profile**. Expect `U-ADMIN` and a connect-code field. An account with no links shows the empty state.
3. Open **Channels** (`/admin/channels`). Expect **Workspace Slack**, status active, and the digest post. A tenant with no integrations shows "No channels yet."
4. Choose **Advanced**. Expect the routing field. Choose **Simple** to hide it. The choice is stored as `ar-settings-mode`.
5. Add **Desk Slack** with bot token `xoxb-desk`. Expect "Channel saved." and the new row. A widget save explains that the plan does not include it.
6. Choose **Test connection** on Workspace Slack. Expect "Connection checked." and `auth.test ok`.
7. Narrow to 375px and switch to dark. The list, the form and the profile stay on the same tokens. Loading uses skeletons. A failed load shows **Try again**.
8. Open **Routines** and confirm Weekly digest is still listed (M10). Chat still opens.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m11 pnpm exec playwright test e2e/m11-channels.spec.ts
```

The test signs in, opens Profile, lists Workspace Slack, saves Desk Slack, tests the connection, and expects zero axe violations. Screenshots land in `docs/testing/m11/` for light and dark, desktop (1280) and mobile (375). The walkthrough video is `docs/testing/m11/walkthrough.mp4`.
