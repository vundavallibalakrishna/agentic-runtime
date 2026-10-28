import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m16";

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

test("import an OSCAL catalogue and open a control", async ({ page }) => {
  await signIn(page);
  await page.goto("/grc");
  await expect(page.getByRole("heading", { name: "GRC" })).toBeVisible();
  await expect(page.getByText("NIST CSF 2.0")).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("link", { name: "GRC" })).toBeVisible();
  await page.getByLabel("Import OSCAL").setInputFiles({
    name: "extra-catalog.json",
    mimeType: "text/plain",
    buffer: Buffer.from(
      JSON.stringify({
        catalog: {
          metadata: {
            title: "Fixture catalogue",
            version: "1.0",
            props: [
              { name: "key", value: "fixture-cat" },
              { name: "licence", value: "free" },
            ],
          },
          controls: [
            {
              id: "fix-1",
              title: "Fixture control",
              parts: [{ name: "statement", prose: "A fixture statement." }],
            },
          ],
        },
      }),
    ),
  });
  await expect(page.getByText("Catalogue imported.")).toBeVisible();
  await expect(page.getByText("Fixture catalogue")).toBeVisible();
  await page.getByRole("link", { name: "Controls" }).click();
  await expect(page.getByRole("button", { name: /Fixture control/ })).toBeVisible();
  await page.getByRole("button", { name: /Fixture control/ }).click();
  await expect(page.getByText("A fixture statement.")).toBeVisible();
  const axe = await new AxeBuilder({ page }).analyze();
  expect(axe.violations).toEqual([]);
  await capture(page, "controls");
  await page.goto("/grc/evidence");
  await expect(page.getByText("No evidence is linked to a control yet.")).toBeVisible();
  await capture(page, "evidence");
});
