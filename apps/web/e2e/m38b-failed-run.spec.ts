import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signInAs } from "./support/sign-in";

// A model that cannot answer: a provider at an address that does not exist. The spec
// registers it as an administrator would, points a name of its own at it, and chats
// through that name, so no other conversation is touched.
test("a failed run is shown as one, with its reason and a way to try again", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  const cookies = await page.context().cookies();
  const token = cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
  const headers = { "x-csrf-token": token };
  const stamp = Date.now();
  const alias = `dead-${stamp}`;
  const provider = await page.request.post("/api/v1/model-providers", {
    headers,
    data: {
      name: `Dead ${stamp}`,
      kind: "openai_compatible",
      baseUrl: "https://dead.invalid/v1",
      apiKey: "not-a-real-key",
    },
  });
  expect(provider.ok(), await provider.text()).toBeTruthy();
  const providerId = (await provider.json()).id as string;
  const model = await page.request.post("/api/v1/models", {
    headers,
    data: { providerId, upstreamModel: "dead/model", name: `Dead ${stamp}`, kind: "chat" },
  });
  expect(model.ok(), await model.text()).toBeTruthy();
  const modelId = (await model.json()).id as string;
  const named = await page.request.post("/api/v1/model-aliases", {
    headers,
    data: { alias, kind: "chat", primaryModelId: modelId },
  });
  expect(named.ok(), await named.text()).toBeTruthy();
  const aliasId = (await named.json()).id as string;

  try {
    await page.goto("/chat");
    const main = page.getByRole("main");
    await main.getByRole("combobox", { name: "Model" }).selectOption(alias);
    await main.getByLabel("Message").fill("Say hello in three words.");
    await main.getByRole("button", { name: "Send" }).click();

    // The reply is a failure, not an answer: it says so, gives the reason, and offers a retry.
    const failed = main.getByRole("alert");
    await expect(failed).toBeVisible({ timeout: 60_000 });
    await expect(failed).toContainText("This reply could not be made.");
    await expect(failed).toContainText("did not answer");
    await expect(failed.getByRole("button", { name: "Try again" })).toBeVisible();
    await expect(main.getByRole("button", { name: "Regenerate" })).toHaveCount(0);

    await page.waitForLoadState("networkidle");
    const report = await new AxeBuilder({ page }).analyze();
    expect(report.violations).toEqual([]);

    // It is remembered as a failure: the same after a reload.
    await page.reload();
    await expect(main.getByRole("alert")).toContainText("This reply could not be made.");

    // Trying again starts a new run, which fails the same way and says so again.
    await main.getByRole("alert").getByRole("button", { name: "Try again" }).click();
    await expect(main.getByRole("alert").last()).toContainText("did not answer", {
      timeout: 60_000,
    });
  } finally {
    await page.request.delete(`/api/v1/model-aliases/${aliasId}`, { headers });
    await page.request.delete(`/api/v1/models/${modelId}`, { headers });
    await page.request.delete(`/api/v1/model-providers/${providerId}`, { headers });
  }
});
