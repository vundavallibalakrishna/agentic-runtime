import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m14";

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

test("assurance desk, guest portal and export stay usable", async ({ page }) => {
  await signIn(page);
  await page.goto("/admin/assurance");
  await expect(page.getByRole("heading", { name: "Assurance" })).toBeVisible();
  await page.getByLabel("Note").fill("Desk note");
  await page.getByRole("button", { name: "Seal evidence" }).click();
  await expect(page.getByText("Evidence sealed.")).toBeVisible();
  await expect(page.getByText("desk")).toBeVisible();
  await page.getByRole("tab", { name: "Holds" }).click();
  await expect(page.getByText("Someone else with hold access must be the approver.")).toBeVisible();
  await page.getByRole("tab", { name: "Retention" }).click();
  await expect(page.getByText("evidence_item")).toBeVisible();
  await page.getByRole("tab", { name: "Guests" }).click();
  await expect(page.getByRole("heading", { name: "Invite a guest" })).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await capture(page, "assurance");
  await page.goto("/guest");
  await expect(page.getByRole("heading", { name: "Guest access" })).toBeVisible();
  await capture(page, "guest");
});
