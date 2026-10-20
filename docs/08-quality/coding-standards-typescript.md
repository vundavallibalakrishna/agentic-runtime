# TypeScript coding standards

Applies to `apps/web` (`@ar/web`) and `packages/*` (`@ar/api-client`, `@ar/tsconfig`). Architecture and pages: [spec 19](../03-specs/19-web-app.md). Versions: [stack](../stack.md) (TypeScript 7 with documented TS6 fallback, OQ-12).

## 1. Compiler and tooling

- `packages/tsconfig/base.json`: `strict: true`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `verbatimModuleSyntax`, `moduleResolution: "bundler"`, `target: "ES2024"`, `isolatedModules`.
- Biome (`biome.json` at the root) is the only linter/formatter: recommended rules + `noExplicitAny: error`, `noNonNullAssertion: error`, `useExhaustiveDependencies: error`, `noConsole: error` (allow in scripts), `useImportType`, `noBarrelFile` (except `packages/api-client/src/index.ts`), `a11y` group as errors. Line width 100, double quotes, semicolons, trailing commas.
- `knip` must be clean (no unused files/exports/deps).
- No `// @ts-ignore`; `// @ts-expect-error <reason>` only in tests.

## 2. Project structure rules (Next.js App Router)

- Route groups `(app)`, `(admin)/admin`, `(platform)/platform`, `(auth)`, `widget` per [spec 19 §2](../03-specs/19-web-app.md#2-directory-layout-appswebsrc).
- Server Components by default; add `"use client"` only for interactive leaves (forms, chat, editors). Data fetching in Server Components goes through `lib/server/api.ts` (forwards the session cookie to `AR_API_INTERNAL_URL`); client components use generated TanStack Query hooks from `@ar/api-client`.
- The browser never sees tokens: all API calls go to same-origin `/api/v1/*` (proxied to `api`) with the session cookie and `X-CSRF-Token` header added by the shared `fetch` wrapper `lib/api/fetcher.ts`.
- Feature folders: `src/features/<area>/{components,hooks,schemas.ts,utils.ts}`; shared UI in `src/components/ui` (shadcn, generated, edited only via the CLI or with a comment `// modified:` explaining the change) and `src/components/common`.
- No direct `fetch` to API URLs in components; no hand-written API types (generated types only). Regenerate with `make gen`.

## 3. React rules

- Function components, named exports, props typed with `type Props = {...}`; no `React.FC`.
- State: TanStack Query for server state, zustand for client-only state, nuqs for URL state, react-hook-form + zod for forms ([spec 19 §6](../03-specs/19-web-app.md#6-state-management-rules)).
- Query keys from generated helpers; mutations invalidate exactly the affected keys; optimistic updates only where spec 19 says so.
- Effects only for synchronisation with external systems; never for derived state.
- Streaming: SSE parsing with `eventsource-parser` over `fetch`; events validated with zod schemas generated from `ar_contracts` JSON Schema; unknown event types are ignored (forward compatible) and logged once.
- Rendering untrusted content: Markdown via `react-markdown` + `rehype-sanitize` (no raw HTML), links get `rel="noopener noreferrer nofollow"` and external-link confirmation; HTML previews in sandboxed iframes (`sandbox` without `allow-same-origin`); never `dangerouslySetInnerHTML` except DOMPurify output in `components/common/SafeHtml.tsx`.
- Permission gating via `usePermissions()` (from `GET /api/v1/auth/session`); hidden **and** server-enforced (UI gating is convenience only).

## 4. Accessibility and i18n

- WCAG 2.1 AA: keyboard navigation for every action, visible focus, labels on inputs, `aria-live="polite"` for streaming assistant text (throttled), colour contrast ≥ 4.5:1; axe checks in Playwright must pass.
- All user-facing strings via `next-intl` (`messages/en.json`); no string literals in JSX except tests/stories. Dates via `date-fns` with the user's timezone setting.

## 5. Styling

- Tailwind v4 utility classes; design tokens as CSS variables in `app/globals.css` (shadcn theme); dark mode via `class` strategy. No inline style objects except dynamic values (e.g. virtualised list offsets). `cn()` helper for class merging.

## 6. Errors and loading

- Every page and data component has loading (skeleton), empty and error states; errors from the API (RFC 9457) displayed with `title` and mapped field errors; `request_id` shown in error details for support.
- Route-level `error.tsx` and `not-found.tsx` per group.

## 7. Naming

| Thing | Convention | Example |
|---|---|---|
| Components / files | PascalCase component in kebab-case file | `run-inspector.tsx` exports `RunInspector` |
| Hooks | `useX` in `use-x.ts` | `useRunStream` |
| Zod schemas | `xSchema` | `agentFormSchema` |
| Test files | `*.test.tsx` beside the file; e2e in `apps/web/e2e/*.spec.ts` | |
| Stories | `*.stories.tsx` | |

## 8. Testing

Vitest + Testing Library + msw for components; Playwright + axe for e2e; Storybook for chat and builder components. Details and coverage gates: [testing-strategy](testing-strategy.md).
