import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m10";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
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

test("routines schedule, run now, and stay accessible", async ({ page }) => {
  await signIn(page);
  await page.goto("/routines");
  await expect(page.getByRole("heading", { name: "Routines" })).toBeVisible();
  await expect(page.getByText("Weekly digest", { exact: true })).toBeVisible();
  await expect(page.getByText("Every Monday 09:00 IST")).toBeVisible();
  await capture(page, "list");

  await page.getByLabel("Name").fill("Launch reminder");
  await page.getByLabel("Instructions").fill("Remind the team that the launch notes are due.");
  await page.getByRole("button", { name: "Preview schedule" }).click();
  await expect(page.getByText("Every Monday 09:00 IST").nth(1)).toBeVisible();
  await page.getByRole("button", { name: "Create a routine" }).click();
  await expect(page.getByRole("heading", { name: "Launch reminder" })).toBeVisible();
  await page.getByRole("button", { name: "Run now" }).click();
  await expect(page.getByText("Run started.")).toBeVisible();
  await expect(page.getByText("manual")).toBeVisible();
  await capture(page, "detail");

  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText("Paused.")).toBeVisible();
  await expect(page.getByText("paused · manual")).toBeVisible();
  await page.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText("Resumed.")).toBeVisible();
  await expect(page.getByText("active", { exact: true })).toBeVisible();

  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});
