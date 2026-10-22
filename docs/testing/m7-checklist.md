# M7 visual checklist

Knowledge collections, ACL-scoped search, and citations. Seed data is the dev tenant plus the Company library (visitor guide, payroll calendar, on-call roster) and the Librarian agent.

## Start

```bash
make bootstrap
make dev
make seed
```

Dev login: **Sign in as admin@dev.local** or **Sign in as member@dev.local** on `/login`. Host ports come from `.env` (`AR_API_HOST_PORT`, `AR_WEB_HOST_PORT`).

The sample collection lives in the API process store. `make seed` writes Postgres rows for migrations; the page you click lists the in-memory library.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat empty state.
2. Open **Knowledge** (`/knowledge`). Expect **Company library**, Simple and Advanced. Advanced shows slug and description.
3. Open **Company library**. Expect Visitor guide and Payroll calendar. On-call roster is listed as hidden from you.
4. Open **Search**, keep the visitor-desk question, and choose **Ask the library**. Expect Visitor guide and “The library can answer this.”
5. Open Chat, choose **Librarian**, and send `When does the visitor desk open?`. Expect a citation chip. Open it and expect the 08:30 passage. **Why** shows the grounding report.
6. Sign out and sign in as `member@dev.local`. Open the same collection. Expect On-call roster. Payroll calendar is absent. Search `When is payroll released?` and expect no payroll hit.
7. Switch the theme to dark and narrow the window to 375px. The library, search hits, and citation drawer stay readable. Empty, loading, and error states use the same tokens.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m7 pnpm exec playwright test e2e/m7-knowledge.spec.ts
```

Screenshots land in `docs/testing/m7/` for light and dark, desktop (1280) and mobile (375).
