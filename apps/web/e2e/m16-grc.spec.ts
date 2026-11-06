import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

test.use({ locale: "en-US" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
}

test("the GRC pack stays out of the default workspace", async ({ page }) => {
  await signIn(page);
  await expect(page.getByRole("link", { name: "GRC" })).toHaveCount(0);
  await page.goto("/grc");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "GRC" })).toHaveCount(0);
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
});
