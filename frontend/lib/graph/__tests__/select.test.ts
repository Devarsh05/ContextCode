import { describe, expect, it } from "vitest";

import {
  centralityTier,
  nodeEdges,
  selectVisibleGraph,
} from "@/lib/graph/select";
import type {
  GraphEdgeResponse,
  GraphNodeResponse,
} from "@/lib/api/types";

function node(
  file_path: string,
  imported_by_count: number,
  import_count = 0,
): GraphNodeResponse {
  return { file_path, language: "python", import_count, imported_by_count };
}

function edge(
  source_file: string,
  target_file: string | null,
  import_raw = "import x",
): GraphEdgeResponse {
  return { source_file, target_file, import_raw };
}

describe("centralityTier", () => {
  it("returns tier 0 for zero fan-in", () => {
    expect(centralityTier(0, 10)).toBe(0);
  });

  it("guards against a non-positive max", () => {
    expect(centralityTier(5, 0)).toBe(0);
    expect(centralityTier(0, 0)).toBe(0);
  });

  it("buckets ratios onto the danger scale", () => {
    expect(centralityTier(2, 10)).toBe(1); // 0.2 → ≤0.25
    expect(centralityTier(5, 10)).toBe(2); // 0.5 → ≤0.5
    expect(centralityTier(7, 10)).toBe(3); // 0.7 → ≤0.75
    expect(centralityTier(8, 10)).toBe(4); // 0.8 → >0.75
  });

  it("puts the most-imported node in the top tier", () => {
    expect(centralityTier(10, 10)).toBe(4);
  });

  it("treats the 0.25 and 0.5 boundaries as inclusive lower tiers", () => {
    expect(centralityTier(25, 100)).toBe(1);
    expect(centralityTier(50, 100)).toBe(2);
    expect(centralityTier(75, 100)).toBe(3);
  });
});

describe("selectVisibleGraph", () => {
  const nodes = [
    node("a.py", 9),
    node("b.py", 5),
    node("c.py", 2),
    node("d.py", 0),
  ];

  it("keeps at most N nodes, most-central first", () => {
    const result = selectVisibleGraph(nodes, [], 2);
    expect(result.nodes.map((nd) => nd.file_path)).toEqual(["a.py", "b.py"]);
  });

  it("re-sorts regardless of input order", () => {
    const shuffled = [node("c.py", 2), node("a.py", 9), node("b.py", 5)];
    const result = selectVisibleGraph(shuffled, [], 1);
    expect(result.nodes[0].file_path).toBe("a.py");
  });

  it("breaks ties deterministically by file path", () => {
    const ties = [node("z.py", 3), node("a.py", 3), node("m.py", 3)];
    const result = selectVisibleGraph(ties, [], 2);
    expect(result.nodes.map((nd) => nd.file_path)).toEqual(["a.py", "m.py"]);
  });

  it("reports the max fan-in among the visible nodes only", () => {
    // Top-2 are a.py(9) and b.py(5); max should reflect the visible set.
    expect(selectVisibleGraph(nodes, [], 2).maxImportedBy).toBe(9);
  });

  it("keeps only edges with both endpoints visible", () => {
    const edges = [
      edge("b.py", "a.py"), // both visible
      edge("c.py", "a.py"), // c.py excluded by top-N
      edge("a.py", "d.py"), // d.py excluded by top-N
    ];
    const result = selectVisibleGraph(nodes, edges, 2);
    expect(result.edges).toEqual([edge("b.py", "a.py")]);
  });

  it("drops unresolved edges (null target)", () => {
    const edges = [edge("b.py", null, "import os"), edge("b.py", "a.py")];
    const result = selectVisibleGraph(nodes, edges, 2);
    expect(result.edges).toEqual([edge("b.py", "a.py")]);
  });

  it("keeps isolated nodes by default", () => {
    // No edges at all → every node is isolated, but the filter is off.
    const result = selectVisibleGraph(nodes, [], 4);
    expect(result.nodes).toHaveLength(4);
  });
});

describe("selectVisibleGraph — hideIsolated", () => {
  const nodes = [node("hub.py", 3), node("leaf.py", 0), node("lonely.py", 0)];
  const edges = [edge("leaf.py", "hub.py")];

  it("drops nodes no rendered edge touches", () => {
    const result = selectVisibleGraph(nodes, edges, 10, true);
    expect(result.nodes.map((nd) => nd.file_path).sort()).toEqual([
      "hub.py",
      "leaf.py",
    ]);
  });

  it("leaves the edge set unchanged (isolated nodes have no edges)", () => {
    const off = selectVisibleGraph(nodes, edges, 10, false);
    const on = selectVisibleGraph(nodes, edges, 10, true);
    expect(on.edges).toEqual(off.edges);
  });

  it("composes with top-N: a node whose only neighbour fell outside top-N reads as isolated", () => {
    // Top-2 by centrality = hub.py(3), leaf2.py(2). hub's only importer
    // leaf.py(0) is outside the top-2, so within the rendered edge set hub has
    // no edge — and so does leaf2 — leaving nothing once isolated nodes drop.
    const ns = [node("hub.py", 3), node("leaf2.py", 2), node("leaf.py", 0)];
    const es = [edge("leaf.py", "hub.py")];
    const result = selectVisibleGraph(ns, es, 2, true);
    expect(result.edges).toEqual([]);
    expect(result.nodes).toEqual([]);
  });

  it("reports max fan-in over the filtered visible set", () => {
    expect(selectVisibleGraph(nodes, edges, 10, true).maxImportedBy).toBe(3);
  });
});

describe("nodeEdges", () => {
  const edges = [
    edge("a.py", "b.py"),
    edge("a.py", "c.py"),
    edge("d.py", "a.py"),
    edge("e.py", "a.py"),
    edge("x.py", "y.py"),
  ];

  it("partitions imports (outgoing) and importers (incoming)", () => {
    const { outgoing, incoming } = nodeEdges("a.py", edges);
    expect(outgoing.map((e) => e.target_file)).toEqual(["b.py", "c.py"]);
    expect(incoming.map((e) => e.source_file)).toEqual(["d.py", "e.py"]);
  });

  it("returns empty lists for an isolated file", () => {
    expect(nodeEdges("lonely.py", edges)).toEqual({
      outgoing: [],
      incoming: [],
    });
  });
});
