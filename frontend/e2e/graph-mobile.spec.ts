import { test, expect, type Page } from "@playwright/test";

/**
 * Mobile QA regression for the dependency-graph tab. Reproduces the 375px viewport
 * where the canvas was reported as a sized-but-empty box, and verifies:
 *   1. nodes are visible on the graph tab at 375px, and
 *   2. after a resize across the mobile↔desktop breakpoint the graph refits
 *      (the ResizeObserver → fitView path) and nodes remain visible.
 *
 * Backend is fully mocked via page.route, mirroring happy-path.spec.ts.
 */

const REPO_ID = "test-repo-123";

const repoResponse = {
  repo_id: REPO_ID,
  url: "https://github.com/acme/widget",
  name: "acme/widget",
  status: "indexing",
  file_count: 42,
};

const sseBody =
  `data: {"status":"indexing","progress_pct":40,"current_stage":"Parsing code"}\n\n` +
  `data: {"status":"completed","progress_pct":100}\n\n`;

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
  await page.route("**/repos/*", async (route) => {
    if (route.request().method() !== "GET") {
      await route.fallback();
      return;
    }
    await route.fulfill({ json: repoResponse });
  });

  await page.route("**/repos/*/status", async (route) => {
    await route.fulfill({ contentType: "text/event-stream", body: sseBody });
  });

  await page.route(/\/repos\/[^/]+\/graph/, async (route) => {
    await route.fulfill({ json: graphResponse });
  });
}

test("graph renders and refits at 375px and across a resize", async ({ page }) => {
  await mockBackend(page);
  await page.setViewportSize({ width: 375, height: 667 });

  await page.goto(`/repo/${REPO_ID}`);

  // SSE completes → workspace → open the Graph tab.
  await expect(page.getByRole("heading", { name: "Workspace" })).toBeVisible();
  await page.getByRole("tab", { name: "Graph" }).click();

  // A custom dep node is visible (not a zero-height/empty canvas).
  const node = page.getByText("main.py");
  await expect(node).toBeVisible();

  // The canvas pane must have real height — the reported bug was a zero-height
  // `.react-flow` (its `height: 100%` resolving against a flex-collapsed parent),
  // so the node sat outside a 0px box even though it was technically in the DOM.
  // `toBeVisible()` alone does NOT catch this (overflow-clipped nodes still pass),
  // so assert the node's box is inside the pane's box.
  const assertNodeInsideCanvas = async () => {
    const pane = page.locator(".react-flow").first();
    const paneBox = await pane.boundingBox();
    const nodeBox = await node.boundingBox();
    expect(paneBox, "react-flow pane should have a box").not.toBeNull();
    expect(nodeBox, "node should have a box").not.toBeNull();
    expect(paneBox!.height, "pane must not collapse to 0px").toBeGreaterThan(200);
    // Node center sits within the pane's visible rect.
    const cx = nodeBox!.x + nodeBox!.width / 2;
    const cy = nodeBox!.y + nodeBox!.height / 2;
    expect(cx).toBeGreaterThanOrEqual(paneBox!.x);
    expect(cx).toBeLessThanOrEqual(paneBox!.x + paneBox!.width);
    expect(cy).toBeGreaterThanOrEqual(paneBox!.y);
    expect(cy).toBeLessThanOrEqual(paneBox!.y + paneBox!.height);
  };

  await assertNodeInsideCanvas();

  // Cross to desktop and back to mobile — exercises the ResizeObserver → fitView
  // refit. Nodes must remain framed inside the (now differently sized) canvas.
  await page.setViewportSize({ width: 1280, height: 800 });
  await expect(node).toBeVisible();
  await page.setViewportSize({ width: 375, height: 667 });
  await assertNodeInsideCanvas();
});
