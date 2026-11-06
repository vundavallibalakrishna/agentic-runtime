import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signInAs } from "./support/sign-in";

test("an administrator lists the hosts tools may reach", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/admin/policies");
  const card = page.getByRole("main").getByRole("region", { name: "Web access" });
  await expect(card).toBeVisible();
  await expect(card.getByLabel("Host", { exact: true })).toHaveValue("");

  const host = `spec-${Date.now()}.example.org`;
  await card.getByLabel("Host", { exact: true }).fill(host);
  await card.getByRole("button", { name: "Add host" }).click();
  await expect(card.getByRole("status")).toHaveText(
    `${host} can now be reached. It applies to the next tool call.`,
  );
  await expect(card.getByRole("list", { name: "Hosts tools may reach" })).toContainText(host);

  // A name that is not a host is refused in the API's words, and stays typed in.
  await card.getByLabel("Host", { exact: true }).fill("not a host");
  await card.getByRole("button", { name: "Add host" }).click();
  await expect(card.getByRole("alert")).toContainText("egress domain is invalid");
  await expect(card.getByLabel("Host", { exact: true })).toHaveValue("not a host");

  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  // The list is the organisation's: it is there after a reload, and a host can be taken off.
  await page.reload();
  await expect(card.getByRole("list", { name: "Hosts tools may reach" })).toContainText(host);
  await card.getByRole("button", { name: `Remove ${host}` }).click();
  await expect(card.getByRole("status")).toHaveText(`${host} can no longer be reached.`);
  await expect(card.getByRole("button", { name: `Remove ${host}` })).toHaveCount(0);
});
