import { apiFetch } from "@/lib/api/client";
import type { IndexRequest, IndexResponse } from "@/lib/api/types";

/**
 * Queue indexing for a public GitHub repo. Returns immediately with the repo
 * and job ids; progress is streamed via the SSE status endpoint.
 */
export function indexRepo(
  url: string,
  forceReindex = false,
): Promise<IndexResponse> {
  const body: IndexRequest = { repo_url: url, force_reindex: forceReindex };
  return apiFetch<IndexResponse>("/repos/index", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
