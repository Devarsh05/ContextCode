import { test, expect, type Page } from "@playwright/test";

/**
 * Demo-first happy path. Every backend call is intercepted — including a stubbed
 * Turnstile script that auto-clears the challenge (mirroring the always-pass
 * TEST site key) — so the suite needs no live backend and no network.
 *
 * Flow: landing → pick a demo repo card → workspace loads → send a chat message
 * (which mints a demo session via Turnstile and sends X-Demo-Session) → see an
 * answer with citations.
 */

const REPO_ID = "demo-repo-123";

const demosResponse = [
  {
    id: REPO_ID,
    name: "acme/widget",
    url: "https://github.com/acme/widget",
    file_count: 42,
    status: "completed",
  },
];

// getRepo returns a completed status so the workspace renders directly.
const repoResponse = {
  repo_id: REPO_ID,
  url: "https://github.com/acme/widget",
  name: "acme/widget",
  status: "completed",
  file_count: 42,
};

// A single terminal SSE frame so the status hook closes cleanly.
const sseBody = `data: {"status":"completed","progress_pct":100}\n\n`;

const demoSessionResponse = { session_id: "demo-sess-1", expires_in: 3600 };

const chatResponse = {
  answer: "This project is a FastAPI backend that indexes repositories.",
  citations: [
    {
      file_path: "src/server.py",
      function_name: "create_app",
      start_line: 10,
      end_line: 20,
      chunk_type: "function",
      snippet: "def create_app():\n    return app",
    },
  ],
};

// Stub the Turnstile script: define window.turnstile so executeTurnstile()
// resolves with a token immediately, with no real Cloudflare network call.
const turnstileStub = `
  window.turnstile = {
    ready: function (cb) { cb(); },
    render: function (container, opts) {
      setTimeout(function () { opts.callback("test-token"); }, 0);
      return "test-widget";
    },
    remove: function () {},
    reset: function () {},
  };
`;

async function mockBackend(page: Page): Promise<{ chatHeaders: Record<string, string>[] }> {
  const chatHeaders: Record<string, string>[] = [];

  // Lowest priority (registered first): GET /repos/{id}.
  await page.route("**/repos/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: repoResponse });
  });

  // Higher priority than the generic /repos/* above.
  await page.route("**/repos/demos", async (route) => {
    await route.fulfill({ json: demosResponse });
  });

  await page.route("**/repos/*/status", async (route) => {
    await route.fulfill({ contentType: "text/event-stream", body: sseBody });
  });

  await page.route("**/turnstile/v0/api.js", async (route) => {
    await route.fulfill({
      contentType: "application/javascript",
      body: turnstileStub,
    });
  });

  await page.route("**/demo/session", async (route) => {
    await route.fulfill({ json: demoSessionResponse });
  });

  await page.route("**/chat", async (route) => {
    chatHeaders.push(route.request().headers());
    await route.fulfill({ json: chatResponse });
  });

  return { chatHeaders };
}

test("pick a demo repo, mint a session via Turnstile, and chat", async ({
  page,
}) => {
  const { chatHeaders } = await mockBackend(page);

  await page.goto("/");

  // Landing: the demo repo card is the primary entry point.
  await page.getByRole("button", { name: /acme\/widget/ }).click();

  // Workspace loads (completed status short-circuits the progress view).
  await expect(page).toHaveURL(new RegExp(`/repo/${REPO_ID}$`));
  await expect(
    page.getByRole("heading", { name: "Workspace" }),
  ).toBeVisible();

  // Chat: ask a question → Turnstile mints a session → answer with a citation.
  const composer = page.getByLabel("Ask a question about this codebase");
  await composer.fill("What does this project do?");
  await composer.press("Enter");

  await expect(page.getByText(chatResponse.answer)).toBeVisible();
  await expect(page.getByText(/src\/server\.py:10-20/)).toBeVisible();

  // The minted demo session was attached to the chat request.
  expect(chatHeaders).toHaveLength(1);
  expect(chatHeaders[0]["x-demo-session"]).toBe("demo-sess-1");
});
