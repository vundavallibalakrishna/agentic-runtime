import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await signInAs(page, email);
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
}

test("an administrator suspends a person, who is shut out, and lets them back in", async ({
  page,
  browser,
}) => {
  await signIn(page, "admin@dev.local");
  await page.goto("/admin/users");
  const row = page.getByRole("row").filter({ hasText: "approver@dev.local" });
  await expect(row.getByText("Active")).toBeVisible();
  // The administrator's own row has no Suspend.
  const own = page.getByRole("row").filter({ hasText: "admin@dev.local" });
  await expect(own.getByRole("button")).toHaveCount(0);

  await row.getByRole("button", { name: /^Suspend/ }).click();
  await expect(row.getByText(/signed out at once/)).toBeVisible();
  const asked = await new AxeBuilder({ page }).analyze();
  expect(asked.violations).toEqual([]);
  await row.getByRole("button", { name: "Yes, suspend" }).click();
  await expect(row.getByText("Suspended")).toBeVisible();

  // The suspended person cannot sign in.
  const other = await browser.newContext();
  const theirs = await other.newPage();
  await theirs.goto("/login");
  await theirs.getByLabel("Email").fill("approver@dev.local");
  await theirs.getByLabel("Password").fill("dev-password");
  await theirs.getByRole("button", { name: /sign in/i }).click();
  await expect(theirs.getByRole("alert")).toBeVisible();
  await expect(theirs).toHaveURL(/\/login/);
  await other.close();

  await row.getByRole("button", { name: /^Let .* back in$/ }).click();
  await expect(row.getByText("Active")).toBeVisible();
  const done = await new AxeBuilder({ page }).analyze();
  expect(done.violations).toEqual([]);
});

test("a person who may not manage users sees no Suspend", async ({ page }) => {
  await signIn(page, "member@dev.local");
  await page.goto("/admin/users");
  await expect(page.getByRole("button", { name: /^Suspend/ })).toHaveCount(0);
});
