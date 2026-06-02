"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

import type { CitationResponse } from "@/lib/api/types";
import { formatCitationRange } from "@/lib/citations";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

/**
 * Compact, expandable citation. Collapsed: shows `file_path:start-end`, the
 * function name, and a chunk-type badge. Clicking reveals the code snippet.
 */
export function CitationCard({ citation }: { citation: CitationResponse }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-md border border-border bg-background/40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left transition-colors hover:bg-accent/50"
      >
        <ChevronDown
          className={cn(
            "size-3.5 shrink-0 text-muted-foreground transition-transform",
            open && "rotate-180",
          )}
        />
        <span className="truncate font-mono text-xs text-foreground">
          {formatCitationRange(citation)}
        </span>
        {citation.function_name && (
          <span className="truncate font-mono text-xs text-muted-foreground">
            {citation.function_name}
          </span>
        )}
        <Badge
          variant="secondary"
          className="ml-auto shrink-0 text-[10px] font-medium uppercase tracking-wide"
        >
          {citation.chunk_type}
        </Badge>
      </button>

      {open && (
        <pre className="max-h-72 overflow-auto border-t border-border bg-card px-3 py-2 font-mono text-xs leading-relaxed text-muted-foreground">
          <code>{citation.snippet}</code>
        </pre>
      )}
    </div>
  );
}
