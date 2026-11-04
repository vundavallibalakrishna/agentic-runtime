import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m28";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const button = page.getByRole("button", { name: "Sign in as admin@dev.local" });
  await expect(button).toBeVisible();
  await Promise.all([page.waitForURL(/\/chat/, { timeout: 30_000 }), button.click()]);
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
  await expect(page.getByText("Cron is evaluated in this time zone.")).toBeVisible();
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
  await expect(page.getByText("Can call agents")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Can ask a person")).toBeVisible();
  await capture(page, "agent-editor");
});
