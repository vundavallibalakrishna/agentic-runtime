import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

test("an edited snake_case argument survives approve", async ({ page, request }) => {
  const created = await request.get("/api/v1/test/review-link");
  expect(created.ok()).toBeTruthy();
  const body = (await created.json()) as { token: string };
  await page.goto(`/review/${body.token}`);
  await expect(page.getByRole("heading", { name: "Review this request" })).toBeVisible();
  const field = page.getByLabel("target_date");
  await expect(field).toHaveValue("2026-01-02");
  await field.fill("2026-02-03");
  await page.getByLabel("Reason").fill("Corrected the date");
  const form = await new AxeBuilder({ page }).analyze();
  expect(form.violations).toEqual([]);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText(/Approved|pending/)).toBeVisible();
  const saved = await request.get("/api/v1/test/review-result");
  expect(saved.ok()).toBeTruthy();
  const result = (await saved.json()) as { arguments: Record<string, string> };
  expect(result.arguments.target_date).toBe("2026-02-03");
  expect(result.arguments.targetDate).toBeUndefined();
});
