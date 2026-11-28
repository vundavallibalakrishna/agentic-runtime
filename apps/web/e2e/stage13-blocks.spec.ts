import { readFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import { expect, openToolCall, type Page, test } from "./support/harness";

import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

const conversationId = "11111111-1111-4111-8111-111111111111";

const conversation = {
  id: conversationId,
  plan: [
    { id: "1", title: "Read the notes", status: "done" },
    { id: "2", title: "Draw the chart", status: "in_progress" },
  ],
  messages: [
    {
      id: "user-1",
      role: "user",
      text: "Review the attached notes and chart the counts.",
      isActiveBranch: true,
      content: [{ type: "text", text: "Review the attached notes and chart the counts." }],
    },
    {
      id: "assistant-1",
      role: "assistant",
      text: "The notes list two gaps.\n\n| Area | Count |\n| --- | --- |\n| North | 2 |\n| South | 5 |",
      isActiveBranch: true,
      status: "completed",
      answeredModel: "Qwen3-32B",
      resolvedModelId: "Qwen/Qwen3-32B",
      reasoning: "Comparing the two files.",
      content: [
        {
          type: "text",
          text: "The notes list two gaps.\n\n| Area | Count |\n| --- | --- |\n| North | 2 |\n| South | 5 |",
        },
        { type: "image", fileId: "file-chart", alt: "Counts" },
        { type: "followups", prompts: ["What is missing?", "Show the table"] },
        {
          type: "citation_ref",
          index: 1,
          citation: {
            index: 1,
            title: "Notes",
            snippet: "North 2, South 5.",
            uri: "https://example.com/notes",
            verified: true,
            status: "supported",
          },
        },
      ],
      toolCalls: [
        {
          qualifiedName: "general.chart",
          status: "succeeded",
          arguments: '{"kind":"bar"}',
          resultPreview: "Drew a bar chart.",
          timeline: [
            { kind: "arguments", text: '{"kind":"bar"}' },
            { kind: "result", text: "Drew a bar chart." },
          ],
          presentation: {
            kind: "chart",
            title: "Counts",
            rows: [
              { label: "North", value: 2 },
              { label: "South", value: 5 },
            ],
            files: [{ fileId: "file-chart", name: "chart.png" }],
          },
        },
      ],
    },
  ],
};

test("each answer block renders on the chat screen", async ({ page }) => {
  await page.route("**/api/v1/files/file-chart/content", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      body: readFileSync(join(process.cwd(), "e2e/fixtures/counts-chart.png")),
    }),
  );
  await page.route(`**/api/v1/conversations/${conversationId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(conversation),
    }),
  );
  await page.route("**/api/v1/files?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            id: "file-chart",
            name: "chart.png",
            mimeType: "image/png",
            conversationId,
          },
        ],
      }),
    }),
  );
  await page.route(`**/api/v1/conversations/${conversationId}/sandbox`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sandbox: null }),
    }),
  );
  await signInAs(page, "admin@dev.local");
  await page.emulateMedia({ colorScheme: "light" });
  await page.goto(`/chat?conversation=${conversationId}`);
  await expect(page.getByTestId("plan-checklist")).toBeVisible();
  await expect(page.getByTestId("thinking")).toBeVisible();
  await expect(page.getByTestId("tool-call")).toContainText("Chart");
  await expect(page.getByTestId("tool-call")).toContainText("Done");
  await expect(page.getByTestId("tool-call")).not.toContainText("general.chart");
  await expect(page.getByTestId("chart-view")).toHaveCount(1);
  await expect(page.getByTestId("tool-call").getByTestId("chart-view")).toHaveCount(0);
  await openToolCall(page, page.getByTestId("chart-reference"));
  await expect(page.getByTestId("chart-reference")).toContainText("chart.png");
  await expect(page.getByRole("img", { name: "Counts" })).toHaveCount(1);
  await expect(page.getByTestId("answered-by")).toContainText("Qwen3-32B");
  await expect(page.getByText("No artifacts yet.")).toHaveCount(0);
  await openToolCall(page, "chart.png");
  await expect(page.getByText("chart.png").first()).toBeVisible();
  await expect(page.getByTestId("followups")).toBeVisible();
  // A verified source is marked in the reply's sources, which open on demand.
  await page
    .getByRole("button", { name: /^\d+ sources?$/ })
    .first()
    .click();
  await expect(page.getByRole("dialog").getByText("Verified").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByText("Request validation failed")).toHaveCount(0);
  await showWholeTurn(page);
  await page.screenshot({ path: `${shots}/stage13-light.png`, fullPage: true });
  await page.getByRole("button", { name: "Interactive" }).click();
  await expect(page.getByTestId("interactive-chart")).toBeVisible();
  await page.screenshot({ path: `${shots}/stage13-chart.png`, fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await expect(page.getByTestId("plan-checklist")).toBeVisible();
  await expect(page.getByTestId("interactive-chart")).toBeVisible();
  await expect(page.getByRole("img", { name: "Counts" })).toHaveCount(0);
  await showWholeTurn(page);
  await page.screenshot({ path: `${shots}/stage13-dark.png`, fullPage: true });
});

const calledId = "22222222-2222-4222-8222-222222222222";

const called = {
  id: calledId,
  plan: [],
  messages: [
    {
      id: "user-2",
      role: "user",
      text: "Check the policy and the logs.",
      isActiveBranch: true,
      content: [{ type: "text", text: "Check the policy and the logs." }],
    },
    {
      id: "assistant-2",
      role: "assistant",
      text: "The policy requires badges. The log check did not finish.",
      isActiveBranch: true,
      status: "completed",
      content: [
        { type: "text", text: "The policy requires badges. The log check did not finish." },
      ],
      toolCalls: [
        {
          qualifiedName: "agents_parallel",
          status: "failed",
          resultPreview: '{"results":[]}',
          presentation: {
            kind: "agents",
            agents: [
              {
                agent: "Policy reader",
                status: "completed",
                task: "Read the access policy.",
                summary: "Badges are required at every door.",
                childRunId: "33333333-3333-4333-8333-333333333333",
              },
              {
                agent: "Log reader",
                status: "failed",
                task: "Read last week's door logs.",
                summary: "The child timed out and was not retried.",
                childRunId: "44444444-4444-4444-8444-444444444444",
              },
            ],
          },
        },
      ],
    },
  ],
};

test("a reply shows the agents it called", async ({ page }) => {
  await page.route(`**/api/v1/conversations/${calledId}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(called),
    }),
  );
  await page.route(`**/api/v1/conversations/${calledId}/sandbox`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ sandbox: null }),
    }),
  );
  await signInAs(page, "admin@dev.local");
  await page.goto(`/chat?conversation=${calledId}`);
  const card = page.getByTestId("tool-call");
  await expect(card).toContainText("Called other agents");
  await expect(card).not.toContainText("agents_parallel");
  await openToolCall(page, "Badges are required at every door.");
  const rows = card.getByTestId("called-agents").getByRole("listitem");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Policy reader · Done");
  await expect(rows.nth(1)).toContainText("Log reader · Didn't finish");
  await expect(card.getByRole("link", { name: "See what Log reader did" })).toHaveAttribute(
    "href",
    "/runs/44444444-4444-4444-8444-444444444444",
  );
  await expect(card).not.toContainText('{"results":[]}');
  expect(
    (await new AxeBuilder({ page }).include('[data-testid="tool-call"]').analyze()).violations,
  ).toEqual([]);
  await page.screenshot({ path: `${shots}/called-agents.png`, fullPage: true });
});

async function showWholeTurn(page: Page) {
  await page.evaluate(() => {
    const scroll = document.querySelector("[data-testid=message-scroll]");
    let node: HTMLElement | null = scroll instanceof HTMLElement ? scroll : null;
    while (node) {
      node.style.overflow = "visible";
      node.style.maxHeight = "none";
      node.style.height = "auto";
      node = node.parentElement;
    }
    document.documentElement.style.height = "auto";
    document.body.style.height = "auto";
  });
}
