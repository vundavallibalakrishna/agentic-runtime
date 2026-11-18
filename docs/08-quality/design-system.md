# Design system

The web app has the look of an administration console: a light top bar, a light work surface, a light side column inside Settings and one blue accent. Density, alignment and a hairline do the work. Inter is the only interface face. The product stays industry-agnostic. Industry vocabulary does not appear in this chrome.

## Tokens

All colour, type, radius, shadow and motion values live in `apps/web/src/app/globals.css`. Feature code uses the CSS variables (`var(--primary)`, `var(--muted-foreground)`, `var(--scrim)`) and does not add hex colours. Syntax highlighting may apply a theme colour at runtime; that colour is not written into a component.

| Token | Use |
|---|---|
| `--background`, `--foreground` | Page |
| `--card` | Panels |
| `--sidebar`, `--sidebar-foreground`, `--sidebar-strong`, `--sidebar-muted`, `--sidebar-hover`, `--sidebar-border` | The side column inside Settings, which follows the theme: its surface, row text, prominent text, section labels, hovered row and outlines |
| `--muted`, `--muted-foreground` | Quiet surfaces and secondary text |
| `--primary`, `--primary-hover`, `--primary-foreground` | The one accent, its hovered shade and the label on it |
| `--border`, `--ring` | Hairlines and the focus ring |
| `--destructive` | A failed action |
| `--success`, `--warning` | A settled status and a waiting status, used through badge tones |
| `--scrim` | The layer behind a menu or the command palette |
| `--shadow`, `--shadow-xs`, `--shadow-composer`, `--radius` | Menus, subtle card elevation, composer elevation and corners |
| `--nav-active`, `--nav-active-foreground` | The selected navigation row and its text |
| `--motion` | Short transitions |

Light and dark are both specified. The theme choice is `system`, `light` or `dark`, stored in `localStorage` under `ar-theme`. The default is `light`; the system setting is followed only when a person chooses `system`. A small script in the document head applies the choice before paint. `prefers-reduced-motion: reduce` shortens animation and transitions.

## Status badges

`ui/Badge` takes a `tone`: `neutral`, `success`, `warning`, `danger` or `info`. A tone tints the badge with one token (a faint fill, a soft border, text in that colour) through the `.tone` classes in `globals.css`, so both themes follow. `statusTone` maps a status word from the API to a tone: published and completed are success, running and queued are info, draft and waiting are warning, failed and disabled are danger. A word it does not know stays neutral. Screens use `statusTone` and do not choose status colours themselves.

## Record lists

A list of records is one panel with a hairline between rows: the `row-list` class on the `ul`. Rows do not carry their own border, corner or background. An empty list draws nothing, so the screen's empty state stands alone. Tools, skills, routines, schedules, knowledge, memory, inbox, approvals, reviews, policies, quotas, channels, computers and evaluations use it. A status word in a row is a badge through `statusTone`. Card grids stay for things a person picks from side by side, such as connectors.

## Type

The faces are loaded with `next/font`: Inter for the interface and IBM Plex Mono for code. Titles use the `font-display` class, which is Inter at a heavier weight. The scale is `--text-xs` through `--text-3xl`, and unsized text is `--text-sm`. Corners follow one scale set in the theme block: 6 px for controls, `--radius` (8 px) for panels, 10 px for large surfaces.

## Shell

`AppShell` is the signed-in frame.

- A top bar with a mark, the product name and the workspace name under it, links to Chat, Agents and Settings, a new-chat action and a create-agent action. Chat and Agents use the full width of the window. This is the whole of what a person sees first: the product is mostly reached through its API, so the screens lead with a chat and the agents.
- Every other screen is under Settings. Settings opens a page that lists them grouped into Work, Build, Data and Admin, and shows the same groups in a collapsible side column on each of those screens. A screen is listed only when the session grants its permission. The create-agent action is visible only to builders.
- The screens under Settings are Inbox, Approvals, Runs, Tools, Skills, Routines, Schedules, Documents, Connectors, Connections, Knowledge, Memory, Profile, Channels, Evaluations, Platform health, Usage, Quotas, Models, Computers and Users, and the links an installed pack adds.
- The header shows the workspace and the signed-in email, a command palette (⌘K or Ctrl+K), and an account menu with the theme choice and sign-out.
- ⌘⇧O (Ctrl+Shift+O) starts a new chat.
- Below the `lg` breakpoint the top-bar links and the Settings groups move into a focus-trapped dialog over a scrim. Escape closes it and restores focus. Account choices use a keyboard-accessible menu.
- Search remains reachable on mobile. A skip link moves keyboard focus to the main content.

## Page layout

Management pages use one `PageHeader`: title and description on the left, page actions or the compact Simple/Advanced selector on the right. At narrow widths actions wrap below the description. A divider separates the page introduction from the work.

`common/ManagementLayout` puts existing items first in both DOM and visual order. At 1280px and above, a 320px creation panel sits beside the list, with a 32px gap. Below that breakpoint, the list and form stack. Form fields fill their panel, labels have consistent spacing, and submit buttons fit their text. Lists and tables retain a minimum width of zero so a long value cannot widen the page; tables use their own horizontal scroll region.

