import { expect, test } from "./support/harness";

import { signInAs } from "./support/sign-in";

test("a message sent while a new chat is still being created stays on the screen", async ({
  page,
}) => {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  await signInAs(page, "admin@dev.local");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByLabel("Message")).toBeVisible();
  // Hold the new conversation back, as a slow connection would, so the message is
  // sent before it exists.
  let created = 0;
  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    created += 1;
    await new Promise((done) => setTimeout(done, 1500));
    return route.continue();
  });
  await page.locator("aside").getByRole("button", { name: "New chat" }).first().click();
  await page.getByLabel("Message").fill("Say hello in three words.");
  await page.getByRole("button", { name: "Send" }).click();
  const said = page
    .getByTestId("message-scroll")
    .getByText("Say hello in three words.", { exact: true });
  await expect(said).toBeVisible({ timeout: 15_000 });
  // The empty conversation used to open over the message a moment later.
  await page.waitForTimeout(2500);
  await expect(said).toBeVisible();
  // One conversation was made, and the message went to it.
  expect(created).toBe(1);
  await expect(page).toHaveURL(/conversation=/);
});
