"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="container flex flex-col items-center px-6 py-32 text-center">
      <p className="font-mono text-sm text-destructive">Something went wrong</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-tight">
        Unexpected error
      </h1>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">
        An error occurred while rendering this page. You can try again.
      </p>
      <Button onClick={reset} className="mt-6">
        Try again
      </Button>
    </div>
  );
}
