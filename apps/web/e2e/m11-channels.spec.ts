import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m11";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
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

test("channel catalogue and profile setup controls stay accessible", async ({ page }) => {
  await signIn(page);
  await page.getByRole("button", { name: "Dev Admin" }).click();
  await page.getByRole("menuitem", { name: "Profile" }).click();
  await expect(page.getByRole("heading", { name: "Profile" })).toBeVisible();
  await expect(page.getByText("U-ADMIN")).toBeVisible();
  await capture(page, "profile");

  await page.goto("/admin/channels");
  await expect(
    page.getByRole("heading", { name: "Channels", exact: true, level: 1 }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Workspace Slack", exact: true })).toBeVisible();
  await expect(page.getByText("The weekly digest is ready for #platform.")).toBeVisible();
  await capture(page, "list");

  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await expect(page.getByLabel("App-level token · Optional")).toBeVisible();
  await page.getByRole("button", { name: "Simple", exact: true }).click();
  await expect(page.getByLabel("Signing secret", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Default agent: Choose existing", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Save channel", exact: true })).toBeDisabled();
  // The connection probe is not offered until it calls the provider (OQ-162).
  await expect(page.getByRole("button", { name: "Test connection", exact: true })).toHaveCount(0);
  await capture(page, "setup-controls");

  await page.getByLabel("Name", { exact: true }).fill("Desk Slack");
  await page.getByLabel("Bot token", { exact: true }).fill("xoxb-desk");
  await page.getByLabel("Signing secret", { exact: true }).fill("desk-signing-secret");
  await page.getByRole("button", { name: "Default agent: Choose existing", exact: true }).click();
  await page.getByRole("dialog").getByRole("list").getByRole("button").first().click();
  await page.getByRole("button", { name: "Save channel", exact: true }).click();
  await expect(page.getByText("Channel saved.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Desk Slack", exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Setup · Desk Slack", exact: true }),
  ).toBeVisible();
  await capture(page, "saved");

  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});
