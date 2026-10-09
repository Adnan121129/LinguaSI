import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive the real web app against a running LinguaSI API (Mock AI Mode is enough).
// Start the API first (see the README), then: npm run e2e
// E2E_BASE_URL points the tests at an already running web app (for example the Docker Compose stack);
// without it, Playwright reuses a dev server on :3000 or starts the production build (npm run build first).
const baseURL = process.env.E2E_BASE_URL ?? "http://localhost:3000";
const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE;

export default defineConfig({
  testDir: "./e2e",
  // The acceptance journey covers every core module in one learner session.
  timeout: 6 * 60_000,
  expect: { timeout: 20_000 },
  workers: 1,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run start",
        url: `${baseURL}/login`,
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      },
});
