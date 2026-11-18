import { expect, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

// The product bills 600 authenticated requests a minute. A walk has to finish with room to spare.
const PRODUCT_RATE_LIMIT = 600;
const HEADROOM = 200;

const screens = [
  ["/tools", "Tools"],
  ["/knowledge", "Knowledge"],
  ["/memory", "Memory"],
  ["/skills", "Skills"],
  ["/routines", "Routines"],
  ["/admin/channels", "Channels"],
  ["/approvals", "Approvals"],
  ["/runs", "Runs"],
  ["/admin/models", "Models"],
  ["/admin/sandboxes", "Computers"],
  ["/admin/usage", "Usage"],
  ["/admin/quotas", "Quotas"],
  ["/admin/users", "Users"],
  ["/admin/policies", "Policies"],
  ["/reviews", "Reviews"],
  ["/connections", "Connections"],
] as const;

test("a signed-in walk stays under the product rate limit", async ({ page, request }) => {
  test.setTimeout(180_000);
  const reset = await request.post("/api/v1/test/traffic");
  expect(reset.ok()).toBeTruthy();

  await page.goto("/login");
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
  await expect(page.getByText("Loading chat")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Too many requests" })).toHaveCount(0);

  for (const [path, title] of screens) {
    await test.step(title, async () => {
      await page.goto(path);
      await expect(page.getByRole("heading", { name: title, exact: true, level: 1 })).toBeVisible();
      await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "Too many requests" })).toHaveCount(0);
    });
  }

  const traffic = await request.get("/api/v1/test/traffic");
  expect(traffic.ok()).toBeTruthy();
  const body = (await traffic.json()) as {
    peakPerMinute: number;
    total: number;
    sessionChecks: number;
    topPaths: { path: string; count: number }[];
  };
  expect(
    body.peakPerMinute,
    `peak ${body.peakPerMinute} total ${body.total} session ${body.sessionChecks} ${JSON.stringify(body.topPaths)}`,
  ).toBeLessThanOrEqual(PRODUCT_RATE_LIMIT - HEADROOM);
});
