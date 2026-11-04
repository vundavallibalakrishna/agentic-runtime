import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m29";

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

test("expose tab shows a key once and a public test console", async ({ page }) => {
  await signIn(page);
  await page.goto("/agents");
  await page.locator('a[href^="/agents/"]:not([href="/agents/new"])').first().click();
  await expect(page).toHaveURL(/\/agents\/[^/]+$/, { timeout: 20_000 });
  await expect(page.getByRole("tab", { name: "Expose" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("tab", { name: "Expose" }).click();
  await expect(page.getByText("No API keys yet.")).toBeVisible();
  await capture(page, "expose-empty");
  const emptyAxe = await new AxeBuilder({ page }).analyze();
  expect(emptyAxe.violations).toEqual([]);

  await page.getByLabel("Key label").fill("Desk");
  await page.getByRole("button", { name: "Create key" }).click();
  await expect(page.getByText("Copy this key now. It is shown once.")).toBeVisible();
  await expect(page.getByText("Send through the API")).toBeVisible();
  await capture(page, "expose-key");

  await page.getByRole("button", { name: "Send through the API" }).click();
  await expect(page.getByRole("region", { name: "Raw response" })).toContainText(/output|status/, {
    timeout: 60_000,
  });
  await capture(page, "expose-console");
});
