import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

import { signInAs } from "./support/sign-in";

// The stand-in model server the harness registered. Its address is read from the page,
// so the spec registers a provider that really answers, as an administrator would.
const STAND_IN = /http:\/\/127\.0\.0\.1:\d+\/s\/embeddings\/v1/;

test("an administrator adds, points, tests and removes models on the Models screen", async ({
  page,
}) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/admin/models");
  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Models", exact: true })).toBeVisible();
  await expect(main.getByRole("heading", { name: "What the product uses" })).toBeVisible();

  // The form starts empty: no vendor address, model id or name is typed in for anyone.
  for (const label of ["Name", "Base URL", "API key"]) {
    await expect(main.getByLabel(label, { exact: true })).toHaveValue("");
  }
  await expect(main.getByRole("button", { name: /Local fake/ })).toHaveCount(0);

  const address = (await main.getByText(STAND_IN).first().innerText()).trim();
  await main.getByLabel("Name", { exact: true }).fill("Spec provider");
  await main.getByLabel("Base URL", { exact: true }).fill(address);
  await main.getByRole("button", { name: "Add provider" }).click();

  // The next step is a model, so its dialog opens by itself.
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Model id").fill("spec-embed");
  await dialog.getByLabel("Kind").selectOption("embedding");
  await dialog.getByRole("button", { name: "Add model" }).click();
  await expect(dialog).toBeHidden();
  await expect(main.getByRole("heading", { name: "Spec provider", exact: true })).toBeVisible();

  // One model is tested by itself, against the provider.
  await main.getByRole("button", { name: "Test spec-embed" }).click();
  await expect(
    main.getByText("Returned a vector of 1024 numbers.", { exact: false }),
  ).toBeVisible();

  // The name the product uses for search is pointed at the new model, and tested.
  await main.getByLabel("Model for Search by meaning").selectOption({ label: "spec-embed" });
  await expect(main.getByRole("button", { name: "Clear Search by meaning" })).toBeVisible();
  await main.getByRole("button", { name: "Test Search by meaning" }).click();
  await expect(main.getByText("It answered.").first()).toBeVisible();

  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  // Removal goes from the outside in, and a refusal says what to do.
  await main.getByRole("button", { name: "Remove Spec provider" }).click();
  await dialog.getByRole("button", { name: "Remove" }).click();
  await expect(dialog.getByRole("alert")).toContainText("still has models");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  await main.getByRole("button", { name: "Remove spec-embed" }).click();
  await dialog.getByRole("button", { name: "Remove" }).click();
  await expect(dialog.getByRole("alert")).toContainText("These aliases still use this model");
  await dialog.getByRole("button", { name: "Cancel" }).click();

  await main.getByRole("button", { name: "Clear Search by meaning" }).click();
  await dialog.getByRole("button", { name: "Remove" }).click();
  await expect(dialog).toBeHidden();
  await expect(main.getByRole("button", { name: "Clear Search by meaning" })).toHaveCount(0);

  await main.getByRole("button", { name: "Remove spec-embed" }).click();
  await dialog.getByRole("button", { name: "Remove" }).click();
  await expect(dialog).toBeHidden();
  await main.getByRole("button", { name: "Remove Spec provider" }).click();
  await dialog.getByRole("button", { name: "Remove" }).click();
  await expect(dialog).toBeHidden();
  await expect(main.getByRole("heading", { name: "Spec provider", exact: true })).toHaveCount(0);
});
