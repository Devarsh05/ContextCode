"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { useIndexRepo } from "@/hooks/use-index-repo";
import { useAccessCode } from "@/hooks/use-access-code";
import {
  AT_CAPACITY_MESSAGE,
  getStoredAccessCode,
  isAtCapacity,
  isUnauthorized,
} from "@/lib/access-code";
import { AccessCodeModal } from "@/components/access-code-modal";
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
  const { setCode, clearCode } = useAccessCode();
  const [url, setUrl] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const pendingUrlRef = useRef<string | null>(null);

  /** Fire the indexing mutation (the access code is read from storage by the
   *  API client). Routes on success; reprompts on 401, toasts on 429. */
  function runIndex(value: string) {
    mutate(
      { url: value },
      {
        onSuccess: ({ repo_id }) => router.push(`/repo/${repo_id}`),
        onError: (error) => {
          if (isUnauthorized(error)) {
            clearCode();
            setModalError("Invalid access code. Please try again.");
            setModalOpen(true);
            return;
          }
          if (isAtCapacity(error)) {
            toast.error(AT_CAPACITY_MESSAGE);
            return;
          }
          toast.error("Couldn't start indexing", {
            description: error.message,
          });
        },
      },
    );
  }

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

    if (!getStoredAccessCode()) {
      pendingUrlRef.current = value;
      setModalError(null);
      setModalOpen(true);
      return;
    }

    runIndex(value);
  }

  return (
    <>
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

      <AccessCodeModal
        open={modalOpen}
        error={modalError}
        onClose={() => setModalOpen(false)}
        onSubmit={(submitted) => {
          setCode(submitted);
          setModalOpen(false);
          const value = pendingUrlRef.current;
          pendingUrlRef.current = null;
          if (value) runIndex(value);
        }}
      />
    </>
  );
}
