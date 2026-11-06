import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

test.use({ locale: "en-US" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
}

test("monitoring routes stay parked", async ({ page }) => {
  await signIn(page);
  for (const path of ["/grc/tests", "/grc/findings", "/grc/connectors"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { name: "Page not found" })).toBeVisible();
  }
});
