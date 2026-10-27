import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("home opens chat after sign-in", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await page.goto("/");
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
  const results = await new AxeBuilder({ page }).analyze();
  expect(results.violations).toEqual([]);
});

test("a signed-out detail link opens sign-in", async ({ page }) => {
  await page.goto("/agents/assistant");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Sign in", exact: true })).toBeVisible();
});

test("healthz returns ok", async ({ request }) => {
  const response = await request.get("/healthz");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});
