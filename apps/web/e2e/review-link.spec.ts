import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

test("a review link that is not valid says so", async ({ page }) => {
  await page.goto("/review/not-a-real-token");
  await expect(page.getByRole("heading", { name: "Review this request" })).toBeVisible();
  await expect(page.getByText("This review link is not valid, or it has expired.")).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});

test("the review page edits any field and approves with a reason", async ({ page }) => {
  await page.route("**/api/v1/review/good-token", async (route) => {
    await route.fulfill({
      json: {
        qualifiedName: "general.http",
        status: "pending",
        argsHash: "abc",
        arguments: { title: "Draft", count: 1, ready: false },
        schema: {
          type: "object",
          required: ["title"],
          properties: {
            title: { type: "string" },
            count: { type: "integer" },
            ready: { type: "boolean" },
          },
        },
        preview: { title: "Send a request", summary: "One item" },
      },
    });
  });
  let posted: { decision?: string; comment?: string; arguments?: { title?: string } } = {};
  await page.route("**/api/v1/review/good-token:decide", async (route) => {
    posted = route.request().postDataJSON();
    await route.fulfill({ json: { status: "pending" } });
  });

  await page.goto("/review/good-token");
  await expect(page.getByRole("heading", { name: "Review this request" })).toBeVisible();
  await expect(page.getByText("One item")).toBeVisible();
  const form = await new AxeBuilder({ page }).analyze();
  expect(form.violations).toEqual([]);
  await page.getByLabel("title").fill("Final");
  await page.getByLabel("Reason").fill("Corrected the title");
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(
    page.getByText("Approved. The original values are kept alongside any you changed."),
  ).toBeVisible();
  expect(posted.decision).toBe("approve");
  expect(posted.comment).toBe("Corrected the title");
  expect(posted.arguments?.title).toBe("Final");
});
