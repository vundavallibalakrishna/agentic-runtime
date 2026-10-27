# Screen layout review — 26 October 2026

Task: M2.5-T01a. Follow-up to the workspace refresh: the individual screens felt uneven in their positioning and spacing.

## Findings and corrections

| Screens | Finding | Correction |
|---|---|---|
| Approvals | Two heavy control rows, an uncontained empty message and an unrelated comment box in an empty queue | Compact settings in the header, grouped scope filters, a contained empty state with Refresh, and comments only when pending work is loaded |
| Tools | Short server rows filled the page width and buried registration below a long list | Existing tools in the main column and registration in a dedicated side panel |
| Knowledge | Creation came before collections; a full-width submit button and serif card titles competed for attention | Collections first, a separate creation panel, a text-width action and interface typography |
| Memory | Mixed form/list widths and heading styles | Saved memories in the main column, memory preferences and creation together in the side panel |
| Skills | Creation dominated the page; search was hidden among advanced creation fields | Skills and search lead the page; authoring has a consistent panel |
| Routines | An oversized form pushed scheduled work to the bottom; field widths varied | Scheduled routines lead; name, agent and instructions align, with schedule fields paired in the creation panel |
| Channels | The Save action could sit beside the token input; selects and text fields had different widths | Existing channels and recent posts lead; all fields align and Save follows them |
| Models | Registration stretched to page width; an empty table appeared during loading | Provider table and registration are separate; loading, empty and failed states do not also show an empty table; errors offer retry |
| Computers | Uncontained creation fields dominated the page | Templates and live computers in the main column, creation in the side panel |
| Quotas | The creation form came before current limits | Consumption and limits lead, with a compact quota form alongside |
| Usage | Export occupied a filter-grid cell and competed with input labels | Export is a page-header action; date and grouping filters share a separate panel |
| Policies | Floating navigation and an uncontained form | Header navigation, compact settings, policies first and a dedicated creation panel |
| Runs, Reviews, Connections | Inconsistent row padding, bare empty states and detached back links | Consistent surfaces and empty states; Reviews/Connections back links move into their headers; connection cards use a responsive grid |
| Users | Page introduction differed from the rest of the workspace | Receives the shared page-header alignment and spacing; directory behavior is unchanged |

The list precedes the form in DOM order as well as visually. At 1280px the creation panel is 320px wide. At 375px it follows the list without page overflow. Existing API calls and mutation payloads are retained. Simple/Advanced still uses each screen's existing settings storage behavior.

## Visual walkthrough

Use the local review startup commands and seeded login in [workspace-polish](workspace-polish.md#how-to-test-visually). This is still the memory-backed, fake-model demo at `http://localhost:3000`; restarting the API resets demo edits.

1. Sign in as **admin@dev.local**. Open Approvals. Expect a calm empty panel and no Comment input. Refresh should reload the queue. Existing loaded pending approvals retain their decision actions and comment input.
2. Open Tools, Knowledge, Memory, Skills and Routines. At 1280px, existing items should be on the left and their creation form on the right. Search Skills without switching to Advanced.
3. Open Channels, Models, Computers, Quotas and Policies. Check consistent field widths and the compact Simple/Advanced selector beside the title. Toggle Advanced to reveal the existing additional fields. On Channels, Save must follow the token field.
4. Open Usage. Export CSV is beside the title; date and grouping filters align below it. Open Users, Runs, Reviews and Connections to inspect their headers, rows and navigation.
5. Repeat at 375px: controls wrap, creation panels follow data, long tables scroll inside their container, and the page has no horizontal overflow. Keyboard reading and tab order follow the same sequence.
6. Repeat in Dark using the account menu. Borders, text and selected controls remain readable.

## Verification

- Web unit suite: **25 passed**.
- TypeScript: passed.
- Biome: changed files passed; the existing `artifact-view.tsx` image warning is unrelated.
- Knip: passed, with existing configuration hints.
- Production web build: passed.
- `screen-layouts.spec.ts`: **5 passed**, including 16 routes at 375px and 1280px in both themes (64 combinations), additional advanced-mode checks, layout/overflow assertions, and axe on each view. The approval-state journey checks empty, pending, failed/retry and loading states using controlled responses without issuing a decision.
- Full backend gates were not repeated for this presentation-only follow-up. Their existing failures and the full-stack startup limitations remain documented in [workspace-polish](workspace-polish.md#verification). The task remains `in_progress` until those repository-wide gates are resolved.

Run the focused checks from the repository root:

```bash
pnpm --filter @ar/web typecheck
pnpm --filter @ar/web test
pnpm exec knip
pnpm --filter @ar/web exec playwright test e2e/screen-layouts.spec.ts --reporter=line
pnpm --filter @ar/web build
```

## Captures

| Screen | Desktop light | Desktop dark | Mobile light | Mobile dark |
|---|---|---|---|---|
| Approvals | [1280px](screen-layouts/approvals-light-1280.png) | [1280px](screen-layouts/approvals-dark-1280.png) | [375px](screen-layouts/approvals-light-375.png) | [375px](screen-layouts/approvals-dark-375.png) |
| Channels | [1280px](screen-layouts/channels-light-1280.png) | [1280px](screen-layouts/channels-dark-1280.png) | [375px](screen-layouts/channels-light-375.png) | [375px](screen-layouts/channels-dark-375.png) |
