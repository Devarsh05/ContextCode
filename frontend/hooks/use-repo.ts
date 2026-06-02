"use client";

import { useQuery } from "@tanstack/react-query";

import { getRepo } from "@/lib/api/repos";

/** Query a repo's metadata (url, name, status). Disabled until repoId is present. */
export function useRepo(repoId: string) {
  return useQuery({
    queryKey: ["repo", repoId],
    queryFn: () => getRepo(repoId),
    enabled: Boolean(repoId),
  });
}
