import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m21";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const button = page.getByRole("button", { name: "Sign in as admin@dev.local" });
  await expect(button).toBeVisible();
  await button.click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
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

test("chat is home, an agent can be created, and GRC stays parked", async ({ page }) => {
  await signIn(page);
  await expect(page.locator("#agent-picker")).toBeVisible();
  await expect(page.locator("#model-picker")).toBeVisible();
  await expect(page.getByRole("link", { name: "GRC" })).toHaveCount(0);
  await capture(page, "chat");

  await page.goto("/agents/new");
  await expect(page.getByRole("heading", { name: "New agent" })).toBeVisible();
  await page.getByLabel("Name").fill("Desk note");
  await page
    .getByLabel("Instructions")
    .fill("Keep notes short and use the checkpoint tool when asked.");
  await capture(page, "builder");
  await page.getByRole("button", { name: "Create and use" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });

  await page.goto("/agents");
  await expect(page.getByText("Desk note")).toBeVisible({ timeout: 20_000 });
  await capture(page, "agents");

  for (const [path, name] of [
    ["/tools", "tools"],
    ["/skills", "skills"],
    ["/connections", "connectors"],
    ["/runs", "runs"],
    ["/admin/models", "models"],
    ["/settings/profile", "settings"],
  ] as const) {
    await page.goto(path);
    await expect(page.getByRole("heading").first()).toBeVisible();
    await capture(page, name);
  }

  await page.goto("/grc");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await capture(page, "parked");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
});
