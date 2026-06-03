import {
  Card,
  CardContent,
  CardHeader,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { STAGES } from "@/lib/indexing-stages";

/**
 * Loading placeholder shown while the repo metadata loads and before the first
 * SSE frame arrives. Mirrors the layout of {@link IndexingProgress} (title +
 * description, progress bar, and one row per pipeline stage) so the transition
 * to the live view causes no layout shift.
 */
export function IndexingProgressSkeleton() {
  return (
    <div className="container animate-fade-in px-6 py-16 sm:py-24">
      <Card className="mx-auto max-w-xl">
        <CardHeader>
          <Skeleton className="h-5 w-44" />
          <Skeleton className="mt-2 h-4 w-32" />
        </CardHeader>

        <CardContent className="space-y-8">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-3 w-8" />
            </div>
            <Skeleton className="h-2 w-full rounded-full" />
          </div>

          <ol className="space-y-1">
            {STAGES.map((stage) => (
              <li key={stage.key} className="flex items-center gap-3 py-1.5">
                <Skeleton className="size-5 rounded-full" />
                <Skeleton className="h-4 w-40" />
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
