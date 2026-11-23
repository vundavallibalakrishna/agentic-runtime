import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

// A person who cannot sign in has no session, so these pages must open without one.
test("the password reset pages open for someone who is signed out", async ({ page }) => {
  await page.goto("/forgot-password");
  await expect(page).toHaveURL(/\/forgot-password$/);
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible();
  const forgot = await new AxeBuilder({ page }).analyze();
  expect(forgot.violations).toEqual([]);

  await page.goto("/reset-password");
  await expect(page).toHaveURL(/\/reset-password$/);
  await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
  await expect(page.getByText("This page needs the link from your reset mail.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Ask for a new link" })).toHaveAttribute(
    "href",
    "/forgot-password",
  );
});

test("a link that is not valid says so and changes nothing", async ({ page }) => {
  await page.goto("/reset-password?token=not-a-real-token");
  await expect(page.getByRole("heading", { name: "Choose a new password" })).toBeVisible();
  const form = await new AxeBuilder({ page }).analyze();
  expect(form.violations).toEqual([]);
  await page.getByLabel("New password", { exact: true }).fill("a-new-password");
  await page.getByLabel("New password again").fill("another-password");
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText("The two passwords are not the same.")).toBeVisible();
  await page.getByLabel("New password again").fill("a-new-password");
  await page.getByRole("button", { name: "Set password" }).click();
  await expect(page.getByText("This reset link is not valid. Ask for a new one.")).toBeVisible();
});

test("the invitation page opens for someone who is signed out and refuses a bad link", async ({
  page,
}) => {
  await page.goto("/invite");
  await expect(page).toHaveURL(/\/invite$/);
  await expect(page.getByRole("heading", { name: "Accept your invitation" })).toBeVisible();
  await expect(page.getByText("This page needs the link from your invitation mail.")).toBeVisible();
  const empty = await new AxeBuilder({ page }).analyze();
  expect(empty.violations).toEqual([]);

  await page.goto("/invite?token=not-a-real-token");
  await expect(page.getByText(/This invitation is not valid/)).toBeVisible();
});
