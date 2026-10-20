import { expect, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

test("sign in, chat, stop, empty and error states", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.screenshot({ path: `${shots}/01-login.png`, fullPage: true });
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await expect(page.getByText("admin@dev.local")).toBeVisible();
  await expect(page.getByText("No conversations yet.")).toBeVisible();
  await page.screenshot({ path: `${shots}/02-empty-chat.png`, fullPage: true });

  await page.getByRole("button", { name: "Draft a short status update" }).click();
  await expect(page.getByText(/fake:|status update/i).first()).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${shots}/03-streamed-reply.png`, fullPage: true });

  await page.getByLabel("Message").fill("Please answer slowly");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Stop" })).toBeVisible({ timeout: 10_000 });
  await page.getByRole("button", { name: "Stop" }).click();
  await page.screenshot({ path: `${shots}/04-stopped.png`, fullPage: true });

  await page.goto("/admin/models");
  await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
  await expect(page.getByText("fake-llm")).toBeVisible();
  await page.screenshot({ path: `${shots}/05-models.png`, fullPage: true });

  await page.route("**/api/v1/conversations", (route) => route.abort());
  await page.goto("/chat");
  await expect(page.getByRole("alert")).toBeVisible();
  await page.screenshot({ path: `${shots}/06-error.png`, fullPage: true });
});
