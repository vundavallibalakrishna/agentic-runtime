# M8 visual checklist

Memory the assistant keeps, the review queue for shared lessons, and a chat reply that uses a preference until you delete it. Seed data is the dev tenant: a one-page status preference, the Platform team glossary, an active lesson on the Assistant, and one lesson waiting for review.

## Start

```bash
make bootstrap
make dev
make seed
```

Dev login: **Sign in as admin@dev.local** or **Sign in as member@dev.local** on `/login`. Host ports come from `.env` (`AR_API_HOST_PORT`, `AR_WEB_HOST_PORT`).

The sample facts live in the API process store. `make seed` writes Postgres rows for migrations; the page you click lists the in-memory facts.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat empty state.
2. Open **Memory** (`/memory`). Expect the one-page status preference, the Platform team line about dating file names, Simple and Advanced, and the remember toggle. Advanced shows scope, category and search.
3. Open Chat and send `Remember that I prefer answers in bullet points.` Expect **Memory updated** with Undo.
4. Start a **New chat** and send `Draft a short status update`. Expect a reply in bullet points and a line that memories were used.
5. Open **Memory**, delete the bullet-point preference, start another chat, and send the same status prompt. The reply no longer follows that preference.
6. Open **Agents**, open **Assistant**. Expect the visitor-desk lesson waiting for review. **Approve** removes it from the queue. **Add a shared lesson** is on the same page.
7. Sign out and sign in as `member@dev.local`. Open **Memory**. The admin's one-page preference is absent. The Platform glossary is visible.
8. Switch the theme to dark and narrow the window to 375px. Memory, the remembered chat and the review queue stay readable. Empty, loading and error states use the same tokens.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m8 pnpm exec playwright test e2e/m8-memory.spec.ts
```

Screenshots land in `docs/testing/m8/` for light and dark, desktop (1280) and mobile (375).
