import { expect, type Page, test } from "@playwright/test";

test.use({ locale: "en-US" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
}

test("workflow routes stay parked", async ({ page }) => {
  await signIn(page);
  await page.goto("/grc/workflows");
  await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "GRC workflows" })).toHaveCount(0);
});
