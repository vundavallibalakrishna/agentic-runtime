import { test as base, expect, type Locator, type Page } from "@playwright/test";

/**
 * The test object every e2e spec imports instead of `@playwright/test`.
 *
 * It adds one automatic behaviour: before a retried attempt it resets the harness's demo
 * tenant once, so the retry replays against the seeded baseline rather than the rows the
 * failed attempt left behind. The harness keeps a single in-memory tenant for the whole
 * run, so without this a serial flow that fails and retries sees a second copy of what it
 * created (two "Desk note"s, two connections), which turns a recoverable flake into a hard
 * failure. On the first attempt this does nothing, so first-attempt behaviour is unchanged.
 *
 * It also makes every stored screenshot show the settled screen. A spec switches theme and
 * takes the picture straight away, and the app fades colours over 120 ms, so without this a
 * dark picture catches links, inputs and buttons half-way between the two themes.
 *
 * The reset is done once per (spec file, retry): Playwright re-runs a whole `serial` group
 * from its first test, and each test in that re-run carries the same retry number, so the
 * first one resets and the rest of the group replay on the clean tenant it left.
 */
const RESET_PATH = "/api/v1/test/reset";
const alreadyReset = new Set<string>();

export const test = base.extend<{ freshTenantOnRetry: undefined }>({
  freshTenantOnRetry: [
    async ({ request }, use) => {
      const info = test.info();
      if (info.retry > 0) {
        const tag = `${info.file}#${info.retry}`;
        if (!alreadyReset.has(tag)) {
          alreadyReset.add(tag);
          const response = await request.post(RESET_PATH);
          if (!response.ok()) {
            throw new Error(`demo tenant reset failed: HTTP ${response.status()}`);
          }
        }
      }
      await use(undefined);
    },
    { auto: true },
  ],
  page: async ({ page }, use) => {
    const shoot = page.screenshot.bind(page);
    page.screenshot = (options) => shoot({ animations: "disabled", ...options });
    await use(page);
  },
});

/**
 * Open the tool calls on the page once `what` has arrived in one of them, and wait until
 * it can be seen. A tool call is one line under an answer until a person opens it, so a
 * check on what a tool returned opens it first, as a person would. `what` is text, or a
 * locator for the element.
 *
 * A reply draws its tool calls twice: while it is being written, and again when it is
 * finished. The second drawing is closed again, so opening once can be undone a moment
 * later. This opens and looks until the text stays in view.
 */
export async function openToolCall(page: Page, what: string | RegExp | Locator, timeout = 20_000) {
  const wanted = typeof what === "string" || what instanceof RegExp ? page.getByText(what) : what;
  // A closed tool call draws its details only once it is opened, so the cards are opened
  // until what was asked for appears in one of them.
  await expect(page.getByTestId("tool-call").first()).toBeAttached({ timeout });
  await expect(async () => {
    await page.getByTestId("tool-call").evaluateAll((cards) => {
      for (const card of cards) if (!card.hasAttribute("open")) card.setAttribute("open", "");
    });
    await expect(wanted.first()).toBeVisible({ timeout: 1_000 });
    // Still open after the reply has had time to finish and draw itself again.
    await page.waitForTimeout(500);
    await expect(wanted.first()).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout });
}

export { expect, type Page };
