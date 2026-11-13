import { mkdirSync } from "node:fs";

import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m25";

test.describe.configure({ mode: "serial" });
test.use({ locale: "en-US", video: "on" });
test.setTimeout(180_000);

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

async function csrf(page: Page) {
  const cookies = await page.context().cookies();
  return cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
}

test("knowledge, memory, skills and a cited chat", async ({ page }) => {
  await signIn(page);
  const token = await csrf(page);
  const headers = { "x-csrf-token": token };

  const library = await page.request.post("/api/v1/library-documents", {
    headers,
    multipart: {
      upload: {
        name: "dock.md",
        mimeType: "text/markdown",
        buffer: Buffer.from("# Dock\n\nThe north dock code is ND-1844-QUILL.\n"),
      },
    },
  });
  expect(library.ok()).toBeTruthy();
  const libraryId = ((await library.json()) as { id: string }).id;

  const collection = await page.request.post("/api/v1/knowledge/collections", {
    headers,
    data: { name: "Docks", slug: "docks", description: "Dock codes" },
  });
  expect(collection.ok()).toBeTruthy();
  const collectionId = ((await collection.json()) as { id: string }).id;
  const member = await page.request.post(`/api/v1/knowledge/collections/${collectionId}/members`, {
    headers,
    data: { kind: "library", libraryDocumentId: libraryId },
  });
  expect(member.ok()).toBeTruthy();

  const skill = await page.request.post("/api/v1/skills:import", {
    headers,
    data: {
      markdown:
        "---\nname: Weekly status\nslug: weekly-status\ndescription: Use when the user asks for a weekly status note.\n---\n\nBegin with STATUS-OK.\n",
    },
  });
  expect(skill.ok()).toBeTruthy();
  const skillId = ((await skill.json()) as { id: string }).id;

  const agent = await page.request.post("/api/v1/agents", {
    headers,
    data: { slug: "dock-clerk", name: "Dock clerk", description: "Knows the docks" },
  });
  expect(agent.ok()).toBeTruthy();
  const agentId = ((await agent.json()) as { id: string }).id;
  const current = await page.request.get(`/api/v1/agents/${agentId}`);
  const detail = (await current.json()) as { definition?: Record<string, unknown> };
  const definition = {
    ...(detail.definition ?? {}),
    instructions: "Answer from the knowledge base and follow a loaded skill.",
    skills: ["weekly-status"],
    knowledge: { collections: ["docks"] },
  };
  const draft = await page.request.put(`/api/v1/agents/${agentId}/versions/draft`, {
    headers,
    data: { definition, changeNote: "attach docks" },
  });
  expect(draft.ok()).toBeTruthy();
  const published = await page.request.post(`/api/v1/agents/${agentId}:publish`, {
    headers,
    data: { changeNote: "attach docks" },
  });
  expect(published.ok()).toBeTruthy();

  await page.goto("/knowledge");
  await expect(page.getByRole("heading", { name: "Knowledge", exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Docks" })).toBeVisible();
  await capture(page, "knowledge");
  await page.getByRole("link", { name: "Docks" }).click();
  await expect(page.getByText("indexed")).toBeVisible();
  await page.getByRole("tab", { name: "Search" }).click();
  await page.getByLabel("Question").fill("north dock code");
  await page.getByRole("button", { name: "Ask the library" }).click();
  await expect(page.getByText("ND-1844-QUILL")).toBeVisible();
  await capture(page, "collection");

  await page.goto("/memory");
  await expect(page.getByRole("heading", { name: "Memory", exact: true })).toBeVisible();
  const remember = page.getByRole("button", { name: "Remember this" });
  await expect(remember).toBeEnabled();
  await page.getByLabel("What should the assistant remember?").fill("Call the user Captain Bala");
  const saved = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/memory") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await remember.click();
  await saved;
  await expect(
    page.getByRole("listitem").filter({ hasText: "Call the user Captain Bala" }),
  ).toBeVisible();
  await capture(page, "memory");

  await page.goto("/skills");
  await expect(page.getByRole("heading", { name: "Skills", exact: true })).toBeVisible();
  const skillRow = page.getByRole("listitem").filter({ hasText: "Weekly status" });
  await expect(skillRow).toBeVisible();
  await capture(page, "skills");
  await skillRow.getByRole("link", { name: "Open" }).click();
  await expect(page.getByLabel("Instructions")).toBeVisible();
  await capture(page, "skill");

  await page.goto(`/agents/${agentId}`);
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByRole("tab", { name: "Knowledge" }).click();
  await expect(page.getByLabel("Knowledge bases")).toBeVisible();
  await capture(page, "agent");

  await page.goto("/chat?agent=dock-clerk");
  await page
    .locator("#composer")
    .fill("Write the weekly status note. What is the north dock code?");
  await page.locator("#composer").press("Enter");
  await expect(page.getByText(/Loaded skill/)).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("button", { name: /Dock/ })).toBeVisible();
  await capture(page, "chat");

  const axe = await new AxeBuilder({ page }).analyze();
  expect(
    axe.violations.filter((item) => item.impact === "serious" || item.impact === "critical"),
  ).toEqual([]);
  const video = page.video();
  await page.context().close();
  if (video) {
    await video.saveAs(`${shots}/walkthrough.webm`);
  }
  void skillId;
});
