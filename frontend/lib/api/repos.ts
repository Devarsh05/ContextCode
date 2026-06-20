import { getStoredAccessCode } from "@/lib/access-code";
import { apiFetch } from "@/lib/api/client";
import type {
  IndexRequest,
  IndexResponse,
  RepoResponse,
} from "@/lib/api/types";

/** X-Access-Code header for the cost-gated write endpoints, when a code is set. */
function accessCodeHeader(): Record<string, string> {
  const code = getStoredAccessCode();
  return code ? { "X-Access-Code": code } : {};
}

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
    headers: accessCodeHeader(),
  });
}

/** Fetch a repo's metadata (url, name, status, file_count) by id. */
export function getRepo(repoId: string): Promise<RepoResponse> {
  return apiFetch<RepoResponse>(`/repos/${repoId}`);
}
