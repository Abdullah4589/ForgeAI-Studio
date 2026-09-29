import { defineConfig, devices } from "@playwright/test";

const apiPort = process.env.E2E_API_PORT ?? "8001";
const webPort = process.env.E2E_WEB_PORT ?? "3100";
const apiUrl = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  testDir: "./e2e",
  // Tests share one backend database, so run them serially for deterministic history state.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${webPort}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "node e2e/start-api.mjs",
      url: `${apiUrl}/api/health`,
      env: { E2E_API_PORT: apiPort, E2E_WEB_PORT: webPort },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      // CI tests the production build; locally the dev server starts faster.
      command: process.env.CI
        ? `npm run build && npm run start -- -p ${webPort}`
        : `npm run dev -- -p ${webPort}`,
      url: `http://localhost:${webPort}/generate`,
      env: { NEXT_PUBLIC_API_URL: apiUrl },
      reuseExistingServer: !process.env.CI,
      timeout: 300_000,
    },
  ],
});
