import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/screen-layouts";
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

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in as admin@dev.local", exact: true }).click();
  await expect(page.getByRole("heading", { name: "What can we work on?" })).toBeVisible();
}

async function fits(page: Page) {
  expect(
    await page.evaluate(() => {
      const main = document.querySelector("main");
      return (
        document.documentElement.scrollWidth <= window.innerWidth &&
        !!main &&
        main.scrollWidth <= main.clientWidth
      );
    }),
  ).toBe(true);
}

for (const theme of ["light", "dark"] as const) {
  for (const width of [1280, 375]) {
    test(`${theme} management screens fit and pass axe at ${width}px`, async ({ page }) => {
      test.setTimeout(180_000);
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript((value) => localStorage.setItem("ar-theme", value), theme);
      await signIn(page);
      for (const [path, title] of screens) {
        await test.step(title, async () => {
          await page.goto(path);
          await expect(
            page.getByRole("heading", { name: title, exact: true, level: 1 }),
          ).toBeVisible();
          await expect(
            page.getByRole("button", { name: "Dev Admin admin@dev.local" }),
          ).toBeVisible();
          await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
          await fits(page);
          expect((await new AxeBuilder({ page }).analyze()).violations, title).toEqual([]);
          const panel = page.locator(".management-form");
          if (await panel.count()) {
            // The data leads both visually and in keyboard/reading order.
            const positions = await panel.evaluate((element) => {
              const data = element.previousElementSibling;
              if (!data) throw new Error("Missing data column");
              const a = data.getBoundingClientRect();
              const b = element.getBoundingClientRect();
              return {
                dataLeft: a.left,
                dataRight: a.right,
                dataBottom: a.bottom,
                formLeft: b.left,
                formTop: b.top,
              };
            });
            if (width === 1280) expect(positions.formLeft).toBeGreaterThan(positions.dataRight);
            else expect(positions.formTop).toBeGreaterThanOrEqual(positions.dataBottom);
          }
          if (title === "Approvals" || title === "Channels") {
            await page.screenshot({
              path: `${shots}/${title.toLowerCase()}-${theme}-${width}.png`,
              fullPage: true,
            });
          }
          const advanced = page.getByRole("button", { name: "Advanced", exact: true });
          if (await advanced.count()) {
            await advanced.click();
            await expect(advanced).toHaveAttribute("aria-pressed", "true");
            await fits(page);
            expect(
              (await new AxeBuilder({ page }).analyze()).violations,
              `${title} advanced`,
            ).toEqual([]);
            await page.getByRole("button", { name: "Simple", exact: true }).click();
          }
        });
      }
    });
  }
}

test("approvals only offers a decision comment for pending work, with loading and retry", async ({
  page,
}) => {
  await signIn(page);
  let state: "empty" | "pending" | "error" = "empty";
  await page.route("**/api/v1/approvals?**", (route) =>
    route.fulfill({
      status: state === "error" ? 503 : 200,
      contentType: "application/json",
      body: JSON.stringify(
        state === "error"
          ? { detail: "Approval service is unavailable." }
          : {
              items:
                state === "pending"
                  ? [
                      {
                        id: "pending-layout-test",
                        qualifiedName: "mail.send",
                        status: "pending",
                        riskClass: "W2",
                        argsHash: "example",
                        preview: { title: "Send a status update" },
                      },
                    ]
                  : [],
            },
      ),
    }),
  );
  await page.goto("/approvals");
  await expect(page.getByText("Nothing is waiting for you.")).toBeVisible();
  await expect(page.getByLabel("Comment", { exact: true })).toHaveCount(0);
  state = "pending";
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.getByText("Send a status update")).toBeVisible();
  await expect(page.getByLabel("Comment", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve", exact: true })).toBeVisible();
  state = "error";
  await page.getByRole("button", { name: "Requested", exact: true }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Approval service is unavailable." }),
  ).toBeVisible();
  await expect(page.getByLabel("Comment", { exact: true })).toHaveCount(0);
  state = "empty";
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByText("Nothing is waiting for you.")).toBeVisible();
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/approvals?**", async (route) => {
    await gate;
    await route.fulfill({ json: { items: [] } });
  });
  await page.getByRole("button", { name: "Refresh", exact: true }).click();
  await expect(page.locator('[aria-busy="true"]')).toBeVisible();
  release();
  await expect(page.getByText("Nothing is waiting for you.")).toBeVisible();
  await page.route("**/api/v1/standing-approvals", (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "missing-tool-grant",
            tool: { name: "" },
            routine: { id: "weekly-routine" },
            expiresAt: "2026-10-27T12:00:00Z",
            revokedAt: "2026-10-26T12:00:00Z",
          },
        ],
      },
    }),
  );
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await expect(page.getByText("Tool unavailable", { exact: true })).toBeVisible();
  await expect(page.getByText("Revoked", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "View routine" })).toHaveAttribute(
    "href",
    "/routines/weekly-routine",
  );
  await expect(page.getByRole("button", { name: "Revoke", exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 900 });
  await fits(page);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
