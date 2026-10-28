import { mkdirSync, writeFileSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

const root = "../../docs/testing/m20";
const enabled = process.env.AR_M20_CERT === "1";

const routes = [
  "/chat",
  "/agents",
  "/agents/new",
  "/tools",
  "/connections",
  "/knowledge",
  "/memory",
  "/skills",
  "/routines",
  "/approvals",
  "/reviews",
  "/runs",
  "/admin/models",
  "/admin/users",
  "/admin/policies",
  "/admin/channels",
  "/admin/evals",
  "/admin/usage",
  "/admin/quotas",
  "/admin/sandboxes",
  "/admin/assurance",
  "/platform/health",
  "/settings/profile",
];

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
}

async function shot(page: Page, name: string) {
  mkdirSync(root, { recursive: true });
  await page.screenshot({ path: `${root}/${name}.png`, fullPage: true });
}

async function setTheme(page: Page, theme: "light" | "dark") {
  await page.addInitScript((value) => {
    window.localStorage.setItem("ar-theme", value);
  }, theme);
}

test.describe("M20 walkthrough", () => {
  test.skip(!enabled, "Set AR_M20_CERT=1 for the local certification run");
  test.setTimeout(600_000);

  test("sign in, register the model, chat, and open the product", async ({ browser, baseURL }) => {
    const context = await browser.newContext({
      baseURL,
      viewport: { width: 1440, height: 900 },
      recordVideo: { dir: root, size: { width: 1440, height: 900 } },
    });
    const page = await context.newPage();
    try {
      const key = process.env.AR_CERT_LLM_API_KEY ?? "";
      expect(key.length).toBeGreaterThan(8);

      await setTheme(page, "light");
      await page.goto("/login");
      await shot(page, "desktop-light-login");
      await signIn(page);
      await shot(page, "desktop-light-chat-empty");

      await page.goto("/admin/models");
      await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
      if ((await page.getByRole("cell", { name: "DeepInfra" }).count()) === 0) {
        await page.getByRole("button", { name: "Advanced" }).click();
        await page.getByRole("button", { name: "OpenAI-compatible" }).click();
        await page.getByLabel("Name").fill("DeepInfra");
        await page.getByLabel("API key").fill(key);
        await page.getByRole("button", { name: "Register and test" }).click();
        await expect(page.getByText(/Sample:/)).toBeVisible({ timeout: 90_000 });
        const sample = await page.getByText(/Sample:/).innerText();
        expect(sample.toLowerCase()).not.toContain("provider test failed");
        expect(sample).not.toContain("fake:");
        expect(sample).not.toContain(key);
        await expect(page.getByLabel("API key")).toHaveValue("");
      }
      await shot(page, "desktop-light-models-registered");

      await page.goto("/chat");
      await page.getByLabel("Message").fill("Reply with exactly the word pong and nothing else.");
      await page.getByRole("button", { name: "Send" }).click();
      await page
        .getByRole("button", { name: "Stop" })
        .waitFor({ state: "visible", timeout: 15_000 })
        .catch(() => undefined);
      await expect(page.getByRole("button", { name: "Stop" })).toBeHidden({ timeout: 120_000 });
      await expect(page.getByText("pong", { exact: true }).last()).toBeVisible();
      const transcript = await page.locator("main").innerText();
      expect(transcript).not.toContain("fake:");
      expect(transcript).not.toContain(key);
      await shot(page, "desktop-light-chat-pong");

      writeFileSync("/tmp/m20-access-policy.txt", "The visitor badge colour is amber.\n");
      await page.goto("/knowledge");
      await page.locator("#knowledge-name").fill("Visitor policy");
      await page.getByRole("button", { name: "Create collection" }).click();
      await page.getByRole("link", { name: "Visitor policy" }).click();
      await page.locator("#knowledge-file").setInputFiles("/tmp/m20-access-policy.txt");
      await page.locator("button[type=submit]").filter({ hasText: "Add a file" }).click();
      await expect(page.getByText("m20-access-policy.txt")).toBeVisible({ timeout: 20_000 });
      await shot(page, "desktop-light-knowledge-uploaded");

      await page.goto("/agents/new");
      await page.locator("#instruction").fill("A one-sentence assistant for visitor questions.");
      await page.getByRole("button", { name: "Draft" }).click();
      await page.waitForTimeout(8_000);
      await shot(page, "desktop-light-builder");

      for (const route of routes) {
        const response = await page.goto(route, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(400);
        const slug = route.replaceAll("/", "_").replace(/^_/, "") || "home";
        await shot(page, `desktop-light-${slug}`);
        if (response && response.status() >= 500) {
          throw new Error(`${route} returned ${response.status()}`);
        }
      }
    } finally {
      await context.close();
    }
  });
});

test.describe("M20 theme and viewport matrix", () => {
  test.skip(!enabled, "Set AR_M20_CERT=1 for the local certification run");
  test.setTimeout(600_000);

  for (const theme of ["light", "dark"] as const) {
    for (const viewport of [
      { name: "desktop", width: 1440, height: 900 },
      { name: "mobile", width: 390, height: 844 },
    ]) {
      if (theme === "light" && viewport.name === "desktop") {
        continue;
      }
      test(`${theme} ${viewport.name}`, async ({ page }) => {
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        await setTheme(page, theme);
        await signIn(page);
        for (const route of routes) {
          await page.goto(route, { waitUntil: "domcontentloaded" });
          await page.waitForFunction(
            (value) => document.documentElement.dataset.theme === value,
            theme,
          );
          await page.waitForTimeout(250);
          const slug = route.replaceAll("/", "_").replace(/^_/, "") || "home";
          await shot(page, `${viewport.name}-${theme}-${slug}`);
        }
      });
    }
  }
});
