import { defineConfig, devices } from "@playwright/test";

import { apiPort, webPort } from "./dev-env";

const root = "../..";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
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
      url: `http://localhost:${webPort}/healthz`,
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
