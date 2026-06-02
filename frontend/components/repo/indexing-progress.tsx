"use client";

import { useRef } from "react";
import { Check, Loader2 } from "lucide-react";

import type { IndexingStatus } from "@/hooks/use-indexing-status";
import {
  STAGES,
  STAGE_DONE,
  STAGE_NONE,
  resolveStageIndex,
} from "@/lib/indexing-stages";
import { cn } from "@/lib/utils";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

/**
 * Animated indexing experience: a progress bar driven by progressPct plus a
 * stepper over the backend pipeline stages, with the active stage spinning.
 */
export function IndexingProgress({ status }: { status: IndexingStatus }) {
  // Hold the last known stage so a transient null/unknown stage doesn't snap
  // the stepper backwards. Monotonic, so safe to derive during render.
  const lastIndexRef = useRef(STAGE_NONE);
  const activeIndex = resolveStageIndex(
    status.status,
    status.message,
    lastIndexRef.current,
  );
  lastIndexRef.current = activeIndex;

  const isIndeterminate =
    status.progressPct == null && status.status !== "completed";
  const pct = status.progressPct ?? 0;

  const currentLabel =
    status.status == null
      ? "Connecting…"
      : activeIndex === STAGE_NONE
        ? "Queued — waiting for a worker…"
        : activeIndex >= STAGE_DONE
          ? "Finishing up…"
          : STAGES[activeIndex].label;

  return (
    <div className="container animate-fade-in px-6 py-16 sm:py-24">
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Loader2 className="size-4 animate-spin text-primary" />
            Indexing repository
          </CardTitle>
          <CardDescription>{currentLabel}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-8">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Progress</span>
              <span className="font-mono tabular-nums">
                {isIndeterminate ? "—" : `${pct}%`}
              </span>
            </div>
            {isIndeterminate ? (
              <div className="relative h-2 w-full overflow-hidden rounded-full bg-primary/20">
                <div className="absolute inset-y-0 w-1/4 animate-indeterminate rounded-full bg-primary" />
              </div>
            ) : (
              <Progress value={pct} />
            )}
          </div>

          <ol className="space-y-1">
            {STAGES.map((stage, index) => {
              const state =
                activeIndex >= STAGE_DONE || index < activeIndex
                  ? "done"
                  : index === activeIndex
                    ? "active"
                    : "pending";

              return (
                <li
                  key={stage.key}
                  className="flex items-center gap-3 py-1.5"
                >
                  <span className="flex size-5 items-center justify-center">
                    {state === "done" ? (
                      <Check className="size-4 text-success" />
                    ) : state === "active" ? (
                      <Loader2 className="size-4 animate-spin text-primary" />
                    ) : (
                      <span className="size-2 rounded-full bg-muted-foreground/30" />
                    )}
                  </span>
                  <span
                    className={cn(
                      "text-sm",
                      state === "active" && "font-medium text-foreground",
                      state === "done" && "text-foreground",
                      state === "pending" && "text-muted-foreground",
                    )}
                  >
                    {stage.label}
                  </span>
                </li>
              );
            })}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
