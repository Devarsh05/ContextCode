"use client";

import { useQuery } from "@tanstack/react-query";

import { listDemoRepos } from "@/lib/api/demo";

/** Query the curated demo repositories shown as the landing-page entry point. */
export function useDemoRepos() {
  return useQuery({
    queryKey: ["demo-repos"],
    queryFn: listDemoRepos,
  });
}
