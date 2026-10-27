import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m9";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(180_000);

async function signIn(page: Page, email: string) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const button = page.getByRole("button", { name: `Sign in as ${email}` });
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

async function send(page: Page, text: string) {
  await page.getByLabel("Message").fill(text);
  await page.getByRole("button", { name: "Send" }).click();
}

test("skills publish, research delegates, and the writer produces a brief", async ({ page }) => {
  await signIn(page, "admin@dev.local");
  await page.goto("/skills");
  await expect(page.getByRole("heading", { name: "Skills", exact: true })).toBeVisible();
  await expect(page.getByText("Brand guidelines")).toBeVisible();
  const skills = await new AxeBuilder({ page }).analyze();
  expect(skills.violations).toEqual([]);
  await capture(page, "skills");

  await page.getByRole("link", { name: "Open" }).first().click();
  await expect(page.getByText("sentence case").first()).toBeVisible();
  await page.getByRole("button", { name: "Advanced" }).click();
  await expect(page.getByText("letterhead.md", { exact: true })).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: "Writer" })).toBeVisible();
  const editor = await new AxeBuilder({ page }).analyze();
  expect(editor.violations).toEqual([]);
  await capture(page, "skill-editor");

  await page.goto("/skills");
  await expect(page.getByText("Brand guidelines")).toBeVisible();
  const existing = page.getByRole("listitem").filter({ hasText: "Launch checklist" });
  if ((await existing.count()) > 0) {
    await existing.first().getByRole("link", { name: "Open" }).click();
  } else {
    await page.getByLabel("Name").fill("Launch checklist");
    await page
      .getByLabel("What the agent should know this skill is for")
      .fill("A short launch checklist.");
    await page.getByLabel("Instructions").fill("1. Confirm the date.\n2. Name the owner.");
    await page.getByRole("button", { name: "Create a skill" }).click();
  }
  await expect(page.getByRole("heading", { name: "Launch checklist" })).toBeVisible();
  const version = page.getByText("v1", { exact: true });
  if (!(await version.isVisible())) {
    await page.getByLabel("Change note").fill("First publish");
    await page.getByRole("button", { name: "Publish", exact: true }).click();
    await expect(version).toBeVisible({ timeout: 15_000 });
  }
  await capture(page, "published");

  await page.goto("/chat?agent=research-lead");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Research lead");
  await send(page, "Research the launch notes and the rollout plan");
  await expect(page.getByText("Merged findings")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("the checklist is complete")).toBeVisible();
  await expect(page.getByText("start with the pilot team")).toBeVisible();
  await capture(page, "research");
  await page.getByRole("link", { name: "View trace" }).last().click();
  await expect(page.getByRole("heading", { name: "Run trace" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Researcher/ }).first()).toBeVisible();
  const trace = await new AxeBuilder({ page }).analyze();
  expect(trace.violations).toEqual([]);
  await capture(page, "trace");

  await page.goto("/chat?agent=writer");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Writer");
  await send(page, "Write a one-page brand brief as a docx");
  await expect(page.getByText("brand-brief.docx")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("sentence case").first()).toBeVisible();
  await capture(page, "brief");

  await page.goto("/runs");
  await expect(page.getByRole("heading", { name: "Runs", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View trace" }).first()).toBeVisible();
  const runs = await new AxeBuilder({ page }).analyze();
  expect(runs.violations).toEqual([]);
  await capture(page, "runs");

  await page.goto("/agents");
  const lead = page.getByRole("listitem").filter({ hasText: "Research lead" });
  await lead.getByRole("link", { name: "View agent" }).click();
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByRole("tab", { name: "Subagents" }).click();
  await expect(page.getByLabel("Allowed subagents")).toHaveValue(/researcher/);
  await page.getByRole("tab", { name: "Skills" }).click();
  await capture(page, "builder");

  await page.goto("/skills");
  await expect(page.getByText("Brand guidelines")).toBeVisible();
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await page.locator("#skill-search").fill("zzz-no-such-skill");
  await expect(page.getByText("No skills yet. Create one and it will show up here.")).toBeVisible();
  await capture(page, "empty");

  await page.getByRole("button", { name: "Dev Admin" }).click();
  await page.getByRole("menuitem", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByRole("button", { name: "Sign in as member@dev.local" }).click();
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
  await page.goto("/skills");
  await expect(page.getByText("Brand guidelines")).toBeVisible();
  const member = await new AxeBuilder({ page }).analyze();
  expect(member.violations).toEqual([]);
  await capture(page, "member");
});
