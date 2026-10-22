import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m5";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page, email = "admin@dev.local") {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${email}` }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
}

async function capture(page: Page, name: string) {
  for (const theme of ["light", "dark"] as const) {
    for (const size of [
      { width: 1280, height: 800, label: "desktop" },
      { width: 375, height: 812, label: "mobile" },
    ]) {
      await page.setViewportSize({ width: size.width, height: size.height });
      await page.evaluate((choice) => {
        localStorage.setItem("ar-theme", choice);
        document.documentElement.classList.toggle("dark", choice === "dark");
        document.documentElement.style.colorScheme = choice;
      }, theme);
      await page.screenshot({
        path: `${shots}/${size.label}-${theme}-${name}.png`,
        fullPage: true,
      });
    }
  }
  await page.setViewportSize({ width: 1280, height: 800 });
}

test("approve a pet, sign a review, and author a policy", async ({ page }) => {
  await signIn(page, "approver@dev.local");
  const approverId = await page.evaluate(async () => {
    const response = await fetch("/api/v1/auth/session", { credentials: "include" });
    const body = (await response.json()) as { user: { id: string } };
    return body.user.id;
  });
  await signIn(page);
  await page.goto("/chat?agent=desk");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await page.getByLabel("Message").fill("Create a pet named Fido");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval before this tool runs.").first()).toBeVisible({
    timeout: 20_000,
  });
  const conversation = new URL(page.url()).searchParams.get("conversation");
  expect(conversation).toBeTruthy();

  await page.goto("/approvals");
  await expect(page.getByRole("heading", { name: "Approvals" })).toBeVisible();
  await expect(page.getByText("petstore.create_pet").first()).toBeVisible();
  const inbox = await new AxeBuilder({ page }).analyze();
  expect(inbox.violations).toEqual([]);
  await capture(page, "inbox");
  await page.getByRole("button", { name: "Approve" }).first().click();
  await expect(page.getByText("Nothing is waiting for you.")).toBeVisible({ timeout: 20_000 });

  await page.goto(`/chat?conversation=${conversation}`);
  await expect(page.getByText(/Created pet \d+\./).first()).toBeVisible({ timeout: 20_000 });
  await capture(page, "pet-created");

  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
  const reviews = await new AxeBuilder({ page }).analyze();
  expect(reviews.violations).toEqual([]);
  await page.getByRole("link", { name: /artifact/ }).click();
  await expect(page.getByText("I reviewed the sample output.")).toBeVisible();
  await page.getByRole("button", { name: "Sign" }).click();
  await expect(page.getByText("signed")).toBeVisible({ timeout: 20_000 });
  await capture(page, "review-signed");

  await page.goto("/admin/policies");
  await expect(page.getByRole("heading", { name: "Policies" })).toBeVisible();
  await page.getByLabel("Name").fill("Deletes wait");
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByLabel("Document").fill(
    JSON.stringify({
      rules: [
        {
          id: "del",
          effect: "requireApproval",
          message: "confirm the delete",
          match: { tools: ["petstore.delete_pet"] },
          approval: { approvers: { mode: "users", users: [approverId] } },
        },
      ],
    }),
  );
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByRole("heading", { name: "Deletes wait" })).toBeVisible();
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText("active").first()).toBeVisible({ timeout: 20_000 });
  const policies = await new AxeBuilder({ page }).analyze();
  expect(policies.violations).toEqual([]);
  await capture(page, "policies");

  await page.goto(`/chat?agent=desk&conversation=${conversation}`);
  await expect(page.getByText(/Created pet \d+\./).first()).toBeVisible();
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await page.getByLabel("Message").fill("Delete pet 1");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval before this tool runs.").first()).toBeVisible({
    timeout: 20_000,
  });
  await signIn(page, "approver@dev.local");
  await page.goto("/approvals");
  await page.getByRole("link", { name: "petstore.delete_pet" }).click();
  await expect(page.getByRole("button", { name: "Confirm it is you" })).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("approved").first()).toBeVisible({ timeout: 20_000 });
  await signIn(page);
  await page.goto(`/chat?conversation=${conversation}`);
  await expect(page.getByText(/Deleted pet 1\./).first()).toBeVisible({ timeout: 20_000 });
});
