# UX quality bar

Applies to every screen in `apps/web` and to pack pages mounted in the shell. Normative UI behaviour: [spec 19](../03-specs/19-web-app.md). Principles: [principles §2](../00-overview/principles.md#2-outstanding-ui-and-presentation).

A task that adds a page is not done until the checks below pass.

## 1. Design system

- Components come from `src/components/ui` (shadcn) and `src/components/common`. A one-off control needs a reason in the task.
- Type, colour, radius, and spacing come from the tokens in `app/globals.css`. No new hex values in a feature.
- Light and dark both look finished. Contrast meets WCAG 2.1 AA (4.5:1 for text).
- Motion is short and can be turned off with `prefers-reduced-motion`.

## 2. States

Every data view has all four:

| State | What the person sees |
|---|---|
| Loading | A skeleton the same shape as the content, not a blank page and not a lone spinner |
| Empty | One sentence, and the single next action |
| Error | What failed in plain language, and a retry |
| Ready | The work, with the primary action obvious |

Streaming chat keeps a caret, announces tokens with `aria-live="polite"` throttled to a few times a second, and does not yank the scroll position.

## 3. Creating an agent

The first control on `/agents/new` is a text field. The placeholder is a full instruction, such as "create an agent that reviews vendor SOC 2 reports and flags gaps". Submitting starts the built-in builder. Template cards sit below, visually secondary. See [spec 19 §5.1](../03-specs/19-web-app.md#51-natural-language-builder).

## 4. Accessibility and responsive layout

- Keyboard reaches every action. Focus is visible.
- Inputs have labels. Icon-only buttons have an accessible name.
- Layouts are usable at 375 px width and at 1280 px. Tables become stacked rows or a horizontal scroll region with a caption, not a clipped page.
- Playwright runs axe on the page.

## 5. Onboarding

After the first login the shell shows one sentence of what the product does and the natural-language field. It does not open settings. Settings stay available from the user menu.

## 6. Copy

Sentences, not labels stacked on labels. Errors say what to do next. No industry jargon in core chrome. Pack pages may use the pack's vocabulary.
