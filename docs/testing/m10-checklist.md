# M10 visual checklist

A weekly routine (cron, Asia/Kolkata) runs the assistant as its owner and records a Slack delivery through a standing approval. A second routine created in the form can be run now from the detail page. Webhook deliveries with the same body are one event.

Seed data is the dev tenant: routine **Weekly digest** (`0 9 * * 1`, `Asia/Kolkata`), delivery to the owner's conversation and `#platform` with a standing approval. Slack itself is stubbed until channels land.

## Start

```bash
make bootstrap
make dev
make seed
```

Dev login: **Sign in as admin@dev.local** on `/login`. Host ports come from `.env` (`AR_API_HOST_PORT`, `AR_WEB_HOST_PORT`).

The sample routine lives in the API process store. `make seed` writes Postgres rows for migrations; the page lists the in-memory catalogue.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open **Routines** (`/routines`). Expect Weekly digest, the summary Every Monday 09:00 IST, and a create form. An empty tenant shows the empty state.
3. Choose **Preview schedule**. Expect the next five Monday 09:00 fires in Asia/Kolkata.
4. Create **Launch reminder** with instructions and the default weekly cron. Expect the detail page.
5. Choose **Run now**. Expect "Run started." and a manual event.
6. Choose **Pause**, then **Resume**. Expect the status to follow.
7. Sign in as `member@dev.local`. The admin's routine is not listed. A routine id from another tenant returns 404.
8. Switch the theme to dark and narrow the window to 375px. The list, the form and the detail stay readable. Loading and error states use the same tokens.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m10 pnpm exec playwright test e2e/m10-routines.spec.ts
```

Screenshots land in `docs/testing/m10/` for light and dark, desktop (1280) and mobile (375). The walkthrough video is `docs/testing/m10/walkthrough.mp4`.
