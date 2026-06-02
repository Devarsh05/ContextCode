"use client";

import { MessagesSquare, Network } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { ChatPanel } from "@/components/repo/chat/chat-panel";
import { GraphPanel } from "@/components/repo/graph/graph-panel";

/**
 * The indexed-repo workspace: a Chat tab (RAG Q&A) and a Graph tab (dependency
 * visualization with danger-zone analysis).
 */
export function Workspace({ repoId }: { repoId: string }) {
  return (
    <div className="container animate-fade-in px-6 py-8">
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">Workspace</h1>
        <Badge variant="secondary" className="font-mono text-xs">
          {repoId}
        </Badge>
      </div>

      <Tabs defaultValue="chat" className="w-full">
        <TabsList>
          <TabsTrigger value="chat" className="gap-1.5">
            <MessagesSquare className="size-4" />
            Chat
          </TabsTrigger>
          <TabsTrigger value="graph" className="gap-1.5">
            <Network className="size-4" />
            Graph
          </TabsTrigger>
        </TabsList>

        <TabsContent value="chat" className="mt-6">
          <ChatPanel repoId={repoId} />
        </TabsContent>

        <TabsContent value="graph" className="mt-6">
          <GraphPanel repoId={repoId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
