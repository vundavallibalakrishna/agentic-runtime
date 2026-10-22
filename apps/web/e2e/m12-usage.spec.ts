import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m12";

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

test("usage charts, quotas, and a blocked chat stay accessible", async ({ page }) => {
  let created = "";
  try {
    await signIn(page);
    await page.goto("/admin/usage");
    await expect(page.getByRole("heading", { name: "Usage" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Export CSV" })).toBeVisible();
    await expect(page.getByText("36,000").first()).toBeVisible();
    await capture(page, "usage");

    await page.goto("/admin/quotas");
    await expect(page.getByRole("heading", { name: "Quotas" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "model_tokens · day" })).toBeVisible();
    await capture(page, "quotas");

    await page.getByRole("button", { name: "Advanced" }).click();
    await expect(page.getByLabel("When full")).toBeVisible();
    await page.getByRole("button", { name: "Simple" }).click();

    await page.getByLabel("Limit").fill("0");
    await page.getByRole("button", { name: "Save quota" }).click();
    await expect(page.getByText("Quota saved.")).toBeVisible();
    created = "0";

    await page.getByRole("button", { name: "Dev Admin" }).click();
    await page.getByRole("menuitem", { name: "Profile" }).click();
    await expect(page.getByRole("heading", { name: "My usage" })).toBeVisible();
    await capture(page, "profile");

    await page.goto("/chat");
    await page.getByLabel("Message").fill("Show the weekly numbers");
    await page.getByRole("button", { name: "Send" }).click();
    const blocked = page.getByRole("alert").filter({ hasText: "Quota reached" });
    await expect(blocked).toBeVisible({ timeout: 20_000 });
    await expect(blocked).toContainText("is 0");
    await capture(page, "blocked");

    const result = await new AxeBuilder({ page }).analyze();
    expect(result.violations).toEqual([]);
  } finally {
    if (created) {
      await page.goto("/admin/quotas");
      const card = page.locator("li").filter({ hasText: "0 / 0" });
      if ((await card.count()) > 0) {
        await card.getByRole("button", { name: "Remove" }).click();
        await expect(page.getByText("Quota removed.")).toBeVisible();
      }
    }
  }
});
