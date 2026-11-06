import type { Page } from "@playwright/test";

/**
 * Sign in as one of the demo tenant's people.
 *
 * The door is in the browser-test harness (`services/api/tests/support/e2e_server.py`),
 * not in the product: it starts a session and sends the browser to the workspace.
 */
export async function signInAs(page: Page, email: string): Promise<void> {
  await page.goto(`${SIGN_IN_PATH}?email=${encodeURIComponent(email)}`);
}

export const SIGN_IN_PATH = "/api/v1/test/sign-in";
