import AxeBuilder from "@axe-core/playwright";
import { expect, type Page, test } from "@playwright/test";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "../../docs/testing/m5";

test.describe.configure({ mode: "serial" });
test.use({ video: "on" });
test.setTimeout(120_000);

async function signIn(page: Page, email = "admin@dev.local") {
  await page.goto("/login");
  await signInAs(page, `${email}`);
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
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

// The flow is one chain of state but far too long to finish inside a single test budget on a
// loaded runner, where it used to run out mid-step. It is split into serial phases that share
// the server-side demo tenant (one API process) and carry the two ids they need between them;
// each phase re-signs in and gets its own budget, so no single test has to complete the lot.
let approverId = "";
let conversation = "";

test("approve a pet", async ({ page }) => {
  await signIn(page, "approver@dev.local");
  approverId = await page.evaluate(async () => {
    const response = await fetch("/api/v1/auth/session", { credentials: "include" });
    const body = (await response.json()) as { user: { id: string } };
    return body.user.id;
  });
  await signIn(page);
  await page.goto("/chat?agent=desk");
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await page.getByLabel("Message").fill("Create a pet named Fido");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval before this tool runs.").first()).toBeVisible({
    timeout: 20_000,
  });
  conversation = new URL(page.url()).searchParams.get("conversation") ?? "";
  expect(conversation).toBeTruthy();

  await page.goto("/approvals");
  await expect(page.getByRole("heading", { name: "Approvals" })).toBeVisible();
  const pet = page.locator("li").filter({ hasText: "petstore.create_pet" }).first();
  await expect(pet).toBeVisible();
  const inbox = await new AxeBuilder({ page }).analyze();
  expect(inbox.violations).toEqual([]);
  await capture(page, "inbox");
  await pet.getByRole("button", { name: "Approve" }).click();
  await expect(pet).toBeHidden({ timeout: 20_000 });

  await page.goto(`/chat?conversation=${conversation}`);
  await expect(page.getByText(/Created pet \d+\./).first()).toBeVisible({ timeout: 20_000 });
  await capture(page, "pet-created");
});

test("sign a review", async ({ page }) => {
  await signIn(page);
  await page.goto("/reviews");
  await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
  const reviews = await new AxeBuilder({ page }).analyze();
  expect(reviews.violations).toEqual([]);
  await page.getByRole("link", { name: /artifact/ }).click();
  await expect(page.getByText("I reviewed the sample output.")).toBeVisible();
  await page.getByRole("button", { name: "Sign" }).click();
  await expect(page.getByText("signed")).toBeVisible({ timeout: 20_000 });
  await capture(page, "review-signed");
});

test("author and activate a policy", async ({ page }) => {
  expect(approverId, "the approve-a-pet phase must run first").toBeTruthy();
  await signIn(page);
  await page.goto("/admin/policies");
  await expect(
    page.getByRole("heading", { name: "Policies", exact: true, level: 1 }),
  ).toBeVisible();
  await page.getByLabel("Name").fill("Deletes wait");
  await page.getByRole("button", { name: "Advanced" }).click();
  await page.getByLabel("Document").fill(
    JSON.stringify({
      rules: [
        {
          id: "del",
          effect: "requireApproval",
          message: "confirm the delete",
          match: { tools: ["petstore.delete_pet"] },
          approval: { approvers: { mode: "users", users: [approverId] } },
        },
      ],
    }),
  );
  await page.getByRole("button", { name: "Save policy" }).click();
  await expect(page.getByRole("heading", { name: "Deletes wait" })).toBeVisible();
  await page.getByRole("button", { name: "Activate" }).click();
  await expect(page.getByText("active").first()).toBeVisible({ timeout: 20_000 });
  const policies = await new AxeBuilder({ page }).analyze();
  expect(policies.violations).toEqual([]);
  await capture(page, "policies");

  // The bundle contract permits up to 15 seconds for sidecar propagation.
  const opaUrl = process.env.AR_OPA_URL;
  if (opaUrl) {
    const session = await (await page.request.get("/api/v1/auth/session")).json();
    await expect
      .poll(
        async () => {
          const response = await page.request.post(`${opaUrl}/v1/data/ar/policy/decision`, {
            data: {
              input: {
                tenant_id: session.tenant.id,
                tool: {
                  qualified_name: "petstore.delete_pet",
                  name: "delete_pet",
                  server_slug: "petstore",
                  risk_class: "W3",
                },
                user: { id: session.user.id, groups: [], teams: [] },
                agent: { slug: "desk", overrides: {} },
                run: { trigger: "chat", channel: "web" },
                args: { petId: 1 },
              },
            },
          });
          return (await response.json()).result?.decision;
        },
        { timeout: 15_000, intervals: [250, 500, 1000] },
      )
      .toBe("require_approval");
  }
});

test("delete a pet behind the new policy", async ({ page }) => {
  expect(conversation, "the approve-a-pet phase must run first").toBeTruthy();
  await signIn(page);
  await page.goto(`/chat?agent=desk&conversation=${conversation}`);
  await expect(page.getByText(/Created pet \d+\./).first()).toBeVisible();
  await expect(page.locator("#agent-picker option:checked")).toHaveText("Desk");
  await page.getByLabel("Message").fill("Delete pet 1");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Waiting for approval before this tool runs.").first()).toBeVisible({
    timeout: 20_000,
  });
  await signIn(page, "approver@dev.local");
  await page.goto("/approvals");
  await page.getByRole("link", { name: "petstore.delete_pet" }).click();
  await expect(page.getByRole("button", { name: "Confirm it is you" })).toBeVisible();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("approved").first()).toBeVisible({ timeout: 20_000 });
  await signIn(page);
  await page.goto(`/chat?conversation=${conversation}`);
  await expect(page.getByText(/Deleted pet 1\./).first()).toBeVisible({ timeout: 20_000 });
});
