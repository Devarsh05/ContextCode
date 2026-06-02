/**
 * Pure graph-shaping logic for the dependency-graph tab. No React / React Flow
 * imports live here so this module stays trivially unit-testable.
 *
 * The backend returns every file node and import edge for a repo. For
 * legibility and render performance we show only the top-N most-imported
 * ("most central") nodes, and keep only edges whose endpoints are both
 * visible. Centrality drives both colour and size so the highest-fan-in files
 * — the "danger zones" — read as the visual focal point.
 */
import type {
  GraphEdgeResponse,
  GraphNodeResponse,
} from "@/lib/api/types";

/** 0 = peripheral … 4 = critical danger zone. */
export type CentralityTier = 0 | 1 | 2 | 3 | 4;

export interface VisibleGraph {
  nodes: GraphNodeResponse[];
  edges: GraphEdgeResponse[];
  /** Highest `imported_by_count` among the visible nodes; drives tiering. */
  maxImportedBy: number;
}

/**
 * Bucket a fan-in count onto a 5-step danger scale, relative to the most-
 * imported node in the visible set. Relative bucketing guarantees the top
 * file(s) always land in tier 4 regardless of repo scale, so the focal point
 * holds on both tiny and huge graphs.
 */
export function centralityTier(count: number, maxCount: number): CentralityTier {
  if (count <= 0 || maxCount <= 0) return 0;
  const ratio = count / maxCount;
  if (ratio <= 0.25) return 1;
  if (ratio <= 0.5) return 2;
  if (ratio <= 0.75) return 3;
  return 4;
}

/** Most-central first; `file_path` tie-break keeps selection deterministic. */
function byCentrality(a: GraphNodeResponse, b: GraphNodeResponse): number {
  if (b.imported_by_count !== a.imported_by_count) {
    return b.imported_by_count - a.imported_by_count;
  }
  return a.file_path.localeCompare(b.file_path);
}

/**
 * Select the top-N most-central nodes and the edges that connect them.
 *
 * Edges survive only when BOTH endpoints are visible — which also drops
 * unresolved/third-party edges, since their `target_file` is null and null is
 * never a member of the visible set.
 */
export function selectVisibleGraph(
  nodes: GraphNodeResponse[],
  edges: GraphEdgeResponse[],
  n: number,
): VisibleGraph {
  const limit = Math.max(0, Math.floor(n));
  const visible = [...nodes].sort(byCentrality).slice(0, limit);

  const visiblePaths = new Set(visible.map((node) => node.file_path));
  const keptEdges = edges.filter(
    (edge) =>
      edge.target_file !== null &&
      visiblePaths.has(edge.source_file) &&
      visiblePaths.has(edge.target_file),
  );

  const maxImportedBy = visible.reduce(
    (max, node) => Math.max(max, node.imported_by_count),
    0,
  );

  return { nodes: visible, edges: keptEdges, maxImportedBy };
}

export interface NodeEdges {
  /** Edges where this file is the importer. */
  outgoing: GraphEdgeResponse[];
  /** Edges where this file is the imported target. */
  incoming: GraphEdgeResponse[];
}

/**
 * Partition the full edge list into this file's imports and importers. Run
 * over ALL edges (not the visible subset) so the detail panel shows real
 * dependencies even when a neighbour falls outside the top-N cap.
 */
export function nodeEdges(
  filePath: string,
  allEdges: GraphEdgeResponse[],
): NodeEdges {
  const outgoing: GraphEdgeResponse[] = [];
  const incoming: GraphEdgeResponse[] = [];
  for (const edge of allEdges) {
    if (edge.source_file === filePath) outgoing.push(edge);
    if (edge.target_file === filePath) incoming.push(edge);
  }
  return { outgoing, incoming };
}
