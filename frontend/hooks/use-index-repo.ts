"use client";

import { useMutation } from "@tanstack/react-query";

import { indexRepo } from "@/lib/api/repos";
import type { IndexResponse } from "@/lib/api/types";

interface IndexRepoVariables {
  url: string;
  forceReindex?: boolean;
}

/** Mutation to queue indexing of a public GitHub repo. */
export function useIndexRepo() {
  return useMutation<IndexResponse, Error, IndexRepoVariables>({
    mutationFn: ({ url, forceReindex = false }) => indexRepo(url, forceReindex),
  });
}
