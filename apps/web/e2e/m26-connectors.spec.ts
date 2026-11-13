import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m26";

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

test("connector catalog and a setup page", async ({ page }) => {
  await signIn(page);
  await page.goto("/connectors");
  await expect(page.getByRole("heading", { name: "Connectors", exact: true })).toBeVisible();
  await expect(page.getByText("Unit", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Contract", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Live", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Ready", { exact: true })).toHaveCount(0);
  await page.getByLabel("Search connectors").fill("notion");
  await expect(page.getByRole("link", { name: /Notion/ })).toBeVisible();
  await capture(page, "catalog");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  await page.getByRole("link", { name: /Notion/ }).click();
  await expect(page.getByRole("heading", { name: "Notion" })).toBeVisible();
  await expect(page.getByText("Unit", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Not offered to an agent").first()).toBeVisible();
  await expect(page.getByText("Built", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Open the provider's app page" })).toBeVisible();
  await expect(page.getByText("Asks first").first()).toBeVisible();
  await capture(page, "notion");
});
