import { expect, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

test("research mode streams a cited report and a sources panel", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await page.getByRole("button", { name: "Research" }).click();
  await expect(page.getByRole("button", { name: "Research" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByLabel("Message").fill("What do the stored notes say about kites?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/\[1\]/).first()).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${shots}/stage10-research.png`, fullPage: true });
});
