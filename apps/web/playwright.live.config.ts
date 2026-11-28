import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL;
if (!baseURL || !/^https?:\/\//.test(baseURL)) {
  throw new Error("E2E_BASE_URL must name the already-running production UI.");
}
if (!process.env.E2E_LOGIN_EMAIL || !process.env.E2E_LOGIN_PASSWORD) {
  throw new Error("E2E_LOGIN_EMAIL and E2E_LOGIN_PASSWORD are required for normal sign-in.");
}

/** No fixture server, synthetic sessions, route interception or retry-time data reset. */
export default defineConfig({
  testDir: "./live-e2e",
  testMatch: "ui-review.spec.ts",
  outputDir: "./test-results/live-ui-review",
  timeout: 600_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "./test-results/live-ui-review/report.json" }]],
  use: { ...devices["Desktop Chrome"], baseURL, trace: "off", screenshot: "off", video: "off" },
});
