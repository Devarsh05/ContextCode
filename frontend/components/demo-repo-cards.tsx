"use client";

import { useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, GitBranch, Loader2 } from "lucide-react";

import { useDemoRepos } from "@/hooks/use-demo-repos";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { DemoRepoResponse } from "@/lib/api/types";

/** Best-effort `owner/repo` slug from a GitHub URL, for a compact subtitle. */
function repoSlug(url: string): string {
  try {
    const segments = new URL(url).pathname.split("/").filter(Boolean);
    if (segments.length >= 2) {
      return `${segments[0]}/${segments[1]}`.replace(/\.git$/, "");
    }
    return segments.join("/");
  } catch {
    return url;
  }
}

function DemoCard({ repo }: { repo: DemoRepoResponse }) {
  const router = useRouter();
  const slug = repoSlug(repo.url);

  return (
    <button
      type="button"
      onClick={() => router.push(`/repo/${repo.id}`)}
      className="group flex flex-col rounded-lg border border-border bg-card p-5 text-left transition-colors hover:border-primary/50 hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
    >
      <div className="flex items-center gap-2.5">
        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-secondary text-primary">
          <GitBranch className="size-4" />
        </span>
        <span className="truncate text-sm font-semibold text-foreground">
          {repo.name}
        </span>
      </div>
      <p className="mt-3 truncate font-mono text-xs text-muted-foreground">
        {slug}
      </p>
      <div className="mt-4 flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {repo.file_count != null
            ? `${repo.file_count.toLocaleString()} files`
            : "Demo repo"}
        </span>
        <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
      </div>
    </button>
  );
}

function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid w-full gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {children}
    </div>
  );
}

/**
 * Primary landing entry point: the curated demo repos as selectable cards.
 * Renders loading skeletons, a friendly empty state, and a retryable error
 * state — all on the shared Indigo Slate tokens.
 */
export function DemoRepoCards() {
  const { data, isLoading, isError, refetch, isFetching } = useDemoRepos();

  return (
    <section className="mt-12 w-full max-w-4xl text-left">
      <div className="mb-4 text-center">
        <h2 className="text-lg font-semibold tracking-tight">
          Try it on a demo repo
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Pick a pre-indexed repository and start chatting instantly — no setup.
        </p>
      </div>

      {isLoading ? (
        <CardGrid>
          {[0, 1, 2].map((i) => (
            <div
              key={i}
              className="flex flex-col rounded-lg border border-border bg-card p-5"
            >
              <div className="flex items-center gap-2.5">
                <Skeleton className="size-8 rounded-md" />
                <Skeleton className="h-4 w-32" />
              </div>
              <Skeleton className="mt-3 h-3 w-40" />
              <Skeleton className="mt-4 h-3 w-20" />
            </div>
          ))}
        </CardGrid>
      ) : isError ? (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card px-6 py-10 text-center">
          <AlertTriangle className="size-6 text-destructive" />
          <div>
            <p className="text-sm font-medium">Couldn&apos;t load demo repos</p>
            <p className="mt-1 text-sm text-muted-foreground">
              Something went wrong reaching the server.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="gap-1.5"
          >
            {isFetching ? (
              <Loader2 className="size-4 animate-spin" />
            ) : null}
            Try again
          </Button>
        </div>
      ) : !data || data.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center">
          <GitBranch className="size-6 text-muted-foreground" />
          <p className="text-sm font-medium">No demo repos yet</p>
          <p className="text-sm text-muted-foreground">
            Bring your own repository below to get started.
          </p>
        </div>
      ) : (
        <CardGrid>
          {data.map((repo) => (
            <DemoCard key={repo.id} repo={repo} />
          ))}
        </CardGrid>
      )}
    </section>
  );
}
