import { defineConfig, devices } from "@playwright/test";

const port = 3100;
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    screenshot: "only-on-failure",
    trace: "on-first-retry",
    video: "retain-on-failure",
  },
  webServer: {
    command:
      "npm run build:web " +
      "&& cp -R apps/web/public apps/web/.next/standalone/apps/web/public " +
      "&& cp -R apps/web/.next/static apps/web/.next/standalone/apps/web/.next/static " +
      `&& PORT=${port} HOSTNAME=127.0.0.1 node apps/web/.next/standalone/apps/web/server.js`,
    env: {
      NEXT_PUBLIC_API_URL: "http://127.0.0.1:8000",
    },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    url: baseURL,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
