import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m24";

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

test("document library, comparison, check and rewrite", async ({ page }) => {
  await signIn(page);
  await page.goto("/documents");
  await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
  await capture(page, "library-empty");
  await page.getByLabel("File").setInputFiles({
    name: "access.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Access\n\nStaff use badges at every door. Visitors sign the book.\n"),
  });
  await expect(page.getByRole("link", { name: "Access" }).first()).toBeVisible();
  await page.getByLabel("File").setInputFiles({
    name: "travel.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Travel\n\nTrips need approval from a manager.\n"),
  });
  await expect(page.getByRole("link", { name: "Travel" }).first()).toBeVisible();
  await capture(page, "library");
  await page.getByRole("link", { name: "Access" }).first().click();
  await expect(page.getByText("Staff use badges at every door.")).toBeVisible();
  await capture(page, "document");

  await page.goto("/documents");
  await page.getByLabel("Left document").selectOption({ label: "Access" });
  await page.getByLabel("Right document").selectOption({ label: "Travel" });
  await page.getByRole("button", { name: "Compare" }).click();
  await expect(page.getByRole("heading", { name: "Comparison" })).toBeVisible();
  await capture(page, "compare");

  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
  const listed = await page.request.get("/api/v1/library-documents");
  expect(listed.ok()).toBeTruthy();
  const items = ((await listed.json()) as { items: { id: string; title: string }[] }).items;
  const access = items.find((item) => item.title === "Access");
  const checked = await page.request.post(`/api/v1/library-documents/${access?.id}:judge`, {
    data: { statements: ["Staff use badges", "Operate a colony on Mars"] },
    headers: { "x-csrf-token": csrf },
  });
  expect(checked.ok()).toBeTruthy();
  const check = (await checked.json()) as { id: string };
  await page.goto(`/documents/checks/${check.id}`);
  await expect(page.getByText("not_found")).toBeVisible();
  await capture(page, "check");

  const rewrite = await page.request.post(`/api/v1/library-documents/${access?.id}:rewrite`, {
    data: { instruction: 'replace "badges" with "passes"' },
    headers: { "x-csrf-token": csrf },
  });
  expect(rewrite.ok()).toBeTruthy();
  const proposal = (await rewrite.json()) as { id: string };
  await page.goto(`/documents/rewrites/${proposal.id}`);
  await expect(page.getByRole("heading", { name: "Rewrite review" })).toBeVisible();
  await capture(page, "rewrite");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => item.impact === "serious" || item.impact === "critical"),
  ).toEqual([]);
});
