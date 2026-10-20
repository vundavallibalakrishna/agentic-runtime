import { defineConfig, devices } from "@playwright/test";

const root = "../..";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: { baseURL: "http://localhost:3000", ...devices["Desktop Chrome"] },
  webServer: [
    {
      command: `uv run --directory ${root} ar-api`,
      url: "http://127.0.0.1:8000/healthz",
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:3000/healthz",
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
