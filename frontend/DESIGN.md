# ContextCode — Design System

**Direction: "Indigo Slate".** Dark-mode-first, confident, minimal — a
developer-tool aesthetic (Linear / Vercel polish). A single electric-indigo
accent on a refined near-black slate base. No gradients, no generic-AI purple
wash.

## Canonical source of tokens

All design tokens live as HSL CSS variables in **`app/globals.css`** — that is
the single source of truth. `tailwind.config.ts` only *references* them via
`hsl(var(--token))` and never hardcodes colors. Do not duplicate live values
elsewhere; the hex column below is design intent only.

Dark (`.dark`) is the canonical theme; a light `:root` exists so `next-themes`
can toggle.

## Color tokens (dark / canonical)

| Token | Hex | Role |
|-------|-----|------|
| `--background` | `#0B0D11` | app base (refined slate-black) |
| `--foreground` | `#F2F4F8` | primary text (off-white) |
| `--card` | `#111318` | raised surfaces |
| `--popover` | `#15181E` | menus, tooltips |
| `--primary` | `#6366F1` | electric indigo — CTAs, active, links, focus |
| `--primary-foreground` | `#FFFFFF` | text on indigo |
| `--secondary` | `#1A1D24` | secondary buttons / chips |
| `--muted` | `#15181E` | muted surfaces |
| `--muted-foreground` | `#8A93A3` | secondary text (≥4.5:1 on base) |
| `--accent` | `#1F232B` | hover / selected surface |
| `--border` | `#1F232B` | hairline borders |
| `--input` | `#232831` | input borders |
| `--ring` | `#6366F1` | focus ring (indigo) |
| `--destructive` | `#F87171` | errors / destructive |
| `--success` | `#34D399` | emerald — "indexed / completed" status |
| `--warning` | `#FBBF24` | amber — warnings / graph danger zones |

`success` and `warning` are extra semantic tokens beyond shadcn's defaults,
exposed in Tailwind as `bg-success` / `text-warning` etc. for status badges and
the dependency-graph view.

## Typography

- **Geist Sans** (UI) and **Geist Mono** (code, file paths, citations), loaded
  via `next/font/local` in `app/layout.tsx` and exposed as `font-sans` /
  `font-mono`. Geist is Vercel's own typeface — chosen for the developer-tool
  feel over the tooling's Inter suggestion.
- **Scale:** 12 / 14 / 16 (base) / 18 / 20 / 24 / 30 / 36 / 48.
- **Weights:** headings 600 (semibold), body 400, labels 500.
- **Line-height:** body ~1.5–1.6, headings ~1.1–1.25.

## Spacing & radius

- **Spacing:** 4px base grid (Tailwind default).
- **Radius:** `--radius: 0.625rem` (10px); shadcn derives `lg = radius`,
  `md = radius − 2px`, `sm = radius − 4px`.

## Components

shadcn/ui (`new-york` style, CSS variables) in `components/ui/`. They consume
the tokens above automatically — restyle via tokens, not per-component hex.
