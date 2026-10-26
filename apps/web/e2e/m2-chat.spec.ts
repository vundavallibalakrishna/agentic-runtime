import { expect, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

test("sign in, chat, stop, empty and error states", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  for (const email of [
    "admin@dev.local",
    "builder@dev.local",
    "member@dev.local",
    "approver@dev.local",
  ]) {
    await expect(page.getByRole("button", { name: `Sign in as ${email}` })).toBeVisible();
  }
  await page.screenshot({ path: `${shots}/01-login.png`, fullPage: true });
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await expect(page.getByText("admin@dev.local")).toBeVisible();
  await expect(page.getByText("Weekly status for the platform")).toBeVisible();
  await page.screenshot({ path: `${shots}/02-empty-chat.png`, fullPage: true });

  await page.getByRole("button", { name: "Write something Draft a short status update" }).click();
  await expect(page.getByText(/fake:/i).first()).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${shots}/03-streamed-reply.png`, fullPage: true });
  await page.getByRole("button", { name: "Regenerate" }).click();
  await expect(page.getByText(/fake:/i).first()).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${shots}/03b-regenerate.png`, fullPage: true });

  await page.getByLabel("Message").fill("Please answer slowly");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible({ timeout: 10_000 });
  await page.screenshot({ path: `${shots}/04-stopped.png`, fullPage: true });

  await page.goto("/admin/models");
  await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
  await expect(page.getByText("fake-llm")).toBeVisible();
  await page.screenshot({ path: `${shots}/05-models.png`, fullPage: true });

  await page.route("**/api/v1/conversations", (route) => route.abort());
  await page.goto("/chat");
  await expect(page.getByRole("alert").filter({ hasText: /failed|loaded|fetch/i })).toBeVisible();
  await page.screenshot({ path: `${shots}/06-error.png`, fullPage: true });
});

test("keycloak sign-in walks username and then password", async ({ page, context }) => {
  if (process.env.AR_E2E_KEYCLOAK !== "1") {
    return;
  }
  for (const email of [
    "admin@dev.local",
    "builder@dev.local",
    "member@dev.local",
    "approver@dev.local",
  ]) {
    await context.clearCookies();
    await page.goto("/login");
    await page.getByRole("link", { name: "Continue with SSO" }).click();
    const password = page.locator("input[name='password']");
    const username = page.locator("input[name='username']");
    await username.waitFor({ timeout: 20_000 });
    if (await username.isVisible()) {
      await username.fill(email);
    }
    if (!(await password.isVisible())) {
      await page.getByRole("button", { name: /sign in/i }).click();
    }
    await password.fill("dev-password");
    await page.getByRole("button", { name: /sign in/i }).click();
    await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(email)).toBeVisible();
    await page.getByRole("button", { name: /Dev / }).click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  }
});
