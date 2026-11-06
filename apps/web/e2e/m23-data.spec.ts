import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m23";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
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

test("database connections and agent limits are visible", async ({ page }) => {
  await signIn(page);
  await page.goto("/connections");
  await expect(page.getByRole("heading", { name: "Database connections" })).toBeVisible();
  await page.getByLabel("Database name").fill("proof");
  await page
    .getByLabel("Connection string")
    .fill("postgresql://analyst:not-shown@127.0.0.1:1/analysis");
  await page.getByRole("button", { name: "Save database" }).click();
  await expect(page.getByText("not-shown")).toHaveCount(0);
  await capture(page, "connections");

  const catalogue = await page.request.get("/api/v1/agents");
  const body = (await catalogue.json()) as {
    items?: { id: string; slug?: string }[];
    data?: { id: string; slug?: string }[];
  };
  const rows = body.items ?? body.data ?? [];
  const assistant = rows.find((row) => row.slug === "assistant") ?? rows[0];
  await page.goto(`/agents/${assistant?.id ?? ""}`);
  await expect(page.getByText("Database tools")).toBeVisible({ timeout: 20_000 });
  await page.getByRole("checkbox", { name: "Query a database" }).check();
  await expect(page.getByLabel("Row limit")).toBeVisible();
  await expect(page.getByLabel("JSON schema")).toBeVisible();
  await capture(page, "editor");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => item.impact === "serious" || item.impact === "critical"),
  ).toEqual([]);
});
