"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Network } from "lucide-react";
import ReactFlow, {
  Background,
  Controls,
  type NodeMouseHandler,
} from "reactflow";
import "reactflow/dist/style.css";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useGraph } from "@/hooks/use-graph";
import { selectVisibleGraph } from "@/lib/graph/select";
import { layoutGraph } from "@/lib/graph/layout";
import { DepNode } from "@/components/repo/graph/dep-node";
import { GraphControls } from "@/components/repo/graph/graph-controls";
import { GraphLegend } from "@/components/repo/graph/graph-legend";
import { NodeDetailPanel } from "@/components/repo/graph/node-detail-panel";

const DEFAULT_N = 60;

// Defined at module scope so React Flow doesn't warn about a new object each render.
const nodeTypes = { dep: DepNode };

export function GraphPanel({ repoId }: { repoId: string }) {
  const [n, setN] = useState(DEFAULT_N);
  const [resolvedOnly, setResolvedOnly] = useState(false);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  const query = useGraph(repoId, resolvedOnly);
  const { data } = query;

  // Recompute layout only when the data (which changes with resolvedOnly via
  // the query key) or N changes — per the perf requirement.
  const layout = useMemo(() => {
    if (!data) return { nodes: [], edges: [] };
    return layoutGraph(selectVisibleGraph(data.nodes, data.edges, n));
  }, [data, n]);

  const selectedNode = useMemo(
    () => data?.nodes.find((node) => node.file_path === selectedPath) ?? null,
    [data, selectedPath],
  );

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }

  if (query.isError) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center gap-3 py-20 text-center">
          <AlertCircle className="size-7 text-destructive" />
          <p className="text-sm font-medium">Couldn&apos;t load the graph</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            {query.error?.message ?? "Something went wrong fetching the dependency graph."}
          </p>
          <Button variant="secondary" size="sm" onClick={() => query.refetch()}>
            Retry
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.node_count === 0) {
    return (
      <Card className="border-dashed">
        <CardContent className="flex flex-col items-center justify-center gap-2 py-20 text-center">
          <Network className="size-7 text-muted-foreground" />
          <p className="text-sm font-medium">No dependencies detected</p>
          <p className="max-w-sm text-sm text-muted-foreground">
            This repo was indexed but no import relationships were found between
            its files.
          </p>
        </CardContent>
      </Card>
    );
  }

  const handleNodeClick: NodeMouseHandler = (_event, node) => {
    setSelectedPath((current) => (current === node.id ? null : node.id));
  };

  return (
    <div className="flex flex-col gap-4">
      <GraphControls
        n={n}
        total={data.node_count}
        visibleCount={layout.nodes.length}
        resolvedOnly={resolvedOnly}
        onNChange={setN}
        onResolvedOnlyChange={setResolvedOnly}
      />

      <div className="flex h-[640px] gap-4">
        <div className="relative flex-1 overflow-hidden rounded-lg border border-border bg-background">
          <ReactFlow
            nodes={layout.nodes}
            edges={layout.edges}
            nodeTypes={nodeTypes}
            onNodeClick={handleNodeClick}
            onPaneClick={() => setSelectedPath(null)}
            fitView
            minZoom={0.1}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="hsl(220 16% 18%)" gap={20} />
            <Controls
              position="top-left"
              className="!border-border !bg-card"
            />
          </ReactFlow>
          <div className="pointer-events-none absolute bottom-3 left-3 right-3 rounded-md bg-card/80 px-3 py-2 backdrop-blur">
            <GraphLegend />
          </div>
        </div>

        {selectedNode && (
          <div className="w-80 shrink-0">
            <NodeDetailPanel
              node={selectedNode}
              allEdges={data.edges}
              onClose={() => setSelectedPath(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
