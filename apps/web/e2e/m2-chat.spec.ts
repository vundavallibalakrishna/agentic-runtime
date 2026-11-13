import { expect, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

test("sign in, chat, stop, empty and error states", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  // The product has one way in: its own password form. It lists nobody.
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("main").getByText(/dev\.local/i)).toHaveCount(0);
  await page.screenshot({ path: `${shots}/01-login.png`, fullPage: true });
  await signInAs(page, "admin@dev.local");
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
  await expect(page.getByRole("heading", { name: "fake-llm", exact: true })).toBeVisible();
  await page.screenshot({ path: `${shots}/05-models.png`, fullPage: true });

  await page.route("**/api/v1/conversations", (route) => route.abort());
  await page.goto("/chat");
  await expect(page.getByRole("alert").filter({ hasText: /failed|loaded|fetch/i })).toBeVisible();
  await page.screenshot({ path: `${shots}/06-error.png`, fullPage: true });
});

test("a seeded user signs in with the password form", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel("Email").fill("admin@dev.local");
  await page.getByLabel("Password").fill("dev-password");
  await page.getByRole("main").getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("admin@dev.local")).toBeVisible();
});
