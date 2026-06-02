"use client";

import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

interface GraphControlsProps {
  n: number;
  /** Total nodes available (caps the slider). */
  total: number;
  visibleCount: number;
  hideIsolated: boolean;
  onNChange: (n: number) => void;
  onHideIsolatedChange: (hideIsolated: boolean) => void;
}

const MIN_N = 10;
const MAX_N = 200;
const STEP = 10;

/** Top-N slider + resolved-only switch for the graph canvas. */
export function GraphControls({
  n,
  total,
  visibleCount,
  hideIsolated,
  onNChange,
  onHideIsolatedChange,
}: GraphControlsProps) {
  const max = Math.max(MIN_N, Math.min(MAX_N, total));

  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-4">
      <div className="flex min-w-[260px] flex-1 flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <label htmlFor="graph-topn" className="font-medium">
            Most-central files
          </label>
          <span className="text-muted-foreground">
            Showing top {visibleCount} of {total}
          </span>
        </div>
        <Slider
          id="graph-topn"
          aria-label="Number of files to show"
          min={MIN_N}
          max={max}
          step={STEP}
          value={[Math.min(n, max)]}
          onValueChange={([value]) => onNChange(value)}
        />
      </div>

      <label className="flex cursor-pointer items-center gap-2 text-xs">
        <Switch
          checked={hideIsolated}
          onCheckedChange={onHideIsolatedChange}
          aria-label="Hide isolated files"
        />
        <span className="font-medium">Hide isolated files</span>
      </label>
    </div>
  );
}
