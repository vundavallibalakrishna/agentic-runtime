import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m22";

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

test("connections, imports and the registry are usable", async ({ page }) => {
  await signIn(page);
  await page.goto("/connections");
  await expect(page.getByRole("heading", { name: "Saved connections" })).toBeVisible();
  await page.getByLabel("Name", { exact: true }).fill("demo");
  await page.getByLabel("Secret", { exact: true }).fill("not-a-real-secret");
  await page.getByRole("button", { name: "Save connection" }).click();
  await expect(page.getByText("Saved. The secret is not shown again.")).toBeVisible();
  await expect(page.getByText("not-a-real-secret")).toHaveCount(0);
  await capture(page, "connections");

  await page.goto("/tools");
  await expect(page.getByRole("heading", { name: "Import an OpenAPI spec" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tool from a description" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Registry" })).toBeVisible();
  await page.getByLabel("What should this tool do?").fill("GET https://example.com/zen");
  await page.getByRole("button", { name: "Review definition" }).click();
  await expect(page.getByText("get_example_com")).toBeVisible();
  await capture(page, "tools");

  const catalogue = await page.request.get("/api/v1/agents");
  const body = (await catalogue.json()) as {
    items?: { id: string; slug?: string }[];
    data?: { id: string; slug?: string }[];
  };
  const rows = body.items ?? body.data ?? [];
  const assistant = rows.find((row) => row.slug === "assistant") ?? rows[0];
  await page.goto(`/agents/${assistant?.id ?? ""}`);
  await expect(page.getByText("MCP, OpenAPI and custom tools")).toBeVisible({ timeout: 20_000 });
  await capture(page, "editor");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => item.impact === "serious" || item.impact === "critical"),
  ).toEqual([]);
});