`common/EmptyState` provides a contained, centred empty state. Errors must not simultaneously claim that the list is empty. Approvals shows a comment field only when pending work is loaded, and the empty queue offers Refresh. Knowledge and Memory section headings use the interface font.

## Settings detail

Where a form has a simple path and extra fields, the page offers Simple and Advanced. The choice is stored in `localStorage` under `ar-settings-mode`. Simple is the default. On Models, Simple is the provider name and the register action. Advanced also shows the base URL.

Detail screens put their Back action in the page header. Approvals, reviews and source creation use a bounded reading column; agent editing places instructions beside publishing, versions and test chat at desktop widths. On phones these panels stack. `detail-panel` supplies consistent padding, borders and wrapping. Radix tabs provide arrow-key navigation, and citation dialogs trap focus and close with Escape.

`DetailState` separates loading, failed and ready views. A failed fetch offers retry without exposing stale decision controls. Mutations disable their controls while pending and announce progress with `ActionStatus`. Completed approvals and reviews retain their result without an editable decision form. Saving must succeed before publishing; a failed save preserves the draft. Skills that the signed-in person cannot edit remain readable, including their advanced fields, with mutations disabled.

## Chat

The thread sits in a centred column. The welcome state pairs a display heading with three starter cards. Conversation history has a separate quiet column on desktop and a disclosure on mobile. The composer uses subtle elevation and a labelled send control that is disabled for an empty message. The composer grows with the text, accepts a file, and sends on Enter. Shift+Enter inserts a line. Streaming keeps a caret, announces text through `aria-live="polite"` about twice a second, and does not pull the scroll position when the reader has moved up. Markdown, including fenced code with a copy control, is rendered in the thread. Copy and regenerate sit on the message. From the tablet width up, a right column holds the run-details panel (status badge, agent, model, duration, step and tool-call counts, each tool call with its status, and the trace link) above the Computer panel. The panel reads the latest run of the conversation, refreshes while the run is live and when the reply ends, and has loading and error states. Below that width the trace link sits above the composer.

## Agent catalogue

The catalogue is a table, one agent per row: name and description, status badge, owner, published version, then the chat action and the favourite toggle. The New agent button in the page header appears only for users with `agents:create`. Search and status filters share one toolbar. Loading uses row-shaped skeletons, an empty filtered result offers Clear filters, and an error offers Try again. Disabled agents do not offer chat. The table scrolls sideways in its own region on a narrow screen. The runs list is a table in the same style, with the run status as a badge.

## Documents and models

The document library is a table: title and file name, media type as the library recorded it, page count, a status badge and an Open action. Upload is a primary button in the page header that wraps the file input, so the input keeps its label and keyboard focus. The compare form sits under the table.

On Models, "What the product uses" is a table: the use with its name and explanation, the model picker, status badges (set is success, not set and needed is danger) and the row actions. A test result names its outcome in the success or failure colour. A provider shows whether its key is stored as a success or warning badge. A scroll region nested in a named section takes its own name, so the two landmarks stay distinct.

## Agent builder and editor

The builder is two columns from 1280 px: on the left the description box, the preview of the draft and the templates; on the right the form for filling in the agent by hand. Below that width they stack in the same order. The preview lists the draft's tools as badges. The editor shows the agent's status as a badge in the page header, and its publish, versions and test-chat panels stay in view while the form scrolls.

A long form carries the `form-sections` class: each `fieldset` directly inside it starts under a hairline with its legend as the section title. Checkboxes and radio buttons take the accent colour. The model picker on both screens lists the chat aliases the tenant has, read through `lib/model-aliases`; chat uses the same reader.

## Detail screens

A detail screen shows one record. Its status is a badge beside the back button in the page header. The facts about the record (trigger, type, pages, embedding model) are a label column and a value column through `common/Facts`, which leaves out a fact with no value; the chat run panel uses the same component. A block inside a panel starts with a small upper-case heading, the `panel-title` class. Lists inside a detail screen follow Record lists.

The routine screen puts the instructions and actions on the left and the facts on the right, with events below as a record list. The approval screen is one panel: the tool name, status and risk badges, then the request, the reasons and the decision, each under a hairline. A knowledge collection shows its facts above the tabs, groups the three ways of adding a document in one panel, and lists documents, passages found, sources and jobs as record lists. A library document keeps its facts and outline in a column that stays in view, shows passages as one divided panel, and puts Judge and Rewrite side by side. Comparison, check and rewrite results use badges for the kind of change, the verdict and the decision.

## Sign-in

The sign-in page offers the organisation account and the four seeded roles (`admin`, `builder`, `member`, `approver` at `@dev.local`). The Keycloak login theme under `deploy/compose/keycloak/themes/agentic` uses the same paper, ink and teal. Those theme files are CSS for Keycloak and are the one place a hex value is expected, because Keycloak does not read the web tokens.

The root route redirects to Chat, so SSO and direct visits enter the same workspace as development sign-in. A workspace session response of 401 sends signed-out visitors to Sign in, including direct links to detail pages. Network failures do not trigger sign-out.

## Bar

Empty, loading and error states, visible focus, labels on inputs, and layouts at 375 px and 1280 px are required. The quality bar is [ux-quality](ux-quality.md). Behaviour of the screens is [spec 19](../03-specs/19-web-app.md).
