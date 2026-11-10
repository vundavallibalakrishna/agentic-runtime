import { readFileSync } from "node:fs";
import { join } from "node:path";
import { expect, type Page, test } from "@playwright/test";

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
      answeredModel: "tenant-model",
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
      body: JSON.stringify({ items: [] }),
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
  await expect(page.getByRole("img", { name: "Counts" })).toHaveCount(2);
  await expect(page.getByTestId("followups")).toBeVisible();
  await expect(page.getByText("Verified")).toBeVisible();
  await expect(page.getByText("Request validation failed")).toHaveCount(0);
  await showWholeTurn(page);
  await page.screenshot({ path: `${shots}/stage13-light.png`, fullPage: true });
  await page.getByRole("button", { name: "Interactive" }).click();
  await expect(page.getByTestId("interactive-chart")).toBeVisible();
  await page.screenshot({ path: `${shots}/stage13-chart.png`, fullPage: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.reload();
  await expect(page.getByTestId("plan-checklist")).toBeVisible();
  await showWholeTurn(page);
  await page.screenshot({ path: `${shots}/stage13-dark.png`, fullPage: true });
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
