import AxeBuilder from "@axe-core/playwright";
import { expect, openToolCall, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m4";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page) {
  await page.goto("/login");
  await signInAs(page, "admin@dev.local");
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
  await page.getByRole("tab", { name: "Personal accounts", exact: true }).click();
  const accounts = page.getByRole("tabpanel", { name: "Personal accounts" });
  const tickets = accounts.getByRole("listitem").filter({ hasText: "Tickets" });
  await expect(tickets.getByText("Tickets", { exact: true })).toBeVisible();
  await expect(tickets.getByText("Connected", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Database connections", exact: true }).click();
  await expect(
    page
      .getByRole("tabpanel", { name: "Database connections" })
      .getByText("Warehouse", { exact: true }),
  ).toBeVisible();
  const connections = await new AxeBuilder({ page }).analyze();
  expect(connections.violations).toEqual([]);

  await page.goto("/chat?agent=desk");
  await page.getByText("Chat options", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Agent: Desk", exact: true })).toBeVisible();
  await page.getByLabel("Message").fill("File a ticket: the printer on floor 3 is jammed");
  await page.getByRole("button", { name: "Send" }).click();
  await openToolCall(page, /Filed ticket TCK-\d+\./);
  await expect(page.getByText(/Filed ticket TCK-\d+\./).first()).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Message").fill("How many orders are in the warehouse?");
  await page.getByRole("button", { name: "Send" }).click();
  await openToolCall(page, page.getByText("3", { exact: true }));
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
  await page.getByText("Chat options", { exact: true }).click();
  await expect(page.getByRole("button", { name: "Agent: Desk", exact: true })).toBeVisible();
  await capture(page, "desk");
});
