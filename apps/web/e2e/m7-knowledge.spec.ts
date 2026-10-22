import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m7";

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

test("company library answers only from documents the reader can open", async ({ page }) => {
  await signIn(page, "admin@dev.local");
  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Company library" })).toBeVisible();
  const library = await new AxeBuilder({ page }).analyze();
  expect(library.violations).toEqual([]);
  await capture(page, "library");

  await page.getByRole("link", { name: /Company library/ }).click();
  await expect(page.getByText("Visitor guide")).toBeVisible();
  await expect(page.getByText("Payroll calendar")).toBeVisible();
  await expect(page.getByText("hidden from you")).toBeVisible();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByRole("button", { name: "Ask the library" }).click();
  await expect(page.getByText("The library can answer this.")).toBeVisible();
  await expect(page.getByText("Visitor guide").first()).toBeVisible();
  await capture(page, "search");

  await page.goto("/chat?agent=librarian");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Librarian");
  await page.getByLabel("Message").fill("When does the visitor desk open?");
  await page.getByRole("button", { name: "Send" }).click();
  const citation = page.getByRole("button", { name: /Visitor guide/ });
  await expect(citation).toBeVisible({ timeout: 30_000 });
  await citation.click();
  await expect(page.getByRole("dialog")).toContainText("08:30");
  await capture(page, "citation");
  await page.getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Why" }).click();
  await expect(page.locator("pre").last()).toBeVisible();

  await page.getByRole("button", { name: "Dev Admin" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in as member@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
  await page.goto("/knowledge");
  await page.getByRole("link", { name: /Company library/ }).click();
  await expect(page.getByText("On-call roster")).toBeVisible();
  await expect(page.getByText("Payroll calendar")).toHaveCount(0);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await page.getByLabel("Question").fill("When is payroll released?");
  await page.getByRole("button", { name: "Ask the library" }).click();
  await expect(page.getByText("Payroll calendar")).toHaveCount(0);
  const member = await new AxeBuilder({ page }).analyze();
  expect(member.violations).toEqual([]);
  await capture(page, "member");
});
