import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m12";

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

async function postJson(page: Page, path: string, body: unknown) {
  return page.evaluate(
    async ({ path: target, body: payload }) => {
      const match = document.cookie.match(/(?:^|; )ar_csrf=([^;]*)/);
      const token = match?.[1] ? decodeURIComponent(match[1]) : "";
      const response = await fetch(target, {
        method: "POST",
        credentials: "include",
        headers: { "content-type": "application/json", "x-csrf-token": token },
        body: JSON.stringify(payload),
      });
      return { ok: response.ok, status: response.status, text: await response.text() };
    },
    { path, body },
  );
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

test("usage charts, quotas, and a blocked chat stay accessible", async ({ page }) => {
  let created = "";
  try {
    await signIn(page);
    await page.goto("/admin/usage");
    await expect(page.getByRole("heading", { name: "Usage" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Export CSV" })).toBeVisible();
    await expect(page.getByText(/Quantity .+ INR/)).toBeVisible({ timeout: 20_000 });
    await capture(page, "usage");

    await page.goto("/admin/quotas");
    await expect(page.getByRole("heading", { name: "Quotas" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "model_tokens · day" })).toBeVisible();
    await page.getByRole("button", { name: "Advanced" }).click();
    await expect(page.getByLabel("When full")).toBeVisible();
    await page.getByRole("button", { name: "Simple" }).click();

    const agent = await postJson(page, "/api/v1/agents", {
      slug: `quota-probe-${Date.now().toString(36)}`,
      name: "Quota probe",
      description: "Shows a blocked chat without stopping other agents.",
    });
    expect(agent.ok, agent.text).toBeTruthy();
    const agentId = (JSON.parse(agent.text) as { id: string }).id;
    const published = await postJson(page, `/api/v1/agents/${agentId}:publish`, {
      changeNote: "quota probe",
    });
    expect(published.ok, published.text).toBeTruthy();
    const quota = await postJson(page, "/api/v1/quotas", {
      scopeType: "agent",
      scopeId: agentId,
      metric: "model_tokens",
      period: "day",
      limitValue: 0,
      action: "block",
      warnAtPct: 80,
    });
    expect(quota.ok, quota.text).toBeTruthy();
    created = "0";
    await page.reload();
    await expect(page.getByText("0 / 0")).toBeVisible();
    await capture(page, "quotas");

    await page.getByRole("button", { name: "Dev Admin" }).click();
    await page.getByRole("menuitem", { name: "Profile" }).click();
    await expect(page.getByRole("heading", { name: "My usage" })).toBeVisible();
    await capture(page, "profile");

    await page.goto("/chat");
    await expect(page.locator("#agent-picker option", { hasText: "Quota probe" })).toBeAttached();
    await page.locator("#agent-picker").selectOption({ label: "Quota probe" });
    const previous = page.url();
    await page.getByRole("button", { name: "New chat" }).click();
    await expect.poll(() => page.url(), { timeout: 20_000 }).not.toBe(previous);
    await page.getByLabel("Message").fill("Show the weekly numbers");
    await page.getByRole("button", { name: "Send" }).click();
    const blocked = page.getByRole("alert").filter({ hasText: "Quota reached" });
    await expect(blocked).toBeVisible({ timeout: 20_000 });
    await expect(blocked).toContainText("is 0");
    await capture(page, "blocked");

    const result = await new AxeBuilder({ page }).analyze();
    expect(result.violations).toEqual([]);
  } finally {
    if (created) {
      await page.goto("/admin/quotas");
      const card = page.locator("li").filter({ hasText: "0 / 0" });
      if ((await card.count()) > 0) {
        await card.getByRole("button", { name: "Remove" }).click();
        await expect(page.getByText("Quota removed.")).toBeVisible();
      }
    }
  }
});
