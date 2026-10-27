import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("tenant choice and platform health fit in both themes and recover from failure", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
  for (const theme of ["light", "dark"]) {
    for (const width of [375, 1280]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate((value) => localStorage.setItem("ar-theme", value), theme);
      for (const path of ["/select-tenant", "/platform/health"]) {
        await page.goto(path);
        await expect(page.locator("main h1")).toBeVisible();
        await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
          true,
        );
        expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      }
    }
  }
  await page.route("**/api/v1/meta", (route) =>
    route.fulfill({ status: 503, json: { detail: "Unavailable" } }),
  );
  await page.reload();
  await expect(
    page.getByRole("alert").filter({ hasText: "The API did not respond." }),
  ).toBeVisible();
  await expect(page.getByText("The API is responding.")).toHaveCount(0);
  await page.unroute("**/api/v1/meta");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByText("The API is responding.")).toBeVisible();
});
