import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "./support/harness";

import { signInAs } from "./support/sign-in";

test("two files sent with a message are shown on it, and after a reload", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  await page.goto("/chat");
  const main = page.getByRole("main");

  // Both files go in at once. Each is shown before sending, with its type and size, and
  // one can be taken off again.
  await main.getByLabel("Attach file").setInputFiles([
    { name: "orders.csv", mimeType: "text/csv", buffer: Buffer.from("region,total\nnorth,120\n") },
    {
      name: "notes.md",
      mimeType: "",
      buffer: Buffer.from("# Notes\n\nThe north dock opens at 6.\n"),
    },
    { name: "extra.txt", mimeType: "text/plain", buffer: Buffer.from("not needed\n") },
  ]);
  const pending = main.getByRole("list", { name: "Attached files" });
  await expect(pending.getByRole("link", { name: "orders.csv" })).toBeVisible();
  // A file the browser gave no type is typed by its name.
  await expect(pending).toContainText("notes.md");
  await expect(pending).toContainText("text/markdown");
  await pending.getByRole("button", { name: "Remove extra.txt" }).click();
  await expect(pending).not.toContainText("extra.txt");

  await main.getByLabel("Message").fill("What do these files say?");
  await main.getByRole("button", { name: "Send" }).click();
  await expect(main.getByRole("button", { name: "Stop" })).toBeHidden({ timeout: 60_000 });

  // The sent message carries both files, each opening its download.
  const sent = main.getByRole("article").filter({ hasText: "What do these files say?" }).first();
  const files = sent.getByRole("list", { name: "Attached files" });
  await expect(files.getByRole("link", { name: "orders.csv" })).toHaveAttribute(
    "href",
    /\/api\/v1\/files\/.+\/content/,
  );
  await expect(files.getByRole("link", { name: "notes.md" })).toBeVisible();
  await expect(files).toContainText("text/csv, 23 B");
  await expect(main.getByRole("list", { name: "Attached files" })).toHaveCount(1);

  await page.waitForLoadState("networkidle");
  const report = await new AxeBuilder({ page }).analyze();
  expect(report.violations).toEqual([]);

  await page.reload();
  const again = main.getByRole("article").filter({ hasText: "What do these files say?" }).first();
  await expect(again.getByRole("link", { name: "orders.csv" })).toBeVisible();
  await expect(again.getByRole("link", { name: "notes.md" })).toBeVisible();
});
