import { defineConfig, devices } from "@playwright/test";

import { apiPort, webPort } from "./dev-env";

const root = "../..";
const inCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  // The dev server compiles a page on its first visit, which can pass five seconds on a CI runner.
  expect: { timeout: 10_000 },
  // In CI a test that passes on a later try is reported as flaky, by name, and the job passes.
  // A test that fails every try still fails the job. Locally there is no retry.
  retries: inCi ? 2 : 0,
  // One API process and one in-memory tenant. Parallel files race on that store.
  workers: 1,
  use: { baseURL: `http://localhost:${webPort}`, ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: `uv run --directory ${root} ar-api`,
      url: `http://127.0.0.1:${apiPort}/healthz`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm dev",
      ...(process.env.AR_E2E_WEB_CWD ? { cwd: process.env.AR_E2E_WEB_CWD } : {}),
      url: `http://localhost:${webPort}/healthz`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
