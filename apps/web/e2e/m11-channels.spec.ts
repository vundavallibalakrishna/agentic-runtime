import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m11";

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

test("channels list, test connection, link profile, and stay accessible", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Dev Admin" }).click();
  await page.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
  await expect(page.getByText("U-ADMIN")).toBeVisible();
  await capture(page, "profile");

  await page.goto("/admin/channels");
  await expect(page.getByRole("heading", { name: "Channels" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workspace Slack" })).toBeVisible();
  await expect(page.getByText("The weekly digest is ready for #platform.")).toBeVisible();
  await capture(page, "list");

  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByLabel("Routing")).toBeVisible();
  await page.getByRole("button", { name: "Simple" }).click();

  await page.getByLabel("Name").fill("Desk Slack");
  await page.getByLabel("Bot token").fill("xoxb-desk");
  await page.getByRole("button", { name: "Save channel" }).click();
  await expect(page.getByText("Channel saved.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Desk Slack" })).toBeVisible();

  await page.getByRole("button", { name: "Test connection" }).first().click();
  await expect(page.getByText("Connection checked.")).toBeVisible();
  await capture(page, "tested");

  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});
