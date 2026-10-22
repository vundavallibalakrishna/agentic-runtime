import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m6";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
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

test("chart a spreadsheet and review computers", async ({ page }) => {
  await signIn(page);
  await page.goto("/chat?agent=revenue-analyst");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Revenue analyst");
  await page.getByLabel("Message").fill("Analyse the attached CSV and chart revenue by month");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("revenue-by-month.png").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("img", { name: "revenue-by-month.png" })).toBeVisible({
    timeout: 30_000,
  });
  const chat = await new AxeBuilder({ page }).analyze();
  expect(chat.violations).toEqual([]);
  await capture(page, "chart");

  await page.evaluate(() => {
    localStorage.setItem("ar-theme", "light");
  });
  await page.goto("/admin/sandboxes");
  await expect(page.getByRole("heading", { name: "Computers", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Python data" })).toBeVisible();
  await page.addStyleTag({
    content: "button,a,input,textarea{transition:none !important}",
  });
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByLabel("Allow package installs")).toBeVisible();
  await page.evaluate(() => {
    for (const animation of document.getAnimations()) {
      animation.finish();
    }
  });
  const admin = await new AxeBuilder({ page }).analyze();
  expect(admin.violations).toEqual([]);
  await capture(page, "computers");
});
