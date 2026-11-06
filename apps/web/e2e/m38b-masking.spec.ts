import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signInAs } from "./support/sign-in";

test("an administrator chooses what is masked in tool results", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/admin/policies");
  const main = page.getByRole("main");
  const card = main.getByRole("region", { name: "Personal data in tool results" });
  await expect(card).toBeVisible();

  // Simple mode: the switch and a sentence. The list of kinds is not on the page.
  await expect(card.getByLabel(/Mask personal data in tool results/)).toBeChecked();
  await expect(card.getByText(/masked: the product default/)).toBeVisible();
  await expect(card.getByLabel("Person's name")).toHaveCount(0);

  // Advanced mode: the kinds, by how they are found, and the bar.
  await main.getByRole("button", { name: "Advanced" }).click();
  await expect(card.getByLabel("Email address")).toBeChecked();
  await expect(card.getByLabel("Payment card number")).toBeChecked();
  const name = card.getByLabel("Person's name");
  await expect(name).not.toBeChecked();
  await expect(card.getByText("Guessed from the sentence")).toBeVisible();

  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  await name.check();
  await card.getByRole("button", { name: "Save" }).click();
  await expect(card.getByRole("status")).toHaveText("Saved. It applies to the next tool result.");

  // The choice is the organisation's: it is there after a reload.
  await page.reload();
  await main.getByRole("button", { name: "Advanced" }).click();
  await expect(card.getByLabel("Person's name")).toBeChecked();

  await card.getByRole("button", { name: "Use the product default" }).click();
  await expect(card.getByRole("status")).toHaveText("The product default is back.");
  await expect(card.getByLabel("Person's name")).not.toBeChecked();
  await expect(card.getByRole("button", { name: "Use the product default" })).toHaveCount(0);
});
