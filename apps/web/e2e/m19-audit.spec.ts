import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m19";

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

test("walk the audit desk and keep the board pack behind sign-off", async ({ page }) => {
  await signIn(page);
  await page.goto("/grc/audit");
  await expect(page.getByRole("heading", { name: "Audit and reporting" })).toBeVisible();
  await expect(
    page.getByText("An auditor guest sees only the requests named in the grant."),
  ).toBeVisible({ timeout: 20_000 });
  await capture(page, "overview");

  await page.getByRole("link", { name: "Requests" }).first().click();
  await expect(page.getByText("SOC 2 population extract")).toBeVisible({ timeout: 20_000 });
  await capture(page, "requests");

  await page.getByRole("link", { name: "Reviews" }).click();
  await expect(page.getByText("Quarterly access review")).toBeVisible();
  await expect(page.getByText("Pay and approve")).toBeVisible();
  await page.getByRole("button", { name: "Start campaign" }).click();
  await expect(page.getByText("Campaign started.")).toBeVisible();
  await expect(page.getByText("Conflict")).toBeVisible();
  await capture(page, "reviews");

  await page.getByRole("link", { name: "Reports" }).click();
  await page.getByRole("button", { name: "Render Statement of applicability" }).click();
  await expect(page.getByText(/Binder .+ is ready/)).toBeVisible({ timeout: 20_000 });
  await page.getByRole("button", { name: "Render Board pack" }).click();
  await expect(page.getByText("A signed review is still required.")).toBeVisible();
  await capture(page, "reports");

  await page.getByRole("link", { name: "Inspections" }).click();
  await expect(page.getByText("SEBI")).toBeVisible();
  await capture(page, "inspections");

  await page.getByRole("link", { name: "Privacy" }).click();
  await expect(page.getByText("customer-1842")).toBeVisible();
  await capture(page, "privacy");

  await page.getByRole("link", { name: "Resilience" }).click();
  await expect(page.getByText("Support assistant")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await capture(page, "resilience");

  await page.context().clearCookies();
  await page.goto("/guest/portal");
  await expect(page.getByRole("heading", { name: "Auditor room" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Request a guest link" })).toBeVisible();
  await capture(page, "guest");
});
