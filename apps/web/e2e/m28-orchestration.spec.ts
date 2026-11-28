import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m28";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await page.waitForURL(/\/chat/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Chat", exact: true })).toBeVisible();
}

async function capture(page: Page, name: string) {
  mkdirSync(shots, { recursive: true });
  for (const theme of ["light", "dark"] as const) {
    for (const size of [
      { width: 1440, height: 900, label: "desktop" },
      { width: 390, height: 844, label: "mobile" },
    ]) {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.evaluate((choice) => {
        localStorage.setItem("ar-theme", choice);
        document.documentElement.classList.toggle("dark", choice === "dark");
        document.documentElement.style.colorScheme = choice;
      }, theme);
      await page.screenshot({
        path: `${shots}/${size.label}-${theme}-${name}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
}

test("schedules, inbox, runs and agent call selection", async ({ page }) => {
  await signIn(page);
  await page.goto("/schedules");
  await expect(page.getByRole("heading", { name: "Schedules", exact: true })).toBeVisible();
  const whenToRun = page.getByRole("group", { name: "When to run", exact: true });
  await expect(whenToRun.getByRole("combobox", { name: "Timezone", exact: true })).toBeVisible();
  await expect(
    whenToRun.getByText(/^Times use this timezone, including its daylight saving changes\./),
  ).toBeVisible();
  await capture(page, "schedules");
  const schedulesAxe = await new AxeBuilder({ page }).analyze();
  expect(schedulesAxe.violations).toEqual([]);

  await page.goto("/inbox");
  await expect(page.getByRole("heading", { name: "Inbox", exact: true })).toBeVisible();
  await expect(page.getByText("Nothing is waiting on you.")).toBeVisible();
  await capture(page, "inbox");

  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs", exact: true })).toBeVisible();
  await capture(page, "runs");

  await page.goto("/agents");
  await page.locator('a[href^="/agents/"]:not([href="/agents/new"])').first().click();
  const canCall = page.locator("summary").filter({ hasText: "Can call agents" });
  await expect(canCall).toBeVisible({ timeout: 20_000 });
  await canCall.click();
  await expect(page.getByLabel("Can ask a person", { exact: true })).toBeVisible();
  await capture(page, "agent-editor");
});
