import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m13";

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

test("observability, evaluations and platform health stay accessible", async ({ page }) => {
  await signIn(page);
  await page.goto("/admin/usage");
  await expect(page.getByRole("heading", { name: "Usage" })).toBeVisible();
  await expect(page.getByText("Operations")).toBeVisible();
  await capture(page, "usage");

  await page.goto("/admin/evals");
  await expect(page.getByRole("heading", { name: "Evaluation library" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Prompt injection" })).toBeVisible();
  await page.getByRole("button", { name: "Run suite" }).first().click();
  await expect(page.getByText("tool-output-injection")).toBeVisible({ timeout: 20_000 });
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
  await capture(page, "evals");

  await page.goto("/platform/health");
  await expect(page.getByRole("heading", { name: "Platform health" })).toBeVisible();
  await expect(page.getByText("postgres")).toBeVisible();
  await capture(page, "health");
});
