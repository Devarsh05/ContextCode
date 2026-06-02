"use client";

import { TIERS, TIER_ORDER } from "@/lib/graph/tiers";

/**
 * Legend for the danger scale. Doubles as the accessibility fallback for the
 * colour encoding — the swatch labels spell out what each colour means, so the
 * scale never relies on colour perception alone.
 */
export function GraphLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
      <span className="font-medium text-foreground">Danger scale</span>
      {TIER_ORDER.map((tier) => {
        const style = TIERS[tier];
        return (
          <span key={tier} className="flex items-center gap-1.5">
            <span
              className="inline-block size-3 rounded-sm border"
              style={{ background: style.fill, borderColor: style.accent }}
              aria-hidden
            />
            {style.label}
          </span>
        );
      })}
      <span className="text-muted-foreground/70">(by files importing it)</span>
    </div>
  );
}
