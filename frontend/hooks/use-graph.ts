"use client";

import { useQuery } from "@tanstack/react-query";

import { getGraph } from "@/lib/api/graph";

/** Query the dependency graph for a repo. Disabled until repoId is present. */
export function useGraph(repoId: string, resolvedOnly = false) {
  return useQuery({
    queryKey: ["graph", repoId, resolvedOnly],
    queryFn: () => getGraph(repoId, resolvedOnly),
    enabled: Boolean(repoId),
  });
}
