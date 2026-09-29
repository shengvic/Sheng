import { defineConfig } from "@playwright/test";

// Run via scripts/e2e.sh, which boots Postgres, the API and `next dev` first.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 20_000 },
  retries: 0,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
