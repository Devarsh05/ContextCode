import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the ContextCode frontend. The suite is fully mocked — every
 * backend call is intercepted via page.route — so it runs against a local Next
 * server with no live backend, indexing, or network.
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  // The Next dev server compiles each route lazily on first request. With
  // parallel workers contending on that single compiler, a cold compile of
  // /repo/[id] can take several seconds — enough to push a web-first assertion
  // (notably the first toHaveURL after navigation) past the 5s default and fail
  // with "page stayed at /". A roomier timeout absorbs the cold compile so the
  // suite is deterministic on slow/CI machines without weakening any assertion.
  expect: { timeout: 15_000 },
  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
