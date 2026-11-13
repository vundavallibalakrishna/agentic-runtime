import { test as base, expect, type Page } from "@playwright/test";

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
});

export { expect, type Page };
