import { defineConfig, devices } from "@playwright/test";

/**
 * Acceptance-only browser configuration.
 *
 * It never starts the servers itself: the acceptance run is driven against the one
 * canonical runtime (Vite on 5173 proxying the API to 127.0.0.1:8000) pointed at a
 * disposable validation database, and starting a second copy here would quietly split
 * that state in two.
 *
 * The browser is the machine's installed Chromium channel rather than a Playwright
 * download, so the acceptance suite adds no browser binaries to the repository.
 */
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/.artifacts",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:5173",
    locale: "ar",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
    video: "off",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], channel: "msedge", viewport: { width: 1440, height: 900 } },
    },
    {
      name: "tablet",
      use: { ...devices["Desktop Chrome"], channel: "msedge", viewport: { width: 768, height: 1024 } },
      testMatch: /responsive\.spec\.js/,
    },
    {
      name: "mobile",
      use: { ...devices["Desktop Chrome"], channel: "msedge", viewport: { width: 390, height: 844 } },
      testMatch: /responsive\.spec\.js/,
    },
  ],
});
