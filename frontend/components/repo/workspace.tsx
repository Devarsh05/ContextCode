"use client";

import { MessagesSquare, Network } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";

function EmptyState({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Network;
  title: string;
  body: string;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-2 py-20 text-center">
        <Icon className="size-7 text-muted-foreground" />
        <p className="text-sm font-medium">{title}</p>
        <p className="max-w-sm text-sm text-muted-foreground">{body}</p>
      </CardContent>
    </Card>
  );
}

/**
 * The indexed-repo workspace: Chat and Graph tabs. These render empty states
 * until Steps 5 and 6 wire up the chat and dependency-graph views.
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
          <EmptyState
            icon={MessagesSquare}
            title="Chat is coming online"
            body="Once this repo is indexed, ask questions and get answers grounded in its code."
          />
        </TabsContent>

        <TabsContent value="graph" className="mt-6">
          <EmptyState
            icon={Network}
            title="Dependency graph is coming online"
            body="A visual map of file dependencies with danger-zone analysis will render here."
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
