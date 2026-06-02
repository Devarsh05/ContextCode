"use client";

import Link from "next/link";
import { AlertTriangle, Loader2, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface IndexingErrorProps {
  message: string;
  /** Whether a force re-index can be triggered (requires the repo URL). */
  canRetry: boolean;
  isRetrying: boolean;
  onRetry: () => void;
}

/** Failure state for indexing: shows the error and a force-reindex Retry. */
export function IndexingError({
  message,
  canRetry,
  isRetrying,
  onRetry,
}: IndexingErrorProps) {
  return (
    <div className="container animate-fade-in px-6 py-16 sm:py-24">
      <Card className="mx-auto max-w-xl border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-destructive">
            <AlertTriangle className="size-4" />
            Indexing failed
          </CardTitle>
          <CardDescription>{message}</CardDescription>
        </CardHeader>

        <CardContent className="flex flex-wrap gap-3">
          {canRetry && (
            <Button onClick={onRetry} disabled={isRetrying} className="gap-2">
              {isRetrying ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RotateCw className="size-4" />
              )}
              {isRetrying ? "Retrying…" : "Retry indexing"}
            </Button>
          )}
          <Button variant="outline" asChild>
            <Link href="/">Start over</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
