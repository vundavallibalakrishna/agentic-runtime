import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m8";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page, email: string) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const button = page.getByRole("button", { name: `Sign in as ${email}` });
  await expect(button).toBeVisible();
  await button.click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
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

async function send(page: Page, text: string) {
  await page.getByLabel("Message").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("a preference is remembered, reviewed, and forgotten", async ({ page }) => {
  await signIn(page, "admin@dev.local");
  await page.goto("/memory");
  await expect(page.getByRole("heading", { name: "Memory", exact: true })).toBeVisible();
  await expect(page.getByText("Prefers weekly status notes to stay under one page.")).toBeVisible();
  await expect(page.getByText("The platform team names files with the date first.")).toBeVisible();
  const memory = await new AxeBuilder({ page }).analyze();
  expect(memory.violations).toEqual([]);
  await capture(page, "memory");

  await page.goto("/chat");
  await send(page, "Remember that I prefer answers in bullet points.");
  await expect(page.getByText("Memory updated:")).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "New chat" }).click();
  await send(page, "Draft a short status update");
  await expect(page.getByText("bullet points")).toBeVisible({ timeout: 30_000 });
  await capture(page, "remembered");

  await page.goto("/memory");
  const bullet = page.getByRole("listitem").filter({ hasText: "bullet points" });
  await bullet.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByText("bullet points")).toHaveCount(0);
  await page.goto("/chat");
  await page.getByRole("button", { name: "New chat" }).click();
  await send(page, "Draft a short status update");
  await expect(page.getByText("I kept this in bullet points")).toHaveCount(0, { timeout: 30_000 });

  await page.goto("/agents");
  const assistant = page.getByRole("listitem").filter({ hasText: "Assistant" });
  await assistant.getByRole("button", { name: "Open" }).click();
  await expect(page.getByText("08:30 opening")).toBeVisible();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("08:30 opening")).toHaveCount(0);
  await capture(page, "review");

  await page.getByRole("button", { name: "Dev Admin" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in as member@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
  await page.goto("/memory");
  await expect(page.getByText("one page")).toHaveCount(0);
  await expect(page.getByText("date first")).toBeVisible();
  const member = await new AxeBuilder({ page }).analyze();
  expect(member.violations).toEqual([]);
  await capture(page, "member");
});
