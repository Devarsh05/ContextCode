"use client";

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useIndexRepo } from "@/hooks/use-index-repo";
import { useIndexingStatus } from "@/hooks/use-indexing-status";
import { useRepo } from "@/hooks/use-repo";
import { IndexingError } from "@/components/repo/indexing-error";
import { IndexingProgress } from "@/components/repo/indexing-progress";
import { IndexingProgressSkeleton } from "@/components/repo/indexing-progress-skeleton";
import { Workspace } from "@/components/repo/workspace";

/**
 * Gate for the /repo/[id] route. Streams indexing status and renders the right
 * surface: a loader on first load, the animated progress experience while
 * indexing, an error+retry on failure, or the workspace once completed.
 *
 * A retry remounts the inner view (via `key`) so the SSE connection reopens.
 */
export function RepoView({ repoId }: { repoId: string }) {
  const [retryNonce, setRetryNonce] = useState(0);

  return (
    <RepoViewInner
      key={retryNonce}
      repoId={repoId}
      onRetried={() => setRetryNonce((n) => n + 1)}
    />
  );
}

function RepoViewInner({
  repoId,
  onRetried,
}: {
  repoId: string;
  onRetried: () => void;
}) {
  const repo = useRepo(repoId);
  const status = useIndexingStatus(repoId);
  const queryClient = useQueryClient();
  const indexRepo = useIndexRepo();

  // Live SSE status wins; fall back to the once-fetched repo status.
  const effectiveStatus = status.status ?? repo.data?.status ?? null;
  const completed = effectiveStatus === "completed";
  const repoNotFound = repo.isError;
  const failed =
    status.error != null || effectiveStatus === "failed" || repoNotFound;

  // The brief window before the repo metadata loads and the first SSE frame.
  const isInitialLoading =
    repo.isLoading && status.status == null && status.error == null;

  function handleRetry() {
    const url = repo.data?.url;
    if (!url) return;
    indexRepo.mutate(
      { url, forceReindex: true },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: ["repo", repoId] });
          onRetried();
        },
        onError: (error) =>
          toast.error("Couldn't restart indexing", {
            description: error.message,
          }),
      },
    );
  }

  if (completed) {
    return <Workspace repoId={repoId} />;
  }

  if (failed) {
    const message = repoNotFound
      ? "We couldn't find this repository. It may have been removed."
      : (status.error ?? "Indexing failed for this repository.");
    return (
      <IndexingError
        title={repoNotFound ? "Repository not found" : "Indexing failed"}
        message={message}
        canRetry={Boolean(repo.data?.url) && !repoNotFound}
        isRetrying={indexRepo.isPending}
        onRetry={handleRetry}
      />
    );
  }

  if (isInitialLoading) {
    return <IndexingProgressSkeleton />;
  }

  return <IndexingProgress status={status} />;
}
