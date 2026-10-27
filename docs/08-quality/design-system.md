# Design system

The web app is a warm neutral surface with one ink accent. Type, spacing and a hairline do the work. Linear, Vercel and Claude are the reference for restraint. Source Serif is used once, on the sign-in title and the empty chat greeting. Everything else is Source Sans. The product stays industry-agnostic. GRC vocabulary does not appear in this chrome.

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
| `--shadow`, `--shadow-xs`, `--shadow-composer`, `--radius` | Menus, subtle card elevation, composer elevation and corners |
| `--nav-active` | Selected navigation surface |
| `--motion` | Short transitions |

Light and dark are both specified. The theme choice is `system`, `light` or `dark`, stored in `localStorage` under `ar-theme`. The default is `system`. A small script in the document head applies the choice before paint. `prefers-reduced-motion: reduce` shortens animation and transitions.

## Type

The faces are loaded with `next/font`: Source Sans 3 for the interface, Source Serif 4 for the sign-in title and the empty-chat greeting, IBM Plex Mono for code. The scale is `--text-xs` through `--text-3xl`.

## Shell

`AppShell` is the signed-in frame.

- A collapsible sidebar with a layered mark and wordmark, a new-chat action, and navigation grouped into Workspace, Resources and Manage. The workspace name appears in the header breadcrumb.
- Navigation remains hidden until the session grants the matching permission. A create-agent shortcut is visible only to builders.
- Navigation items are Chat, Agents, Tools, Knowledge, Memory, Skills, Routines, Channels, Approvals, Runs, Models, Computers and Users. An item is hidden when the session lacks its permission. Sections that are not built yet stay in the list with a "Soon" mark and open a short holding page.
- The header shows the workspace and the signed-in email, a command palette (⌘K or Ctrl+K), and an account menu with the theme choice and sign-out.
- ⌘⇧O (Ctrl+Shift+O) starts a new chat.
- Below the `lg` breakpoint the sidebar becomes a focus-trapped dialog over a scrim. Escape closes it and restores focus. Account choices use a keyboard-accessible menu.
- Search remains reachable on mobile. A skip link moves keyboard focus to the main content.

## Page layout

Management pages use one `PageHeader`: title and description on the left, page actions or the compact Simple/Advanced selector on the right. At narrow widths actions wrap below the description. A divider separates the page introduction from the work.

`common/ManagementLayout` puts existing items first in both DOM and visual order. At 1280px and above, a 320px creation panel sits beside the list, with a 32px gap. Below that breakpoint, the list and form stack. Form fields fill their panel, labels have consistent spacing, and submit buttons fit their text. Lists and tables retain a minimum width of zero so a long value cannot widen the page; tables use their own horizontal scroll region.

`common/EmptyState` provides a contained, centred empty state. Errors must not simultaneously claim that the list is empty. Approvals shows a comment field only when pending work is loaded, and the empty queue offers Refresh. Knowledge and Memory section headings use the interface font; the serif face stays reserved for the chat greeting and sign-in.

## Settings detail

Where a form has a simple path and extra fields, the page offers Simple and Advanced. The choice is stored in `localStorage` under `ar-settings-mode`. Simple is the default. On Models, Simple is the provider name and the register action. Advanced also shows the base URL.

Detail screens put their Back action in the page header. Approvals, reviews and source creation use a bounded reading column; agent editing places instructions beside publishing, versions and test chat at desktop widths. On phones these panels stack. `detail-panel` supplies consistent padding, borders and wrapping. Radix tabs provide arrow-key navigation, and citation dialogs trap focus and close with Escape.

`DetailState` separates loading, failed and ready views. A failed fetch offers retry without exposing stale decision controls. Mutations disable their controls while pending and announce progress with `ActionStatus`. Completed approvals and reviews retain their result without an editable decision form. Saving must succeed before publishing; a failed save preserves the draft. Skills that the signed-in person cannot edit remain readable, including their advanced fields, with mutations disabled.

## Chat

The thread sits in a centred column. The welcome state pairs a serif heading with three starter cards. Conversation history has a separate quiet column on desktop and a disclosure on mobile. The composer uses subtle elevation and a labelled send control that is disabled for an empty message. The composer grows with the text, accepts a file, and sends on Enter. Shift+Enter inserts a line. Streaming keeps a caret, announces text through `aria-live="polite"` about twice a second, and does not pull the scroll position when the reader has moved up. Markdown, including fenced code with a copy control, is rendered in the thread. Copy and regenerate sit on the message.

## Agent catalogue

A prominent description-based builder entry appears only for users with `agents:create`. Agent cards show their description, status, version, owner, favourite toggle and available chat action. Search and status filters share one toolbar. Loading uses card-shaped skeletons, an empty filtered result offers Clear filters, and an error offers Try again. Disabled agents do not offer chat.

## Sign-in

The sign-in page offers the organisation account and the four seeded roles (`admin`, `builder`, `member`, `approver` at `@dev.local`). The Keycloak login theme under `deploy/compose/keycloak/themes/agentic` uses the same paper, ink and teal. Those theme files are CSS for Keycloak and are the one place a hex value is expected, because Keycloak does not read the web tokens.

The root route redirects to Chat, so SSO and direct visits enter the same workspace as development sign-in. A workspace session response of 401 sends signed-out visitors to Sign in, including direct links to detail pages. Network failures do not trigger sign-out.

## Bar

Empty, loading and error states, visible focus, labels on inputs, and layouts at 375 px and 1280 px are required. The quality bar is [ux-quality](ux-quality.md). Behaviour of the screens is [spec 19](../03-specs/19-web-app.md).
