import { expect, test } from "./support/harness";

test("the review queue asks a signed-out person to sign in", async ({ page }) => {
  await page.goto("/reviews");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});
