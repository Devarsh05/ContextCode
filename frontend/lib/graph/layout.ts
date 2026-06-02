/**
 * Dagre layout for the visible dependency graph. Imports React Flow *types*
 * only (no JSX/components), so it stays out of the React render path and the
 * selector tests stay React-free. Components consume the {nodes, edges} it
 * returns.
 *
 * Direction is left-to-right (rankdir "LR"): an edge A → B means "A imports B",
 * so dependencies flow rightward into the high-fan-in danger zones.
 */
import dagre from "dagre";
import { MarkerType, Position, type Edge, type Node } from "reactflow";

import type { GraphNodeResponse } from "@/lib/api/types";
import { centralityTier, type VisibleGraph } from "@/lib/graph/select";
import { TIERS } from "@/lib/graph/tiers";

/** Payload carried on each React Flow node, read by the custom DepNode. */
export interface DepNodeData {
  node: GraphNodeResponse;
  tier: ReturnType<typeof centralityTier>;
}

export type DepFlowNode = Node<DepNodeData, "dep">;

const RANK_SEP = 120;
const NODE_SEP = 28;

export function layoutGraph(visible: VisibleGraph): {
  nodes: DepFlowNode[];
  edges: Edge[];
} {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", ranksep: RANK_SEP, nodesep: NODE_SEP });
  g.setDefaultEdgeLabel(() => ({}));

  const tierOf = new Map(
    visible.nodes.map((node) => [
      node.file_path,
      centralityTier(node.imported_by_count, visible.maxImportedBy),
    ]),
  );

  for (const node of visible.nodes) {
    const style = TIERS[tierOf.get(node.file_path) ?? 0];
    g.setNode(node.file_path, { width: style.width, height: style.height });
  }
  for (const edge of visible.edges) {
    // target_file is guaranteed non-null for kept edges.
    g.setEdge(edge.source_file, edge.target_file as string);
  }

  dagre.layout(g);

  const nodes: DepFlowNode[] = visible.nodes.map((node) => {
    const tier = tierOf.get(node.file_path) ?? 0;
    const style = TIERS[tier];
    const pos = g.node(node.file_path);
    return {
      id: node.file_path,
      type: "dep",
      data: { node, tier },
      // dagre gives the centre; React Flow positions from the top-left.
      position: { x: pos.x - style.width / 2, y: pos.y - style.height / 2 },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  const edges: Edge[] = visible.edges.map((edge, i) => ({
    id: `${edge.source_file}->${edge.target_file}#${i}`,
    source: edge.source_file,
    target: edge.target_file as string,
    style: { stroke: "hsl(220 16% 38%)", strokeWidth: 1.5, opacity: 0.6 },
    markerEnd: { type: MarkerType.ArrowClosed, color: "hsl(220 16% 38%)" },
  }));

  return { nodes, edges };
}
