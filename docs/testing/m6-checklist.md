# M6 visual checklist

Computers, artifacts and the browser. Seed data is the dev tenant (`admin@dev.local`) plus the Revenue analyst agent and a finished “Revenue by month” thread.

## Start

```bash
make bootstrap
make dev
make seed
```

Dev login: `POST /api/v1/auth/dev-login` with `admin@dev.local`, or use **Sign in as admin@dev.local** on `/login`. Host ports come from `.env` (API `AR_API_HOST_PORT`, web `AR_WEB_HOST_PORT`).

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat empty state with the assistant greeting.
2. Open **Computers** in the sidebar (`/admin/sandboxes`). Expect platform templates `default`, `python-data`, `browser` and `data-science`, plus Simple and Advanced. Advanced shows CPU, memory and package installs.
3. Open Chat, choose **Revenue analyst**, and send `Analyse the attached CSV and chart revenue by month`. Expect the reply to mention `revenue-by-month.png` and the computer panel to show the PNG.
4. Open the seeded thread **Revenue by month**. Expect the same chart in the artifacts list.
5. Attach a `.csv` on a new analyst thread and send the same sentence. Expect another PNG artifact.
6. Switch the theme to dark and narrow the window to 375px. The computer panel and the Computers page stay readable. Empty, loading and error states use the same tokens.
7. A file named `page.html` downloads as an attachment with `Content-Type: application/octet-stream`. The app does not render it inline.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m6 pnpm exec playwright test e2e/m6-computer.spec.ts
```

Screenshots land in `docs/testing/m6/` for light and dark, desktop (1280) and mobile (375).
