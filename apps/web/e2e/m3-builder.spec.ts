import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m3";

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

test("build, publish, roll back and import a bundle", async ({ page }) => {
  await signIn(page);
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Helpdesk" })).toBeVisible();
  const catalogue = await new AxeBuilder({ page }).analyze();
  expect(catalogue.violations).toEqual([]);

  await page.goto("/agents/new");
  await page
    .getByLabel("What should this agent do?")
    .fill("create an agent that reviews vendor SOC 2 reports and flags gaps");
  await page.getByRole("button", { name: "Draft" }).click();
  await expect(page.getByText("Tool: files")).toBeVisible();
  await expect(page.getByLabel("Validation")).toBeVisible();
  const builder = await new AxeBuilder({ page }).analyze();
  expect(builder.violations).toEqual([]);
  await page.getByLabel("Change the proposal").fill("Ask for the report name first.");
  await page.getByRole("button", { name: "Update draft" }).click();
  await expect(page.getByText(/report name/i)).toBeVisible();
  await page.getByRole("button", { name: "Use this draft" }).click();
  await expect(page.getByLabel("Instructions")).toBeVisible();
  await expect(page.getByLabel("Instructions")).toHaveValue(/SOC 2|report/i);

  await page.goto("/agents/new");
  await page.getByRole("button", { name: "Support" }).click();
  await expect(page.getByLabel("Instructions")).toBeVisible();
  await page
    .getByLabel("Instructions")
    .fill("Help the person finish the request in one short reply.");
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByRole("tab", { name: "YAML" }).click();
  await expect(page.getByLabel("YAML")).toHaveValue(/one short reply/);
  await page.getByLabel("Test message").fill("hello from the draft");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText(/fake:/i)).toBeVisible({ timeout: 20_000 });
  await page.getByLabel("Change note").fill("first release");
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText("v1 published")).toBeVisible();
  await page
    .getByLabel("Instructions")
    .fill("Help the person finish the request, then offer one next step.");
  await page.getByLabel("Change note").fill("second release");
  await page.getByRole("button", { name: "Publish" }).click();
  await expect(page.getByText("v2 published")).toBeVisible();
  const editor = await new AxeBuilder({ page }).analyze();
  expect(editor.violations).toEqual([]);
  await page.getByRole("button", { name: "Roll back" }).first().click();
  await expect(page.getByText(/v3 published/)).toBeVisible();
  await page.getByRole("button", { name: "Export bundle" }).click();
  await expect(page.locator("pre")).toContainText("kind:");
  const exported = await page.locator("pre").innerText();
  await page.getByLabel("Import bundle").fill(exported);
  await page.getByRole("button", { name: "Preview import" }).click();
  await expect(page.getByText(/unchanged|new_version|create/)).toBeVisible();
});

test("catalogue, builder and editor in light and dark", async ({ page }) => {
  await signIn(page);
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Helpdesk" })).toBeVisible();
  await capture(page, "catalogue");
  await page.goto("/agents/new");
  await page
    .getByLabel("What should this agent do?")
    .fill("create an agent that reviews vendor SOC 2 reports and flags gaps");
  await page.getByRole("button", { name: "Draft" }).click();
  await expect(page.getByText("Tool: files")).toBeVisible();
  await capture(page, "builder");
  await page.getByRole("button", { name: "Support" }).click();
  await expect(page.getByLabel("Instructions")).toBeVisible();
  await capture(page, "editor");
});
