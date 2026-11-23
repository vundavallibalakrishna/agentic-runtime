import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await signInAs(page, email);
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
}

test("an administrator invites a person, sees them waiting, and revokes", async ({ page }) => {
  await signIn(page, "admin@dev.local");
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "Invite people" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Invite", exact: true })).toBeDisabled();
  const address = `invited-${Date.now()}@example.test`;
  await page.getByLabel("Email addresses").fill(address);
  await page.getByRole("button", { name: "Invite 1 person" }).click();
  // The install the tests run on may or may not have a mail server: either way the screen
  // says what happened to the mail, and the person is listed as waiting.
  await expect(page.getByText(/^Mail (sent|not sent)$/)).toBeVisible();
  const waiting = page
    .getByRole("listitem")
    .filter({ hasText: address })
    .filter({
      has: page.getByRole("button", { name: "Revoke" }),
    });
  await expect(waiting).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
  await waiting.getByRole("button", { name: "Revoke" }).click();
  await expect(waiting).toHaveCount(0);
});

test("a person who may not manage users is not shown the invite form", async ({ page }) => {
  await signIn(page, "member@dev.local");
  await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "Invite people" })).toHaveCount(0);
});
