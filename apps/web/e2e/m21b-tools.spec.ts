import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m21b";

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

test("general tools are visible in the catalogue, the builder and chat", async ({ page }) => {
  await signIn(page);
  await page.goto("/tools");
  await expect(page.getByRole("heading", { name: "General tools" })).toBeVisible();
  await expect(page.getByText("general.code").first()).toBeVisible();
  await capture(page, "tools");

  await page.goto("/agents/new");
  await expect(page.getByRole("heading", { name: "New agent" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Run Python" })).toBeChecked();
  await page.getByLabel("Name").fill("Field analyst");
  await page
    .getByLabel("Instructions")
    .fill("Analyse files with code and bring a downloadable result.");
  await page.getByRole("checkbox", { name: "Web search" }).uncheck();
  await capture(page, "builder");

  const catalogue = await page.request.get("/api/v1/agents");
  const body = (await catalogue.json()) as {
    items?: { id: string; slug?: string }[];
    data?: { id: string; slug?: string }[];
  };
  const rows = body.items ?? body.data ?? [];
  const assistant = rows.find((row) => row.slug === "assistant") ?? rows[0];
  await page.goto(`/agents/${assistant?.id ?? ""}`);
  await expect(page.getByRole("checkbox", { name: "Call an API" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("General tools").first()).toBeVisible();
  await capture(page, "editor");

  await page.goto("/chat");
  const composer = page.getByRole("textbox").last();
  await composer.fill('/tool general.code {"source":"print(6*7)"}');
  await composer.press("Enter");
  await expect(page.getByText("general.code").first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText("42", { exact: true })).toBeVisible({ timeout: 20_000 });
  await capture(page, "chat-code");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => item.impact === "serious" || item.impact === "critical"),
  ).toEqual([]);
});
