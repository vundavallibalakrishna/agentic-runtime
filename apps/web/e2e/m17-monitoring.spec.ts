import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m17";

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
  for (const theme of ["light", "dark"] as const) {
    for (const size of [
      { width: 1280, height: 800, label: "desktop" },
      { width: 375, height: 812, label: "mobile" },
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
  await page.setViewportSize({ width: 1280, height: 800 });
}

test("run a control test and close a finding with verified evidence", async ({ page }) => {
  await signIn(page);
  await page.goto("/grc/tests");
  await expect(page.getByRole("heading", { name: "GRC" })).toBeVisible();
  await expect(page.getByRole("button", { name: /aws-config/ })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("Fail").first()).toBeVisible();
  await capture(page, "tests");
  await page.goto("/grc/findings");
  await expect(page.getByRole("button", { name: /aws-config failed/ })).toBeVisible();
  await page.getByLabel("Evidence item").selectOption({ index: 0 });
  await page.getByRole("button", { name: "Close finding" }).click();
  await expect(page.getByText("Closure needs a verified evidence item.")).toBeVisible();
  await capture(page, "findings");
  await page.getByLabel("Evidence item").selectOption({ label: "grc_aws" });
  await page.getByRole("button", { name: "Close finding" }).click();
  await expect(page.getByText("Finding closed.")).toBeVisible();
  await expect(page.getByText("Closed").first()).toBeVisible();
  await page.goto("/grc/connectors");
  await expect(page.getByRole("heading", { name: "AWS" })).toBeVisible();
  await expect(page.getByText("Read only").first()).toBeVisible();
  await expect(page.getByText("Writes wait for approval").first()).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await capture(page, "connectors");
});
