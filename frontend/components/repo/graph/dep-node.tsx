"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";

import { TIERS } from "@/lib/graph/tiers";
import type { DepNodeData } from "@/lib/graph/layout";

/** Last path segment — the bit a reader actually scans for. */
function basename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

/**
 * A single file node. Colour, size, and glow come from the centrality tier so
 * the most-imported files visibly dominate. The full path is exposed via the
 * native title tooltip; the visible label is just the basename.
 */
function DepNodeImpl({ data, selected }: NodeProps<DepNodeData>) {
  const { node, tier } = data;
  const style = TIERS[tier];

  return (
    <div
      title={node.file_path}
      style={{
        width: style.width,
        minHeight: style.height,
        background: style.fill,
        borderColor: style.accent,
        color: style.text,
        boxShadow: selected
          ? `0 0 0 2px ${style.accent}`
          : style.glow,
      }}
      className="flex flex-col justify-center gap-0.5 rounded-lg border px-3 py-2 transition-shadow"
    >
      <Handle type="target" position={Position.Left} className="!bg-border" />
      <span
        className="truncate font-mono text-[13px] font-medium leading-tight"
        style={{ color: style.text }}
      >
        {basename(node.file_path)}
      </span>
      <div className="flex items-center gap-2 text-[11px]" style={{ color: style.accent }}>
        <span className="uppercase tracking-wide">{node.language}</span>
        <span aria-hidden>·</span>
        <span>{node.imported_by_count} imported by</span>
      </div>
      <Handle type="source" position={Position.Right} className="!bg-border" />
    </div>
  );
}

export const DepNode = memo(DepNodeImpl);
