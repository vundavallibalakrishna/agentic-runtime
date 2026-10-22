# Design system

The web app is a neutral surface with one ink accent. Type, spacing and a hairline do the work. Linear, Vercel and Claude are the reference for restraint. Source Serif is used once, on the sign-in title and the empty chat greeting. Everything else is Source Sans. The product stays industry-agnostic. GRC vocabulary does not appear in this chrome.

## Tokens

All colour, type, radius, shadow and motion values live in `apps/web/src/app/globals.css`. Feature code uses the CSS variables (`var(--primary)`, `var(--muted-foreground)`, `var(--scrim)`) and does not add hex colours. Syntax highlighting may apply a theme colour at runtime; that colour is not written into a component.

| Token | Use |
|---|---|
| `--background`, `--foreground` | Page |
| `--card`, `--sidebar` | Panels and the navigation column |
| `--muted`, `--muted-foreground` | Quiet surfaces and secondary text |
| `--primary`, `--primary-foreground` | The one accent and the label on it |
| `--border`, `--ring` | Hairlines and the focus ring |
| `--destructive` | A failed action |
| `--scrim` | The layer behind a menu or the command palette |
| `--shadow`, `--radius` | Elevation and corners |
| `--motion` | Short transitions |

Light and dark are both specified. The theme choice is `system`, `light` or `dark`, stored in `localStorage` under `ar-theme`. The default is `system`. A small script in the document head applies the choice before paint. `prefers-reduced-motion: reduce` shortens animation and transitions.

## Type

The faces are loaded with `next/font`: Source Sans 3 for the interface, Source Serif 4 for the sign-in title and the empty-chat greeting, IBM Plex Mono for code. The scale is `--text-xs` through `--text-3xl`.

## Shell

`AppShell` is the signed-in frame.

- A collapsible sidebar with the mark and the wordmark, the workspace name, and primary navigation.
- Navigation items are Chat, Agents, Tools, Knowledge, Routines, Approvals, Runs, Models, Computers and Users. An item is hidden when the session lacks its permission. Sections that are not built yet stay in the list with a "Soon" mark and open a short holding page.
- The header shows the workspace and the signed-in email, a command palette (⌘K or Ctrl+K), and an account menu with the theme choice and sign-out.
- ⌘⇧O (Ctrl+Shift+O) starts a new chat.
- Below the `lg` breakpoint the sidebar becomes a panel over a scrim.

## Settings detail

Where a form has a simple path and extra fields, the page offers Simple and Advanced. The choice is stored in `localStorage` under `ar-settings-mode`. Simple is the default. On Models, Simple is the provider name and the register action. Advanced also shows the base URL.

## Chat

The thread sits in a centred column. The composer grows with the text, accepts a file, and sends on Enter. Shift+Enter inserts a line. Streaming keeps a caret, announces text through `aria-live="polite"` about twice a second, and does not pull the scroll position when the reader has moved up. Markdown, including fenced code with a copy control, is rendered in the thread. Copy and regenerate sit on the message.

## Sign-in

The sign-in page offers the organisation account and the four seeded roles (`admin`, `builder`, `member`, `approver` at `@dev.local`). The Keycloak login theme under `deploy/compose/keycloak/themes/agentic` uses the same paper, ink and teal. Those theme files are CSS for Keycloak and are the one place a hex value is expected, because Keycloak does not read the web tokens.

## Bar

Empty, loading and error states, visible focus, labels on inputs, and layouts at 375 px and 1280 px are required. The quality bar is [ux-quality](ux-quality.md). Behaviour of the screens is [spec 19](../03-specs/19-web-app.md).
