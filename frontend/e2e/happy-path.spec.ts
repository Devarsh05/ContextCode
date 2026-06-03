import { test, expect, type Page } from "@playwright/test";

/**
 * Deterministic end-to-end happy path. Every backend call is intercepted, so the
 * test needs no live backend, no real indexing, and no network — including a
 * scripted text/event-stream response for the SSE progress endpoint.
 *
 * Flow: enter a repo URL → progress view streams to completion → workspace loads
 * → send a chat message → see an answer with citations → open the Graph tab →
 * see nodes.
 */

const REPO_ID = "test-repo-123";

const indexResponse = {
  repo_id: REPO_ID,
  job_id: "job-1",
  status: "indexing",
};

// getRepo returns a non-terminal status so the progress view renders rather than
// short-circuiting straight to the workspace.
const repoResponse = {
  repo_id: REPO_ID,
  url: "https://github.com/acme/widget",
  name: "acme/widget",
  status: "indexing",
  file_count: 42,
};

// Two SSE frames: an in-progress frame, then the terminal "completed" frame that
// causes the hook to close the EventSource before any reconnect/onerror.
const sseBody =
  `data: {"status":"indexing","progress_pct":40,"current_stage":"Parsing code"}\n\n` +
  `data: {"status":"completed","progress_pct":100}\n\n`;

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

const graphResponse = {
  repo_id: REPO_ID,
  node_count: 2,
  edge_count: 1,
  nodes: [
    {
      file_path: "app/main.py",
      language: "python",
      import_count: 1,
      imported_by_count: 2,
    },
    {
      file_path: "app/utils.py",
      language: "python",
      import_count: 0,
      imported_by_count: 1,
    },
  ],
  edges: [
    {
      source_file: "app/main.py",
      target_file: "app/utils.py",
      import_raw: "from app import utils",
    },
  ],
};

async function mockBackend(page: Page) {
  // Registered first → lowest priority. GET-only; anything else falls through to
  // the more specific routes registered below (Playwright matches in reverse).
  await page.route("**/repos/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: repoResponse });
  });

  await page.route("**/repos/index", async (route) => {
    await route.fulfill({ json: indexResponse });
  });

  await page.route("**/repos/*/status", async (route) => {
    // A small delay so the progress view is observable before completion.
    await new Promise((resolve) => setTimeout(resolve, 600));
    await route.fulfill({ contentType: "text/event-stream", body: sseBody });
  });

  // Regex (not glob) so it matches the `?resolved_only=...` query string.
  await page.route(/\/repos\/[^/]+\/graph/, async (route) => {
    await route.fulfill({ json: graphResponse });
  });

  await page.route("**/chat", async (route) => {
    await route.fulfill({ json: chatResponse });
  });
}

test("index a repo, chat with citations, and view the graph", async ({
  page,
}) => {
  await mockBackend(page);

  await page.goto("/");

  // Landing → submit a valid GitHub URL.
  await page
    .getByLabel("Public GitHub repository URL")
    .fill("https://github.com/acme/widget");
  await page.getByRole("button", { name: "Analyze" }).click();

  // Progress view streams while the SSE response is pending.
  await expect(page).toHaveURL(new RegExp(`/repo/${REPO_ID}$`));
  await expect(page.getByText("Indexing repository")).toBeVisible();

  // SSE reaches "completed" → workspace loads.
  await expect(
    page.getByRole("heading", { name: "Workspace" }),
  ).toBeVisible();

  // Chat tab: ask a question, get an answer with a citation.
  const composer = page.getByLabel("Ask a question about this codebase");
  await composer.fill("What does this project do?");
  await composer.press("Enter");

  await expect(page.getByText(chatResponse.answer)).toBeVisible();
  await expect(page.getByText(/src\/server\.py:10-20/)).toBeVisible();

  // Graph tab: nodes render.
  await page.getByRole("tab", { name: "Graph" }).click();
  await expect(page.getByText("main.py")).toBeVisible();
});
