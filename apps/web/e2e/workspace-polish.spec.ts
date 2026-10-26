import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/workspace-polish";

async function signIn(page: Page, role = "admin") {
  await page.goto("/login");
  await page.getByRole("button", { name: `Sign in as ${role}@dev.local` }).click();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`${theme} workspace at ${width}px is accessible and fits`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled();
      await page.screenshot({ path: `${shots}/chat-${theme}-${width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      if (width < 1024) {
        await page.getByRole("button", { name: "Open menu", exact: true }).click();
        await expect(page.getByRole("dialog")).toBeVisible();
        await page.keyboard.press("Escape");
        await expect(page.getByRole("dialog")).toBeHidden();
        await expect(page.getByRole("button", { name: "Open menu", exact: true })).toBeFocused();
      }
      await page.goto("/agents");
      await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();
      await page.screenshot({ path: `${shots}/agents-${theme}-${width}.png`, fullPage: true });
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
    });
  }
}

test("catalogue loading, empty filters, retry and member permissions", async ({ page }) => {
  await signIn(page, "member");
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: /^(Create an agent|New agent)$/, exact: true }),
  ).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Users", exact: true })).toHaveCount(0);
  await page.getByRole("textbox", { name: "Search agents" }).fill("no-agent-matches-this");
  await expect(
    page.getByText("No agents match these filters. Try a different search."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();

  await page.route("**/api/v1/agents", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Agents are temporarily unavailable." }),
    }),
  );
  await page.reload();
  await expect(
    page.getByRole("alert").filter({ hasText: "Agents are temporarily unavailable." }),
  ).toContainText("Agents are temporarily unavailable.");
  await page.unroute("**/api/v1/agents");
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();

  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/agents", async (route) => {
    await gate;
    await route.continue();
  });
  await page.reload();
  await expect(page.getByRole("status", { name: "Loading agents" })).toBeVisible();
  release();
  await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();
});

test("command palette starts a new chat from another page", async ({ page }) => {
  await signIn(page);
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Helpdesk", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Search anything" }).click();
  await page.getByRole("textbox", { name: "Command", exact: true }).fill("New chat");
  await page.getByRole("button", { name: /New chat/ }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
});
