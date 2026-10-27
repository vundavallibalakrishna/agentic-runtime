import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/detail-screens";
const endpoints: Record<string, unknown> = {
  "/agents/detail-agent": {
    id: "detail-agent",
    name: "Research assistant",
    description: "A focused assistant for clear, grounded answers.",
    canEdit: true,
    draft: {
      definition: {
        instructions: "Find the facts, cite your sources, and explain the conclusion clearly.",
        model: { alias: "reasoning" },
      },
    },
  },
  "/agents/detail-agent/versions": { items: [{ version: 1, state: "published" }] },
  "/agents/detail-agent/memory": { items: [] },
  "/skills/detail-skill": {
    id: "detail-skill",
    name: "Clear writing",
    description: "A shared guide to thoughtful, concise writing.",
    draft: {
      version: 2,
      instructionsMd:
        "## Start with the answer\n\nUse plain language and concrete examples.\n\n- Keep the reader in mind.\n- Make the next step clear.",
    },
  },
  "/skills/detail-skill/versions": { items: [{ version: 1 }] },
  "/skills/detail-skill/where-used": { agents: [] },
  "/approvals/detail-approval": {
    id: "detail-approval",
    qualifiedName: "tickets.create_ticket",
    status: "pending",
    riskClass: "W2",
    preview: {
      title: "Create a support ticket",
      summary: "Report a printer issue on floor three.",
    },
    policyReasons: ["This action needs your approval."],
    arguments: { title: "Printer issue" },
  },
  "/review-items/detail-review": {
    id: "detail-review",
    subjectType: "Weekly report",
    statementText: "I have reviewed this report and confirm it is ready to share.",
    status: "pending",
    contentHash: "content",
    statementHash: "statement",
  },
  "/routines/detail-routine": {
    id: "detail-routine",
    name: "Weekly digest",
    status: "active",
    triggerSummary: "Every Monday at 09:00",
    instructions: "Summarise the week's updates and flag any decisions that need attention.",
    nextFires: ["2026-11-02T03:30:00Z"],
  },
  "/routines/detail-routine/events": { items: [] },
  "/knowledge/collections/detail-library": {
    id: "detail-library",
    name: "Company library",
    description: "The documents your assistants use to answer questions.",
    canManage: true,
  },
  "/knowledge/collections/detail-library/documents": { items: [] },
  "/knowledge/collections/detail-library/sources": { items: [] },
  "/knowledge/collections/detail-library/jobs": { items: [] },
  "/runs/detail-run": {
    id: "detail-run",
    status: "completed",
    trigger: "chat",
    resultSummary: "Found the visitor guide and answered the question with a source.",
  },
  "/runs/detail-run/children": { items: [] },
  "/runs/detail-run/steps": { items: [{ id: "step", kind: "knowledge.search" }] },
  "/runs/detail-run/tool-calls": { items: [] },
};
const screens = [
  ["/agents/detail-agent", "Research assistant", "/agents/detail-agent"],
  ["/skills/detail-skill", "Clear writing", "/skills/detail-skill"],
  ["/approvals/detail-approval", "Approval", "/approvals/detail-approval"],
  ["/reviews/detail-review", "Review", "/review-items/detail-review"],
  ["/routines/detail-routine", "Weekly digest", "/routines/detail-routine"],
  ["/knowledge/detail-library", "Company library", "/knowledge/collections/detail-library"],
  ["/runs/detail-run", "Run trace", "/runs/detail-run"],
] as const;
async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Chat", exact: true })).toBeVisible();
}
async function fixtures(page: Page) {
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname.replace("/api/v1", "");
    if (path in endpoints) await route.fulfill({ json: endpoints[path] });
    else await route.continue();
  });
}
async function audit(page: Page) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  expect(
    await page.evaluate(
      () =>
        document.documentElement.scrollWidth <= innerWidth &&
        (document.querySelector("main")?.scrollWidth ?? 0) <=
          (document.querySelector("main")?.clientWidth ?? 0),
    ),
  ).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
}
for (const theme of ["light", "dark"])
  for (const width of [1280, 375]) {
    test(`${theme} detail screens at ${width}px`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      await fixtures(page);
      for (const [path, , endpoint] of screens) {
        await test.step(path, async () => {
          await page.goto(path);
          await expect(page.locator("main h1")).toBeVisible();
          await expect(page.getByRole("button", { name: "Try again", exact: true })).toHaveCount(0);
          await audit(page);
          await page.screenshot({
            path: `${shots}/${endpoint.split("/").pop()}-${theme}-${width}.png`,
            fullPage: true,
          });
          if (path.startsWith("/knowledge")) {
            for (const name of ["Search", "Sources", "Jobs"]) {
              await page.getByRole("tab", { name, exact: true }).click();
              await expect(page.getByRole("tab", { name, exact: true })).toHaveAttribute(
                "aria-selected",
                "true",
              );
              await audit(page);
            }
          }
        });
      }
      for (const path of [
        "/agents/new",
        "/knowledge/detail-library/sources/new",
        "/settings/profile",
      ]) {
        await page.goto(path);
        await expect(page.locator("main h1")).toBeVisible();
        await audit(page);
      }
      await page.goto("/agents/detail-agent");
      await page.getByRole("button", { name: "Advanced", exact: true }).click();
      await page.getByRole("tab", { name: "Model", exact: true }).focus();
      await page.keyboard.press("ArrowRight");
      await expect(page.getByRole("tab", { name: "Tools", exact: true })).toBeFocused();
      await audit(page);
    });
  }

test("detail loading and failed fetches never expose stale actions, and retry recovers", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signIn(page);
  await fixtures(page);
  for (const [path, , endpoint] of screens) {
    let release: () => void = () => {};
    const pending = new Promise<void>((resolve) => {
      release = resolve;
    });
    const matcher = `**/api/v1${endpoint}`;
    await page.route(matcher, async (route) => {
      await pending;
      await route.fulfill({ status: 503, json: { detail: "Service unavailable. Please retry." } });
    });
    await page.goto(path);
    await expect(page.locator('[aria-busy="true"]').first()).toBeVisible();
    release();
    await expect(page.getByRole("alert").filter({ hasText: "Service unavailable" })).toBeVisible();
    await expect(
      page.getByRole("button", { name: /^(Publish|Approve|Sign off|Run now)$/ }),
    ).toHaveCount(0);
    await page.unroute(matcher);
    await page.getByRole("button", { name: "Try again", exact: true }).click();
    await expect(page.getByText("Service unavailable. Please retry.")).toHaveCount(0);
    await audit(page);
  }
});
