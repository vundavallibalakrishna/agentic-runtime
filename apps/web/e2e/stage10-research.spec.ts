import { expect, test } from "./support/harness";
import { signInAs } from "./support/sign-in";

const shots = process.env.E2E_SCREENSHOT_DIR ?? "e2e/screenshots";

test("research mode streams a cited report and a sources panel", async ({ page }) => {
  await signInAs(page, "admin@dev.local");
  // Research reads the document library, so the notes it should cite are uploaded first,
  // the way a person adds a document.
  const cookies = await page.context().cookies();
  const csrf = cookies.find((cookie) => cookie.name === "ar_csrf")?.value ?? "";
  const uploaded = await page.request.post("/api/v1/library-documents", {
    headers: { "x-csrf-token": csrf },
    multipart: {
      upload: {
        name: "kite-notes.md",
        mimeType: "text/markdown",
        buffer: Buffer.from(
          "# Kite notes\n\nThe stored notes say a kite needs steady wind of at least eight knots.\n",
        ),
      },
    },
  });
  expect(uploaded.ok(), await uploaded.text()).toBeTruthy();
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Chat" })).toBeVisible();
  await page.getByRole("button", { name: "Research", exact: true }).click();
  await expect(page.getByRole("button", { name: "Research", exact: true })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await page.getByLabel("Message").fill("What do the stored notes say about kites?");
  await page.getByRole("button", { name: "Send" }).click();
  // The panel is headed Research, and counts the sources the report cites.
  await expect(page.getByRole("heading", { name: "Research", exact: true })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText(/\d+ sources?/).first()).toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(/\[1\]/).first()).toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: `${shots}/stage10-research.png`, fullPage: true });
});
