import { expect, test } from "@playwright/test";

import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

const conversation = {
  id: "block-1",
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
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
        "base64",
      ),
    }),
  );
  await page.route("**/api/v1/conversations/block-1", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(conversation),
    }),
  );
  await signInAs(page, "admin@dev.local");
  await page.goto("/chat?conversation=block-1");
  await expect(page.getByTestId("plan-checklist")).toBeVisible();
  await expect(page.getByTestId("thinking")).toBeVisible();
  await expect(page.getByTestId("tool-call")).toBeVisible();
  await expect(page.getByTestId("interactive-chart")).toBeVisible();
  await expect(page.getByTestId("followups")).toBeVisible();
  await expect(page.getByText("Verified")).toBeVisible();
  await page.getByTestId("plan-checklist").screenshot({ path: `${shots}/stage13-plan.png` });
  await page.getByTestId("thinking").screenshot({ path: `${shots}/stage13-thinking.png` });
  await page.getByTestId("tool-call").screenshot({ path: `${shots}/stage13-tool.png` });
  await page.getByTestId("followups").screenshot({ path: `${shots}/stage13-followups.png` });
  await page.screenshot({ path: `${shots}/stage13-answer.png`, fullPage: true });
});
