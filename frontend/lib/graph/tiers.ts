/**
 * Danger-zone colour + size scale for graph nodes.
 *
 * A sequential cool→hot ramp anchored to the app's semantic tokens
 * (see app/globals.css): peripheral files sit in a dim, desaturated slate that
 * recedes against the near-black background; centrality climbs through indigo
 * (the brand accent) into amber (warning) and finally red (destructive) for the
 * top "danger zone" files, which also grow largest and gain a glow ring. Colour
 * is never the sole signal — size, the legend, and the detail panel reinforce
 * it (network graphs are inherently low-accessibility, so redundancy matters).
 *
 * Node fill is a low-alpha tint of the accent laid over the card surface, which
 * keeps the foreground label text comfortably above 4.5:1 contrast in dark mode.
 */
import type { CentralityTier } from "@/lib/graph/select";

export interface TierStyle {
  tier: CentralityTier;
  label: string;
  /** Saturated accent — borders, swatches, the danger glow. */
  accent: string;
  /** Translucent tint used as the node fill over the card surface. */
  fill: string;
  /** Label colour with enough contrast on the tinted fill. */
  text: string;
  /** Laid-out node box size (px); larger = more central. */
  width: number;
  height: number;
  /** Optional box-shadow that makes the top tier "pop". */
  glow?: string;
}

export const TIERS: Record<CentralityTier, TierStyle> = {
  0: {
    tier: 0,
    label: "Peripheral",
    accent: "hsl(220 14% 45%)",
    fill: "hsl(223 17% 8%)",
    text: "hsl(218 12% 72%)",
    width: 150,
    height: 48,
  },
  1: {
    tier: 1,
    label: "Low",
    accent: "hsl(239 50% 62%)",
    fill: "hsl(239 50% 62% / 0.12)",
    text: "hsl(220 30% 96%)",
    width: 168,
    height: 52,
  },
  2: {
    tier: 2,
    label: "Moderate",
    accent: "hsl(239 84% 67%)",
    fill: "hsl(239 84% 67% / 0.16)",
    text: "hsl(220 30% 96%)",
    width: 188,
    height: 58,
  },
  3: {
    tier: 3,
    label: "High",
    accent: "hsl(43 96% 56%)",
    fill: "hsl(43 96% 56% / 0.16)",
    text: "hsl(220 30% 96%)",
    width: 212,
    height: 64,
  },
  4: {
    tier: 4,
    label: "Critical",
    accent: "hsl(0 91% 71%)",
    fill: "hsl(0 91% 71% / 0.2)",
    text: "hsl(220 30% 98%)",
    width: 240,
    height: 72,
    glow: "0 0 0 1px hsl(0 91% 71% / 0.6), 0 0 24px hsl(0 91% 71% / 0.35)",
  },
};

/** Ordered low→high for the legend. */
export const TIER_ORDER: CentralityTier[] = [0, 1, 2, 3, 4];
