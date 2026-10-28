import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m18";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const button = page.getByRole("button", { name: "Sign in as admin@dev.local" });
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

test("walk the GRC workflows and keep export behind a signed review", async ({ page }) => {
  await signIn(page);
  await page.goto("/grc/workflows");
  await expect(page.getByRole("heading", { name: "GRC workflows" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Questionnaires" }).first()).toBeVisible();
  await capture(page, "overview");

  await page.getByRole("link", { name: "Questionnaires" }).first().click();
  await expect(page.getByText("Do you encrypt disks?").first()).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Export questionnaire" }).click();
  await expect(page.getByText("A signed review is still required.")).toBeVisible();
  await capture(page, "questionnaires");

  await page.getByRole("link", { name: "Vendors" }).click();
  await expect(page.getByText("Northwind")).toBeVisible();
  await capture(page, "vendors");

  await page.getByRole("link", { name: "Policies" }).click();
  await expect(page.getByText("Access control")).toBeVisible();
  await page.getByRole("button", { name: "Publish policy" }).click();
  await expect(page.getByText("A signed review is still required.")).toBeVisible();
  await capture(page, "policies");

  await page.getByRole("link", { name: "Risks" }).click();
  await expect(page.getByText("Vendor outage")).toBeVisible();
  await expect(page.getByText(/12/)).toBeVisible();
  await capture(page, "risks");

  await page.getByRole("link", { name: "Regulatory" }).click();
  await expect(page.getByText(/DPDP circular/)).toBeVisible();
  await capture(page, "regulatory");

  await page.getByRole("link", { name: "Incidents" }).click();
  await expect(page.getByText("Laptop with customer extracts")).toBeVisible();
  await expect(page.getByText(/dpdp 72h/)).toBeVisible();
  await capture(page, "incidents");

  await page.getByRole("link", { name: "Exceptions" }).click();
  await expect(
    page.getByText("The legacy store is isolated until the quarter closes."),
  ).toBeVisible();
  await capture(page, "exceptions");

  await page.getByRole("link", { name: "Ethics" }).click();
  await expect(page.getByText("Unsolicited gift from a supplier")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await capture(page, "ethics");
});
