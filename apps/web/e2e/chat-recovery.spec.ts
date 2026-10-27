import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Chat", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
}

test("a failed conversation creation preserves the message for retry", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 503, json: { detail: "Chat is temporarily unavailable" } });
    } else await route.continue();
  });
  await page.getByLabel("Message", { exact: true }).fill("Keep this draft when saving fails");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Chat is temporarily unavailable" }),
  ).toBeVisible();
  await expect(page.getByLabel("Message", { exact: true })).toHaveValue(
    "Keep this draft when saving fails",
  );
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeEnabled();
});

test("a late history response cannot replace a new chat", async ({ page }) => {
  await signIn(page);
  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        json: { items: [{ id: "delayed-history", title: "Delayed conversation" }] },
      });
    } else await route.continue();
  });
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let requested = false;
  await page.route("**/api/v1/conversations/delayed-history", async (route) => {
    requested = true;
    await pending;
    await route.fulfill({
      json: {
        messages: [{ id: "old-message", role: "user", text: "Outdated conversation message" }],
      },
    });
  });
  await page.goto("/chat");
  await page.getByRole("button", { name: "Delayed conversation" }).click();
  await expect.poll(() => requested).toBe(true);
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(page).not.toHaveURL(/delayed-history/);
  release();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
  await expect(page.getByText("Outdated conversation message")).toHaveCount(0);
});

test("New chat cancels a deep-linked history load and clears its URL", async ({ page }) => {
  await signIn(page);
  let release: () => void = () => {};
  const pending = new Promise<void>((resolve) => {
    release = resolve;
  });
  let requested = false;
  await page.route("**/api/v1/conversations/deep-linked-history", async (route) => {
    requested = true;
    await pending;
    await route.fulfill({
      json: {
        messages: [{ id: "old-message", role: "user", text: "Outdated deep-linked message" }],
      },
    });
  });
  await page.goto("/chat?conversation=deep-linked-history");
  await expect.poll(() => requested).toBe(true);
  await page.getByRole("button", { name: "New chat ⌘⇧O", exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  release();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
  await expect(page.getByText("Outdated deep-linked message")).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
});
