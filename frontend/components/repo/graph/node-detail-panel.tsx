"use client";

import { ArrowDownLeft, ArrowUpRight, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { nodeEdges } from "@/lib/graph/select";
import type {
  GraphEdgeResponse,
  GraphNodeResponse,
} from "@/lib/api/types";

interface NodeDetailPanelProps {
  node: GraphNodeResponse;
  allEdges: GraphEdgeResponse[];
  onClose: () => void;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-sm font-medium tabular-nums">{value}</span>
    </div>
  );
}

function EdgeList({
  title,
  icon: Icon,
  rows,
  empty,
}: {
  title: string;
  icon: typeof ArrowUpRight;
  rows: React.ReactNode[];
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-1.5 text-xs font-medium">
        <Icon className="size-3.5 text-muted-foreground" />
        {title}
        <span className="text-muted-foreground">({rows.length})</span>
      </div>
      {rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">{empty}</p>
      ) : (
        <ul className="flex flex-col gap-1.5">{rows}</ul>
      )}
    </div>
  );
}

/**
 * Side panel for a selected node. Shows the file's metadata and its real
 * imports/importers — computed over the FULL edge set so dependencies aren't
 * hidden by the top-N cap on the canvas.
 */
export function NodeDetailPanel({
  node,
  allEdges,
  onClose,
}: NodeDetailPanelProps) {
  const { outgoing, incoming } = nodeEdges(node.file_path, allEdges);

  return (
    <aside className="flex h-full w-full flex-col rounded-lg border border-border bg-card">
      <div className="flex items-start justify-between gap-2 border-b border-border p-4">
        <div className="min-w-0">
          <p className="break-all font-mono text-sm font-medium">
            {node.file_path}
          </p>
          <Badge variant="secondary" className="mt-1.5 text-[11px]">
            {node.language}
          </Badge>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="size-7 shrink-0"
          onClick={onClose}
          aria-label="Close details"
        >
          <X className="size-4" />
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 border-b border-border p-4">
        <Stat label="Imports" value={node.import_count} />
        <Stat label="Imported by" value={node.imported_by_count} />
      </div>

      <ScrollArea className="flex-1">
        <div className="flex flex-col gap-5 p-4">
          <EdgeList
            title="Imports"
            icon={ArrowUpRight}
            empty="This file imports nothing in the repo."
            rows={outgoing.map((edge, i) => (
              <li key={i} className="flex flex-col gap-0.5 text-xs">
                <span className="font-mono text-muted-foreground">
                  {edge.import_raw}
                </span>
                <span className="break-all font-mono">
                  {edge.target_file ?? "(unresolved / external)"}
                </span>
              </li>
            ))}
          />
          <EdgeList
            title="Imported by"
            icon={ArrowDownLeft}
            empty="No file in the repo imports this."
            rows={incoming.map((edge, i) => (
              <li key={i} className="break-all font-mono text-xs">
                {edge.source_file}
              </li>
            ))}
          />
        </div>
      </ScrollArea>
    </aside>
  );
}
