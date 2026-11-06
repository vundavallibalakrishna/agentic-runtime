import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signInAs } from "./support/sign-in";

test("the sign-in page offers one way in and is accessible", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Continue with SSO" })).toBeVisible();
  await expect(page.getByRole("main").getByRole("button")).toHaveCount(0);
  // The dev server may still be compiling the page it just served.
  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  await page.goto("/login?error=user_suspended");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Your account is suspended. Ask an administrator.",
  );
});

test("a visitor who is not signed in is sent to the sign-in page", async ({ page }) => {
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/login$/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("a failed session check replaces the page with an error and a retry", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();

  let failing = true;
  await page.route("**/api/v1/auth/session", async (route) => {
    if (failing) {
      await route.fulfill({ status: 500, contentType: "application/json", body: "{}" });
      return;
    }
    await route.continue();
  });
  await page.goto("/agents");
  await expect(
    page.getByRole("heading", { name: "We could not check your sign-in" }),
  ).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Try again");
  await expect(page.getByRole("heading", { name: "Agents" })).toHaveCount(0);
  await expect(page.getByText("Assistant", { exact: true })).toHaveCount(0);
  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  failing = false;
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { name: "Agents" }).first()).toBeVisible();
  await expect(page.getByText("Assistant", { exact: true }).first()).toBeVisible();
});
