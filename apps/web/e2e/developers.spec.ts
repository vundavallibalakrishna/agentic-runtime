import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

import { signInAs } from "./support/sign-in";

test("the developer notes show this workspace's address in the samples", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/developers");
  await expect(page.getByRole("heading", { name: "Developer notes" })).toBeVisible();
  const note = page.getByTestId("note");
  await expect(note.getByRole("heading", { name: "Connect your platform" })).toBeVisible();
  const origin = new URL(page.url()).origin;
  await expect(note).toContainText(`${origin}/api/v1/files:upload`);
  await expect(note).not.toContainText("{{BASE_URL}}");
  await page.getByRole("button", { name: "Chat from your application" }).click();
  await expect(note.getByRole("heading", { name: "Mention documents" })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("the guide can be read without signing in", async ({ page }) => {
  await page.goto("/developer-guide");
  await expect(page.getByRole("heading", { name: "Developer notes" })).toBeVisible();
  await expect(page.getByTestId("note")).toContainText("What you need from the workspace owner");
  // Nothing of a workspace is on it: the agent in the samples is a placeholder.
  await expect(page.getByTestId("note")).toContainText("/v1/agents/<agent-slug>:run");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("a service account is created with what it will do, and its key is shown once", async ({
  page,
}) => {
  const json = (body: unknown) => ({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
  const accounts: object[] = [];
  await page.route("**/api/v1/service-accounts", (route) => {
    if (route.request().method() === "POST") {
      accounts.push({ id: "sa-1", name: "Billing sync", status: "active" });
      return route.fulfill(json(accounts[0]));
    }
    return route.fulfill(json({ items: accounts }));
  });
  await page.route("**/api/v1/service-accounts:capabilities", (route) =>
    route.fulfill(
      json({ items: [{ key: "chat", role: "member", permissions: ["chat:use", "agents:read"] }] }),
    ),
  );
  await page.route("**/api/v1/role-assignments", (route) =>
    route.request().method() === "POST" ? route.fulfill(json({ id: "a-1" })) : route.continue(),
  );
  await page.route("**/api/v1/api-keys**", (route) =>
    route.request().method() === "POST"
      ? route.fulfill(json({ id: "k-1", prefix: "ab12", key: "ak_ab12.sk_shown-once" }))
      : route.fulfill(
          json({
            items: accounts.length
              ? [{ id: "k-1", prefix: "ab12", scopes: [], lastUsedAt: null, revokedAt: null }]
              : [],
          }),
        ),
  );
  await signInAs(page, "admin@dev.local");
  await page.goto("/admin/developers/keys");
  await expect(page.getByRole("heading", { name: "Service accounts and keys" })).toBeVisible();
  await expect(page.getByText("No service accounts yet.")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByLabel("Name").fill("Billing sync");
  await page.getByLabel("Chat with agents and send them files").check();
  await expect(page.getByTestId("grants")).toContainText("chat:use, agents:read");
  await page.getByRole("button", { name: "Create account and key" }).click();
  const shown = page.getByTestId("new-secret");
  await expect(shown).toContainText("ak_ab12.sk_shown-once");
  await expect(shown).toContainText("This is the only time the key is shown.");
  await expect(page.getByRole("button", { name: "Delete Billing sync" })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("typing @ opens the document picker and a picked document goes on the message", async ({
  page,
}) => {
  await page.route("**/api/v1/library-documents", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          { id: "d1", fileId: "f1", title: "Access policy", mediaType: "text/markdown" },
          { id: "d2", fileId: "f2", title: "Travel policy", mediaType: "text/markdown" },
        ],
      }),
    }),
  );
  await signInAs(page, "admin@dev.local");
  await page.goto("/chat");
  const box = page.getByRole("textbox", { name: "Message" });
  await box.click();
  await page.keyboard.type("Compare @");
  const picker = page.getByTestId("document-picker");
  await expect(picker).toBeVisible();
  // The @ is not part of the message.
  await expect(box).toHaveValue("Compare ");
  await picker.getByLabel("Find a document").fill("travel");
  await expect(picker.getByLabel("Access policy")).toHaveCount(0);
  await picker.getByLabel("Travel policy").check();
  expect(
    (await new AxeBuilder({ page }).include('[data-testid="document-picker"]').analyze())
      .violations,
  ).toEqual([]);
  await picker.getByRole("button", { name: "Done" }).click();
  await expect(picker).toHaveCount(0);
  await expect(page.getByText("Travel policy")).toBeVisible();
  await expect(box).toBeFocused();
});
