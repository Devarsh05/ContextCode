"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useIndexRepo } from "@/hooks/use-index-repo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/**
 * Returns true when `value` looks like a public GitHub repo URL
 * (github.com host with at least an owner/repo path). Tolerates a
 * missing protocol so users can paste "github.com/owner/repo".
 */
function isGithubRepoUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  try {
    const url = new URL(/^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`);
    const host = url.hostname.toLowerCase();
    if (host !== "github.com" && host !== "www.github.com") return false;
    const segments = url.pathname.split("/").filter(Boolean);
    return segments.length >= 2;
  } catch {
    return false;
  }
}

/**
 * GitHub-URL input + Analyze button. Validates the URL client-side, queues
 * indexing via the indexRepo mutation, then routes to the repo workspace.
 */
export function RepoUrlForm() {
  const router = useRouter();
  const { mutate, isPending } = useIndexRepo();
  const [url, setUrl] = useState("");

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isPending) return;

    const value = url.trim();
    if (!isGithubRepoUrl(value)) {
      toast.error("Enter a valid GitHub repository URL", {
        description: "Example: https://github.com/owner/repo",
      });
      return;
    }

    mutate(
      { url: value },
      {
        onSuccess: ({ repo_id }) => router.push(`/repo/${repo_id}`),
        onError: (error) =>
          toast.error("Couldn't start indexing", {
            description: error.message,
          }),
      },
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mt-8 flex w-full max-w-md flex-col gap-3 sm:flex-row"
    >
      <Input
        type="text"
        inputMode="url"
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        value={url}
        onChange={(event) => setUrl(event.target.value)}
        placeholder="https://github.com/owner/repo"
        aria-label="Public GitHub repository URL"
        className="h-11 font-mono text-sm"
        disabled={isPending}
      />
      <Button type="submit" size="lg" className="h-11 gap-2" disabled={isPending}>
        {isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" />
            Analyzing
          </>
        ) : (
          <>
            Analyze
            <ArrowRight className="size-4" />
          </>
        )}
      </Button>
    </form>
  );
}
