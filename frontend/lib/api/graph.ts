import { apiFetch } from "@/lib/api/client";
import type { GraphResponse } from "@/lib/api/types";

/** Fetch the dependency graph for a repo. */
export function getGraph(
  repoId: string,
  resolvedOnly = false,
): Promise<GraphResponse> {
  const query = new URLSearchParams({ resolved_only: String(resolvedOnly) });
  return apiFetch<GraphResponse>(`/repos/${repoId}/graph?${query}`);
}
