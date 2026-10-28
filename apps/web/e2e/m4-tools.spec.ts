import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m4";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local" }).click();
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

test("register a server, connect, and let the desk agent act", async ({ page }) => {
  await signIn(page);
  await page.goto("/tools");
  await expect(page.getByRole("heading", { name: "Tickets" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Warehouse" })).toBeVisible();
  const tools = await new AxeBuilder({ page }).analyze();
  expect(tools.violations).toEqual([]);

  const slug = `echo${Date.now().toString(36).slice(-6)}`;
  await page.getByLabel("Short name").fill(slug);
  await page.getByLabel("Name", { exact: true }).fill(slug);
  await page.getByLabel("Server address").fill("memory://echo");
  await page.getByRole("button", { name: "Register" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: /Approved|Submitted for review/ }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: slug, exact: true })).toBeVisible();

  await page.goto("/connections");
  await expect(page.getByRole("heading", { name: "Tickets" })).toBeVisible();
  await expect(page.getByText("Connected").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Warehouse" })).toBeVisible();
  const connections = await new AxeBuilder({ page }).analyze();
  expect(connections.violations).toEqual([]);

  await page.goto("/chat?agent=desk");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await page.getByLabel("Message").fill("File a ticket: the printer on floor 3 is jammed");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/Filed ticket TCK-\d+\./).first()).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Message").fill("How many orders are in the warehouse?");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("3", { exact: true }).first()).toBeVisible({ timeout: 20_000 });
  await capture(page, "desk-acted");

  await page.goto("/tools");
  await expect(page.getByText("tickets.create_ticket").first()).toBeVisible();
  await capture(page, "tools-log");
});

test("tools and connections in light and dark", async ({ page }) => {
  await signIn(page);
  await page.goto("/tools");
  await expect(page.getByRole("heading", { name: "Tickets" })).toBeVisible();
  await capture(page, "tools");
  await page.goto("/connections");
  await expect(page.getByRole("heading", { name: "Connections", exact: true })).toBeVisible();
  await capture(page, "connections");
  await page.goto("/chat?agent=desk");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await capture(page, "desk");
});
