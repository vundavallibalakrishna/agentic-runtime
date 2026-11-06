import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m27";

const pages = [
  ["servicenow", "ServiceNow"],
  ["salesforce", "Salesforce"],
  ["zendesk", "Zendesk"],
  ["hubspot", "HubSpot"],
  ["okta", "Okta"],
  ["entra", "Microsoft Entra ID"],
  ["aws", "AWS"],
  ["azure", "Azure"],
  ["gcp", "Google Cloud"],
] as const;

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(360_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await page.waitForURL(/\/chat/, { timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Chat", exact: true })).toBeVisible();
}

async function capture(page: Page, name: string) {
  mkdirSync(shots, { recursive: true });
  for (const theme of ["light", "dark"] as const) {
    for (const size of [
      { width: 1440, height: 900, label: "desktop" },
      { width: 390, height: 844, label: "mobile" },
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
  await page.setViewportSize({ width: 1440, height: 900 });
}

test("batch-two catalog and setup pages", async ({ page }) => {
  await signIn(page);
  await page.goto("/connectors");
  await expect(page.getByRole("heading", { name: "Connectors", exact: true })).toBeVisible();
  await page.getByLabel("Search connectors").fill("service");
  await expect(page.getByRole("link", { name: /ServiceNow/ })).toBeVisible();
  await expect(page.getByText("Built", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Not live-tested").first()).toBeVisible();
  await capture(page, "catalog");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);

  for (const [slug, name] of pages) {
    await page.goto(`/connectors/${slug}`);
    await expect(page.getByRole("heading", { name })).toBeVisible();
    await expect(page.getByText("Built", { exact: true })).toBeVisible();
    await expect(page.getByText("Not live-tested", { exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open the provider's app page" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Setup guide" })).toBeVisible();
    await capture(page, slug);
  }

  await page.goto("/connectors/servicenow");
  await expect(page.getByText("Asks first").first()).toBeVisible();
  await page.goto("/connectors/aws");
  await expect(page.getByText("ReadOnlyAccess", { exact: true })).toBeVisible();
  await expect(page.getByText("Asks first")).toHaveCount(0);

  const video = page.video();
  await page.context().close();
  if (video) {
    await video.saveAs(`${shots}/walkthrough.webm`);
  }
});
