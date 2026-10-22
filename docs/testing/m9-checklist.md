# M9 visual checklist

A research lead delegates two questions to a researcher and merges the findings. A writer loads the brand-guidelines skill and produces a one-page DOCX. The run trace shows the parent and both children.

Seed data is the dev tenant: skill `brand-guidelines` (asset `letterhead.md`), agents `researcher`, `research-lead` and `writer`.

## Start

```bash
make bootstrap
make dev
make seed
```

Dev login: **Sign in as admin@dev.local** or **Sign in as member@dev.local** on `/login`. Host ports come from `.env` (`AR_API_HOST_PORT`, `AR_WEB_HOST_PORT`).

The sample skill and agents live in the API process store. `make seed` writes Postgres rows for migrations; the pages you click list the in-memory catalogue.

## Click-through

1. Open `/login` and sign in as `admin@dev.local`. Expect the chat heading.
2. Open **Skills** (`/skills`). Expect Brand guidelines, Simple and Advanced, and a create form. Advanced shows slug and search. An empty search that matches nothing shows the empty state.
3. Open Brand guidelines. Expect the Markdown preview, sentence case, the letterhead asset in Advanced, versions, and Writer under where-used.
4. Create a skill named `Launch checklist` with a one-line description and instructions, then publish it with a change note. Expect version 1.
5. Open Chat at `/chat?agent=research-lead`. Send `Research the launch notes and the rollout plan`. Expect **Merged findings** covering launch notes and the rollout plan.
6. Choose **View trace**. Expect two Researcher children on the graph.
7. Start a new chat at `/chat?agent=writer`. Send `Write a one-page brand brief as a docx`. Expect `brand-brief.docx` and sentence case.
8. Open **Runs**. Expect the completed traces, including an empty list only before the first message.
9. Open an agent, choose Advanced, and open the Skills and Subagents tabs. Expect slug fields and depth controls.
10. Sign in as `member@dev.local`. Skills still lists Brand guidelines. A skill owned by another tenant is not shown.
11. Switch the theme to dark and narrow the window to 375px. Skills, the trace and chat stay readable. Loading and error states use the same tokens.

## Automated

```bash
cd apps/web && E2E_SCREENSHOT_DIR=../../docs/testing/m9 pnpm exec playwright test e2e/m9-skills.spec.ts
```

Screenshots land in `docs/testing/m9/` for light and dark, desktop (1280) and mobile (375). The walkthrough video is `docs/testing/m9/walkthrough.mp4`.
